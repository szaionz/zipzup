import logging
import re
import time
from urllib import parse

from flask import make_response, request
from base_classes import ChannelProvider, LogoProvider, StreamProvider, GuideProvider, GuideEntry

from typing import List, Optional
from typing_extensions import override
from constants import *
import datetime
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from common_providers import DirectStreamProvider, ExternalLogoProvider
from models import my_redis
import redis_lock
from selenium import webdriver, common
from selenium.webdriver.chrome.options import Options
from keshet_experimental import KeshetStreamSimulator
import pickle
from io import BytesIO

KESHET_STREAM_EXPIRY = datetime.timedelta(minutes=5)
SIMULATOR_EXPIRY = datetime.timedelta(hours=12)

def get_stream(url, driver, stream_name='index.m3u8'):
    driver.get(url)
    # time.sleep(5)
    for _ in range(20):
        JS_get_network_requests = """

            const perf = window.performance || window.msPerformance || window.webkitPerformance;
            const network = perf.getEntriesByType("resource");
            return network;

        """
        network_requests = driver.execute_script(JS_get_network_requests)
        for n in network_requests:
            if stream_name in n["name"]:
                logging.info(f'Request: {n}')
                return n["name"]
        time.sleep(1)


class KeshetStreamProvider(StreamProvider):
    def __init__(self, index_stream: str, web: str, **kwargs):
        super().__init__(**kwargs)
        self.index_stream = index_stream
        self.web = web
        
    def _get_profile_simulator_cache_key(self, profile_index: str) -> str:
        return f'keshet:{self.tvg_id}_profile_simulator_{profile_index}'
    
    def _get_index_stream_cache_key(self) -> str:
        return f'keshet:{self.tvg_id}_index_stream'
    
    def get_index_stream(self) -> str:
        cached_stream = my_redis.get(self._get_index_stream_cache_key())
        if cached_stream:
            return cached_stream.decode('utf-8')
        else:
            return None
        
    def set_index_stream(self, stream_content: str):
        my_redis.set(self._get_index_stream_cache_key(), stream_content)
        
        
    def get_profile_simulator(self, profile_index: str) -> KeshetStreamSimulator:
        cached_bytes = my_redis.get(self._get_profile_simulator_cache_key(profile_index))
        if cached_bytes:
            with BytesIO(cached_bytes) as f:
                return pickle.load(f)
            
        else:
            return None
        
    def set_profile_simulator(self, profile_index: str, simulator: KeshetStreamSimulator):
        with BytesIO() as f:
            pickle.dump(simulator, f)
            my_redis.set(self._get_profile_simulator_cache_key(profile_index), f.getvalue())
            
    def get_my_profile_endpoint(self, index) -> str:
        """
        Returns the endpoint for the profile simulator.
        """
        return f'/{self.tvg_id}/profile/{index}/profileManifest.m3u8'
        
        
    @override
    def get_stream_url(self, request_base_url: str = 'http://localhost:5000') -> str:
        return f'{request_base_url}/{self.tvg_id}/{self.index_stream}'
    
    def _get_last_metadata_updated_key(self) -> str:
        return f'keshet:{self.tvg_id}_last_metadata_updated'
    
    def _get_last_metadata_updated(self) -> Optional[datetime.datetime]:
        last_updated = my_redis.get(self._get_last_metadata_updated_key())
        if last_updated:
            return datetime.datetime.fromisoformat(last_updated.decode('utf-8'))
        return None
    
    def _set_last_metadata_updated(self, timestamp: datetime.datetime):
        my_redis.set(self._get_last_metadata_updated_key(), timestamp.isoformat())
        
    def _get_max_profile_stream_key(self) -> str:
        return f'keshet:{self.tvg_id}_max_profile_stream'
    
    def _get_max_profile_stream(self) -> Optional[int]:
        max_profile = my_redis.get(self._get_max_profile_stream_key())
        if max_profile:
            return int(max_profile.decode('utf-8'))
        return None
    
    def _set_max_profile_stream(self, profile_index: int):
        my_redis.set(self._get_max_profile_stream_key(), str(profile_index))
        
    
    def refresh_metadata_cache(self):
        with redis_lock.Lock(my_redis, 'selenium'):
            with webdriver.Remote(command_executor='http://selenium:4444/wd/hub', options=webdriver.ChromeOptions()) as driver:
                out_url=get_stream(self.web, driver)
                if out_url:
                    pr = parse.urlparse(out_url)
                    qs_dict = parse.parse_qs(pr.query)
                    del qs_dict["b-in-range"]
                    pr=pr._replace(query=parse.urlencode(qs_dict, doseq=True))
                    out_url = pr.geturl()
                else:
                    logging.error("Failed to get stream URL from Keshet web page.")
                    return

        without_end = '/'.join(out_url.split('/')[:-1])
        # my_redis.set(f'keshet_{self.tvg_id}_stream_url', out_url, ex=KESHET_STREAM_EXPIRY)
        text=requests.get(out_url,
                        ).text
        lines = text.splitlines()
        outlines = []
        max_profile_index = 0
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                outlines.append(line)
            else:
                profileManifestUrl = (without_end + '/' + line)
                match = re.search(r"/profile/(\d+)/hdntl", profileManifestUrl)
                if match:
                    profile_index = int(match.group(1))
                    max_profile_index = max(max_profile_index, profile_index)
                    outlines.append(f"{self.get_my_profile_endpoint(profile_index)}")
                    self.set_profile_simulator(profile_index, KeshetStreamSimulator(profileManifestUrl))
                else:
                    continue
        text = '\n'.join(outlines) + '\n'
        
        self.set_index_stream(text)
        self._set_last_metadata_updated(datetime.datetime.now())
        self._set_max_profile_stream(max_profile_index)
        
    def health_check(self) -> bool:
        max_profile_index = self._get_max_profile_stream()
        if max_profile_index is None:
            return False
        for profile_index in range(0, max_profile_index + 1):
            simulator = self.get_profile_simulator(profile_index)
            if not simulator:
                logging.error(f"Profile {profile_index} health check failed.")
                return False
            if not simulator.sync_and_health_check():
                logging.error(f"Profile {profile_index} health check failed.")
                return False
            else:
                self.set_profile_simulator(profile_index, simulator)
        logging.info(f'Keshet stream provider {self.tvg_id} health check passed for all profiles.')
        return True
    
    
    @override
    def add_helper_routes(self, app):
        @app.route(f'/{self.tvg_id}/{self.index_stream}')
        def keshet_route():
            index_stream_content = self.get_index_stream()
            if index_stream_content:
                return index_stream_content, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}
            else:
                return "Index stream not found", 404

            
            return text, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}
        @app.route(f'/{self.tvg_id}/profile/<int:profile_index>/profileManifest.m3u8')
        def keshet_profile_route(profile_index: int):
            simulator = self.get_profile_simulator(profile_index)
            if not simulator:
                return "Profile simulator not found", 404
            return make_response(simulator.generate_playlist(), 200, {'Content-Type': 'application/vnd.apple.mpegurl'})


class KeshetGuideProvider(GuideProvider):
    def __init__(self, guide: str, **kwargs):
        super().__init__(**kwargs)
        self.guide = guide

    @override
    def get_guide(self) -> List[GuideEntry]:
        return [
            GuideEntry(
                start=datetime.datetime.fromtimestamp(item['StartTimeUTC']/1000),
                end= datetime.datetime.fromtimestamp(item['StartTimeUTC']/1000 + item['DurationMs']/1000),
                name=item['ProgramName'],
                description=item['EventDescription'],
                picture= item['Picture'],
                channel=self.tvg_id
            )
            for item in requests.get(self.guide).json()['programs']
        ]
        
class KeshetChannelProvider(ChannelProvider):
    channel_group = 'keshet'
    
    def __init__(self, index_stream: str, web: str, guide: str, **kwargs):
        self.stream_provider = KeshetStreamProvider(index_stream=index_stream, web=web, **kwargs)
        self.guide_provider = KeshetGuideProvider(guide=guide, **kwargs)
        self.logo_provider = ExternalLogoProvider(**kwargs)
        
    @override
    def get_guide_provider(self) -> GuideProvider:
        return self.guide_provider
    
    @override
    def get_stream_provider(self) -> StreamProvider:
        return self.stream_provider
    
    @override
    def get_logo_provider(self) -> LogoProvider:
        return self.logo_provider
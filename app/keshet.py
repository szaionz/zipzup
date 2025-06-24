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

KESHET_STREAM_EXPIRY = datetime.timedelta(minutes=5)

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
    @override
    def get_stream_url(self, request_base_url: str = 'http://localhost:5000') -> str:
        return f'{request_base_url}/{self.tvg_id}/{self.index_stream}'
    
    @override
    def add_helper_routes(self, app):
        @app.route(f'/{self.tvg_id}/{self.index_stream}')
        def keshet_route():
            stream_url =my_redis.get(f'keshet_{self.tvg_id}_stream_url')
            if stream_url:
                out_url = stream_url.decode('utf-8')
            else:
                with redis_lock.Lock(my_redis, 'selenium'):
                    stream_url = my_redis.get(f'keshet_{self.tvg_id}_stream_url')
                    if stream_url:
                        return requests.get(stream_url.decode('utf-8')).text, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}
                    with webdriver.Remote(command_executor='http://selenium:4444/wd/hub', options=webdriver.ChromeOptions()) as driver:
                        out_url=get_stream(self.web, driver)
                        if out_url:
                            pr = parse.urlparse(out_url)
                            qs_dict = parse.parse_qs(pr.query)
                            del qs_dict["b-in-range"]
                            pr=pr._replace(query=parse.urlencode(qs_dict, doseq=True))
                            out_url = pr.geturl()
                        else:
                            return "Stream not found", 404
            without_end = '/'.join(out_url.split('/')[:-1])
            my_redis.set(f'keshet_{self.tvg_id}_stream_url', out_url, ex=KESHET_STREAM_EXPIRY)
            text=requests.get(out_url,
                            
                            headers={'User-Agent': request.user_agent.string}
                            ).text
            lines = text.splitlines()
            outlines = []
            exp_time = None
            for line in lines:
                line = line.strip()
                if line.startswith('#'):
                    outlines.append(line)
                else:
                    match = re.search('hdntl=exp=(.*?)~acl=', line)
                    if match and match.group(1).isnumeric():
                        exp_time = datetime.datetime.fromtimestamp(int(match.group(1)))
                        logging.info(f"Stream expiration time: {exp_time}")
                    outlines.append(without_end + '/' + line)
            text = '\n'.join(outlines) + '\n'
            return text, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}


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
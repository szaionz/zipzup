import logging
from base_classes import ChannelProvider, LogoProvider, StreamProvider, GuideProvider, GuideEntry

from typing import List, Optional
from typing_extensions import override
from constants import *
import datetime
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from common_providers import DirectStreamProvider, ExternalLogoProvider

class KnessetGuideProvider(GuideProvider):
    def __init__(self, guide: str, **kwargs):
        super().__init__(**kwargs)
        self.guide = guide
        
    @override
    def get_guide(self) -> List[GuideEntry]:
        now = datetime.datetime.now(LOCAL_TZ)
        out_json = []
        
        # def delocalize_src(src: str) -> str:
        #     if src.startswith('/'):
        #         return f"{url}{src}"
        #     return src
        req = requests.get(self.guide)
        if req.status_code != 200:
            raise Exception(f"Failed to fetch Knesset guide data for {self.tvg_id}:  {req.status_code}")
        soup = BeautifulSoup(req.text, 'html.parser')
        navbar = soup.find('div', class_='broadcasts-navbar')
        dates = [div.get('data-date').strip() for div in navbar.find_all('div') if div.attrs.get('data-date')]
        broadcast_tables = soup.find_all('table', class_='broadcasts-table')
        old_start = None
        start = None
        for date, broadcast_table in zip(dates, broadcast_tables):
            date_str = date
            for item in broadcast_table.find_all('div', class_='brodcast-listing-desktop'):
                old_start = start
                start = LOCAL_TZ.localize(datetime.datetime.strptime(f"{date_str} {item.find('p', class_='broadcast-list-content-timing').text.strip()}", '%Y-%m-%d %H:%M'))
                if old_start and start < old_start:
                    date_str = (LOCAL_TZ.localize(datetime.datetime.strptime(date_str, '%Y-%m-%d')) + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
                    start = LOCAL_TZ.localize(datetime.datetime.strptime(f"{date_str} {item.find('p', class_='broadcast-list-content-timing').text.strip()}", '%Y-%m-%d %H:%M'))
                out_json.append(
                    {
                        'start': start,
                        'name': item.find(class_='broadcast-list-content-title').text.strip(),
                        'description': item.find('div', class_='broadcast-desc-alt').text.strip() if item.find('div', class_='broadcast-desc-alt') else '',
                        'picture': (item.find('div', class_='broadcastImage').find('img')['src']) if item.find('div', class_='broadcastImage') else None
                    }
                )
        out_json = sorted(out_json, key=lambda x: x['start'])
        out_json_with_end = []
        for i, j in zip(out_json, out_json[1:]):
            i['end'] = j['start']
            out_json_with_end.append(i)
        return [
            GuideEntry(
                **entry,
                channel=self.tvg_id
            )
            for entry in out_json_with_end
        ]
            
class KnessetChannelProvider(ChannelProvider):
    channel_group = 'knesset'
    
    def __init__(self, **kwargs):
        self.guide_provider = KnessetGuideProvider(**kwargs)
        self.stream_provider = DirectStreamProvider(**kwargs)
        self.logo_provider = ExternalLogoProvider(
            **kwargs
        )
    @override
    def get_guide_provider(self) -> GuideProvider:
        return self.guide_provider
    @override
    def get_stream_provider(self) -> StreamProvider:
        return self.stream_provider
    @override
    def get_logo_provider(self) -> LogoProvider:
        return self.logo_provider
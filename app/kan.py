from base_classes import ChannelProvider, LogoProvider, StreamProvider, GuideProvider, GuideEntry

from typing import List, Optional
from typing_extensions import override
from constants import *
import datetime
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from common_providers import DirectStreamProvider

class KanGuideProvider(GuideProvider):
    def __init__(self, channel_id: int, **kwargs):
        super().__init__(**kwargs)
        self.channel_id = channel_id
    
    @override
    def get_guide(self) -> List[GuideEntry]:
        headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        # 'Accept-Encoding': 'gzip, deflate, br, zstd',
        'X-Time-Offset': '0',
        'X-Requested-With': 'XMLHttpRequest',
        'DNT': '1',
        'Sec-GPC': '1',
        'Connection': 'keep-alive',
        'Referer': f'https://www.kan.org.il/tv-guide/?channelId={self.channel_id}',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        }
        now = datetime.datetime.now(LOCAL_TZ)
        out_json = []
        for dt_offset in range(-7, 7):
            dt = now + datetime.timedelta(days=dt_offset)
            date_str = dt.strftime('%d-%m-%Y')
            response = requests.get(
                "https://www.kan.org.il/umbraco/surface/LoadBroadcastSchedule/LoadSchedule",
                                    params={
                                        'channelId': f'{self.channel_id}',
                                        'currentPageId': '1517',
                                        'day': date_str,
                                        },
                                    headers=headers
                                    )
            if response.status_code != 200:
                print(f"Failed to fetch data for {date_str}: {response.status_code}")
                raise Exception(f"Failed to fetch data for {date_str}: {response.status_code}")
            soup = BeautifulSoup(response.text, 'html.parser')
            # print(response.text)
            def delocalize(src):
                if src.startswith('/'):
                    return f"https://www.kan.org.il{src}"
                return src
            out_json.extend(
                [
                    {
                        'start':UTC.localize(date_parser.parse(item.find_next('p', class_='program-hour')['data-date-utc'], dayfirst=True)),
                        'name': item.find('h3', class_='program-title').text.strip(),
                        'description': item.find('div', class_='program-description').text.strip(),
                        'picture': f"{delocalize(item.find('img', class_='img-fluid')['src'])}" if item.find('img', class_='img-fluid') else None
                    } for item in soup.find_all('div', class_='results-item')
                ]
            )
        out_json = sorted(out_json, key=lambda x: x['start'])
        # print(out_json)
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

class KanLogoProvider(LogoProvider):
    def __init__(self, channel_id: int, **kwargs):
        self.channel_id = channel_id
    
    @override
    def get_img(self, request_base_url: str = 'http://localhost:5000') -> str:
        return f'{request_base_url}/static/kan_pngs/{self.channel_id}.png'
    
class KanChannelProvider(ChannelProvider):
    channel_group = 'kan'
    def __init__(self, **kwargs):
        self.guide_provider = KanGuideProvider(**kwargs)
        self.stream_provider = DirectStreamProvider(**kwargs)
        self.logo_provider = KanLogoProvider(**kwargs)
        
    @override
    def get_guide_provider(self) -> GuideProvider:
        return self.guide_provider
    
    @override
    def get_stream_provider(self) -> StreamProvider:
        return self.stream_provider
    
    @override
    def get_logo_provider(self) -> LogoProvider:
        return self.logo_provider
        
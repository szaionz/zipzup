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

class I24GuideProvider(GuideProvider):
    def __init__(self, guide: str, **kwargs):
        super().__init__(**kwargs)
        self.guide = guide
        
    @override
    def get_guide(self) -> List[GuideEntry]:
        r = requests.get(self.guide)
        if r.status_code != 200:
            logging.error("Failed to fetch i24 News EPG")
            raise Exception("Failed to fetch i24 News EPG")
        data = r.json()
        out_json = []
        now = datetime.datetime.now(tz=LOCAL_TZ)
        most_recent_sunday = (now - datetime.timedelta(days=(now.weekday() + 1) % 7)).date()
        # most_recent_sunday_str = most_recent_sunday.strftime('%Y-%m-%d')
        for item in data:
            relevant_date = most_recent_sunday+ datetime.timedelta(days=item['day'])
            relevant_date_str = relevant_date.strftime('%Y-%m-%d')

            time_start = datetime.datetime.strptime(f"{relevant_date_str} {item['startHour']}", f'%Y-%m-%d %H:%M').replace(tzinfo=LOCAL_TZ)
            time_end = datetime.datetime.strptime(f"{relevant_date_str} {item['endHour']}", f'%Y-%m-%d %H:%M').replace(tzinfo=LOCAL_TZ)
            if time_end < time_start:
                logging.warning(f"End time {time_end} is before start time {time_start} for program {item['show']['title']}, adding one day to end time.")
                time_end += datetime.timedelta(days=1)
            if 'text' in item['show']['parsedBody'][0]:
                description = item['show']['parsedBody'][0]['text']
            elif 'children' in item['show']['parsedBody'][0]:
                description = ' '.join(child['text'] for child in item['show']['parsedBody'][0]['children'] if 'text' in child)
            else:
                description = ''
            out_json.append(GuideEntry(
                start= time_start,
                end=time_end,
                name= item['show']['title'],
                description= description,
                picture=item['show']['image']['href'],
                channel=self.tvg_id
            )
            )
        return out_json
    
class I24ChannelProvider(ChannelProvider):
    channel_group = 'i24'
    
    def __init__(self, **kwargs):
        self.guide_provider = I24GuideProvider(**kwargs)
        self.stream_provider = DirectStreamProvider(**kwargs)
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
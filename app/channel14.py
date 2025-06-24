import json
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

class Channel14GuideProvider(GuideProvider):
    def __init__(self, guide: str, **kwargs):
        super().__init__(**kwargs)
        self.guide = guide
        
    @override
    def get_guide(self) -> List[GuideEntry]:
        r = requests.get(self.guide)
        if r.status_code != 200:
            return []
        text =r.text
        soup = BeautifulSoup(text, 'html.parser')
        relevant_scripts = [script for script in soup.find_all('script') if 'program' in script.text]
        if not relevant_scripts:
            raise Exception("No relevant script found in the page")
        relevant_script = relevant_scripts[0] if relevant_scripts else None
        m=json.loads(relevant_script.text[relevant_script.text.index('"')-3: relevant_script.text.rindex('"')+2])
        d=json.loads(m[1][m[1].index('['):])[-1]['children'][-1]['data']
        out = []
        for d_ in d:
            for date, programs in d_.items():
                for program in programs:
                    start_date = datetime.datetime.strptime(f'{date} {program["start"]}', '%Y-%m-%d %H:%M').replace(tzinfo=LOCAL_TZ)
                    end_date = datetime.datetime.strptime(f'{date} {program["end"]}', '%Y-%m-%d %H:%M').replace(tzinfo=LOCAL_TZ)
                    if end_date.timestamp()<start_date.timestamp():
                        logging.warning(f"End date {end_date} is before start date {start_date} for program {program['program']}, adding one day to start date.")
                        end_date += datetime.timedelta(days=1)
                    out.append(GuideEntry(
                            start= start_date,
                            end= end_date,
                            name= program['program'],
                            description= program['subtitle'],
                            picture= program['image'],
                            channel=self.tvg_id
                        )
                    )
        return out
    
class Channel14ChannelProvider(ChannelProvider):
    channel_group = '14'
    
    def __init__(self, **kwargs):
        self.guide_provider = Channel14GuideProvider(**kwargs)
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
from base_classes import ChannelProvider, LogoProvider, StreamProvider, GuideProvider, GuideEntry

from typing import List, Optional
from typing_extensions import override
from constants import *
import datetime
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from common_providers import ExternalLogoProvider, StreamWithRefererProvider

class ReshetGuideProvider(GuideProvider):
    def __init__(self, id, guide, **kwargs):
        self.tvg_id = id
        self.guide = guide
        
    @override
    def get_guide(self) -> List[GuideEntry]:
        r = requests.get(self.guide)
        if r.status_code != 200:
            raise Exception("Failed to fetch Reshet EPG")
        data = r.json()
        out_json = []
        for week in data['pageProps']['page']['Content']['PageGrid'][0]['broadcastWeek']:
            for program in week['shows']:
                try:
                    out_json.append({
                        'start': LOCAL_TZ.localize(datetime.datetime.strptime(f"{program['show_date']} {program['start_time']}", '%Y-%m-%d %H:%M')),
                        'name': program['title'],
                        'description': program['desc'],
                        'picture': program['imageObj'].get('d') or program['imageObj'].get('m'),
                    })
                except:
                    continue
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
        
class ReshetChannelProvider(ChannelProvider):
    channel_group = 'reshet'
    
    def __init__(self, **kwargs):
        self.guide_provider = ReshetGuideProvider(**kwargs)
        self.stream_provider = StreamWithRefererProvider(**kwargs)
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
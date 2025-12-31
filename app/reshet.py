from base_classes import ChannelProvider, LogoProvider, StreamProvider, GuideProvider, GuideEntry

from typing import List, Optional
from typing_extensions import override
from constants import *
import datetime
import requests
import json
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from common_providers import ExternalLogoProvider, StreamWithRefererProvider

class ReshetGuideProvider(GuideProvider):
    def __init__(self, id, guide, **kwargs):
        self.tvg_id = id
        self.guide = guide
        
    @override
    def get_guide(self) -> List[GuideEntry]:
        base_url = "https://13tv.co.il"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # 1. Fetch the homepage HTML
        # This will raise requests.exceptions.HTTPError for 4xx/5xx responses
        # or ConnectionError for network issues.
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()

        # 2. Parse HTML to find the __NEXT_DATA__ script
        soup = BeautifulSoup(response.text, "html.parser")
        next_data_tag = soup.find("script", {"id": "__NEXT_DATA__"})

        if not next_data_tag:
            raise ValueError("Could not find <script id='__NEXT_DATA__'> tag in the HTML source.")

        # 3. Load the JSON data and extract the buildId
        try:
            data = json.loads(next_data_tag.string)
            build_id = data['buildId']
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode __NEXT_DATA__ JSON: {e}")
        except KeyError:
            raise ValueError("The 'buildId' key was missing from the __NEXT_DATA__ JSON object.")

        # 4. Construct the dynamic URL
        dynamic_url = f"{base_url}/_next/data/{build_id}/he/tv-guide.json?all=tv-guide"

        r = requests.get(dynamic_url)
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
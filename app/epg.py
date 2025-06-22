from io import BytesIO
import logging
from xml.etree import ElementTree as ET
import datetime
from zipfile import ZipFile
from bs4 import BeautifulSoup
import requests
import pytz
from dateutil import parser as date_parser
import json 
import os
from datetime import timedelta

TZ = pytz.timezone('Asia/Jerusalem')
JSON_DIR = os.environ.get('JSON_DIR', '/json')
GUIDE_COOLDOWN = timedelta(days=1)
with open('/app/channels.json', 'r', encoding='utf-8') as f:
    CHANNELS = json.load(f)
    
def epg_json_to_xml_tv(json_data):
    root = ET.Element("tv")
    
    for channel in json_data.keys():
        channel_element = ET.SubElement(root, "channel", id=channel)
        display_name = ET.SubElement(channel_element, "display-name")
        display_name.text = channel
        # root.append(channel_element)
    for channel, programs in json_data.items():
        if programs:
            for program in programs:
                start_datetime = datetime.datetime.fromtimestamp(program["start"], tz=datetime.timezone.utc)
                stop_datetime = datetime.datetime.fromtimestamp(program["end"], tz=datetime.timezone.utc)
                programme_element = ET.SubElement(root, "programme", start=start_datetime.strftime("%Y%m%d%H%M%S %z"),
                                                stop=stop_datetime.strftime("%Y%m%d%H%M%S %z"),
                                                channel=channel)
                title_element = ET.SubElement(programme_element, "title")
                title_element.text = program["name"]
                desc_element = ET.SubElement(programme_element, "desc")
                desc_element.text = program["description"].replace('(C) פישנזון', '').strip()
                if "picture" in program:
                    icon_element = ET.SubElement(programme_element, "icon", src=program["picture"])
                    # programme_element.append(icon_element)
                # root.append(programme_element)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')


def get_keshet_epg_json():
    return [
            {
                'start': item['StartTimeUTC']/1000,
                'end': item['StartTimeUTC']/1000 + item['DurationMs']/1000,
                'name': item['ProgramName'],
                'description': item['EventDescription'],
                'picture': item['Picture']
            } for item in
            requests.get("https://www.mako.co.il/AjaxPage?jspName=EPGResponse.jsp").json()['programs']
        ]


def get_i24_news_epg_json():
    r = requests.get('https://api.i24news.tv/v2/he/schedules')
    if r.status_code != 200:
        logging.error("Failed to fetch i24 News EPG")
        raise Exception("Failed to fetch i24 News EPG")
    data = r.json()
    out_json = []
    now = datetime.datetime.now(tz=TZ)
    most_recent_sunday = (now - datetime.timedelta(days=(now.weekday() + 1) % 7)).date()
    # most_recent_sunday_str = most_recent_sunday.strftime('%Y-%m-%d')
    for item in data:
        relevant_date = most_recent_sunday+ datetime.timedelta(days=item['day'])
        relevant_date_str = relevant_date.strftime('%Y-%m-%d')

        time_start = datetime.datetime.strptime(f"{relevant_date_str} {item['startHour']}", f'%Y-%m-%d %H:%M').replace(tzinfo=TZ)
        time_end = datetime.datetime.strptime(f"{relevant_date_str} {item['endHour']}", f'%Y-%m-%d %H:%M').replace(tzinfo=TZ)
        if time_end < time_start:
            logging.warning(f"End time {time_end} is before start time {time_start} for program {item['show']['title']}, adding one day to end time.")
            time_end += datetime.timedelta(days=1)
        out_json.append({
            'start': time_start.timestamp(),
            'end': time_end.timestamp(),
            'name': item['show']['title'],
            'description': item['show']['parsedBody'][0]['text'],
            'picture': item['show']['image']['href']
        })
    return out_json


def get_kan_epg_json(channel_id='4444'):
    
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
        'Referer': f'https://www.kan.org.il/tv-guide/?channelId={channel_id}',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    }
    TZ = pytz.timezone('Asia/Jerusalem')
    now = datetime.datetime.now(TZ)
    out_json = []
    for dt_offset in range(-7, 7):
        dt = now + datetime.timedelta(days=dt_offset)
        date_str = dt.strftime('%d-%m-%Y')
        response = requests.get(
            "https://www.kan.org.il/umbraco/surface/LoadBroadcastSchedule/LoadSchedule",
                                params={
                                    'channelId': f'{channel_id}',
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
                    'start':date_parser.parse(item.find_next('p', class_='program-hour')['data-date-utc'], dayfirst=True).timestamp(),
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
    return out_json_with_end

def get_now_14_epg_json():
    r = requests.get('https://www.c14.co.il/shidurim')
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
                start_date = datetime.datetime.strptime(f'{date} {program["start"]}', '%Y-%m-%d %H:%M').replace(tzinfo=TZ)
                end_date = datetime.datetime.strptime(f'{date} {program["end"]}', '%Y-%m-%d %H:%M').replace(tzinfo=TZ)
                if end_date.timestamp()<start_date.timestamp():
                    logging.warning(f"End date {end_date} is before start date {start_date} for program {program['program']}, adding one day to start date.")
                    end_date += datetime.timedelta(days=1)
                out.append({
                    'start': start_date.timestamp(),
                    'end': end_date.timestamp(),
                    'name': program['program'],
                    'description': program['subtitle'],
                    'picture': program['image'],
                })
    return out

def get_reshet_epg_json():
    r = requests.get('https://13tv.co.il/_next/data/7KvrHSb4k5_4V5p4Z7CYE/he/tv-guide.json?all=tv-guide')
    if r.status_code != 200:
        raise Exception("Failed to fetch Reshet EPG")
    data = r.json()
    out_json = []
    for week in data['pageProps']['page']['Content']['PageGrid'][0]['broadcastWeek']:
        for program in week['shows']:
            try:
                out_json.append({
                    'start': datetime.datetime.strptime(f"{program['show_date']} {program['start_time']}", '%Y-%m-%d %H:%M').replace(tzinfo=TZ).timestamp(),
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
    return out_json_with_end


def get_base_epg_json():
    r = requests.get('https://bit.ly/epgfish', stream=True)
    with ZipFile(BytesIO(r.raw.read())) as zf:
        json_data = zf.read('epg.json').decode('utf-8')
    json_data = json.loads(json_data)
    return json_data
    
GUIDES = {
        '12': get_keshet_epg_json,
        # '11': get_kan_epg_json,
        '14': get_now_14_epg_json,
        'epg': get_base_epg_json,
        'i24news': get_i24_news_epg_json,
        '13': get_reshet_epg_json,
        **{k: lambda channel_id=channel['id']: get_kan_epg_json(channel_id) for k, channel in CHANNELS['kan'].items() if channel.get('enabled')}
    }

def get_channel_path(channel):
    return os.path.join(JSON_DIR, channel + '.json')

def sync_guides():
    for channel, func in GUIDES.items():
        logging.info(f"Fetching EPG for channel {channel}")
        if os.path.exists(get_channel_path(channel)):
            last_modified = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(JSON_DIR, channel + '.json')), tz=TZ)
            if datetime.datetime.now(tz=TZ) - last_modified < GUIDE_COOLDOWN:
                logging.info(f"Using cached EPG for channel {channel}")
                continue
        try:
            guide = func()
        except Exception as e:
            logging.error(f"Failed to fetch EPG for channel {channel}: {e}")
            guide = []
        if guide:
            with open(get_channel_path(channel), 'w', encoding='utf-8') as f:
                json.dump(guide, f, ensure_ascii=False)
                logging.info(f"Saved EPG for channel {channel} to {get_channel_path(channel)}")
            
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting EPG sync")
    sync_guides()
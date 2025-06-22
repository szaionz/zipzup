from datetime import timedelta
import datetime
import hashlib
from io import BytesIO
import logging
import os
import re
from selenium import webdriver
import time
from urllib import parse
from flask import Flask, make_response, redirect, request
import requests
import epg 
import json
from zipfile import ZipFile
import redis
import redis_lock

from epg import epg_json_to_xml_tv, get_channel_path, get_keshet_epg_json, get_kan_epg_json, get_now_14_epg_json, GUIDES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
r = redis.Redis(host='redis', port=6379, db=0)
app = Flask(__name__, static_folder='static', static_url_path='/static')

URL = "https://www.mako.co.il/mako-vod-live-tv/"
RESHET_ROOT='https://reshet.g-mana.live/media/87f59c77-03f6-4bad-a648-897e095e7360/'

with open('/app/channels.json', 'r', encoding='utf-8') as f:
    CHANNELS = json.load(f)
    
with open('tuner.m3u', 'r') as f:
    PLAYLIST = f.read()
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
                return n["name"]
        time.sleep(1)


@app.route('/keshet/index.m3u8')
def keshet():
    etag = request.headers.get('If-None-Match')
    if etag and r.get(f'keshet_index_m3u8_etag:{etag}'):
        return '', 304, {'Content-Type': 'application/vnd.apple.mpegurl', 'Etag': etag}
    text = r.get('keshet_index_m3u8')
    
    if not text:    
        stream_url =r.get('keshet_stream_url')
        if stream_url:
            out_url = stream_url.decode('utf-8')
        else:
            with redis_lock.Lock(r, 'selenium'):
                stream_url = r.get('keshet_stream_url')
                if stream_url:
                    return requests.get(stream_url.decode('utf-8')).text, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}
                with webdriver.Remote(command_executor='http://selenium:4444/wd/hub', options=webdriver.ChromeOptions()) as driver:
                    out_url=get_stream(URL, driver)
                    if out_url:
                        pr = parse.urlparse(out_url)
                        qs_dict = parse.parse_qs(pr.query)
                        del qs_dict["b-in-range"]
                        pr=pr._replace(query=parse.urlencode(qs_dict, doseq=True))
                        out_url = pr.geturl()
                        # return redirect(out_url, code=302)
                    else:
                        return "Stream not found", 404
        without_end = '/'.join(out_url.split('/')[:-1])
        r.set('keshet_stream_url', out_url, ex=timedelta(minutes=5))
        text=requests.get(out_url).text
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
        text = '\n'.join(outlines)
    else:
        text = text.decode('utf-8')
        exp_time = datetime.datetime.fromtimestamp(float(r.get('keshet_index_m3u8_exp'))) if r.get('keshet_index_m3u8_exp') else None
    response = make_response(text)
    if exp_time:
        response.headers['Cache-Control'] = f'public, max-age={int((exp_time - datetime.datetime.now()).total_seconds())}'
    response.headers['Content-Type'] = 'application/vnd.apple.mpegurl'
    etag = hashlib.md5(text.encode('utf-8')).hexdigest()
    response.headers['ETag'] = etag
    if exp_time and etag:
        r.set(f'keshet_index_m3u8_etag:{etag}', text, ex=timedelta(seconds=int((exp_time - datetime.datetime.now()).total_seconds())))
        r.set('keshet_index_m3u8', text, ex=timedelta(seconds=int((exp_time - datetime.datetime.now()).total_seconds())))
    if exp_time:
        r.set('keshet_index_m3u8_exp', exp_time.timestamp(), ex=timedelta(seconds=int((exp_time - datetime.datetime.now()).total_seconds())))
    response.headers['Etag'] = etag
    return response


@app.route('/reshet/<path:path>')
def reshet(path):
    text_response = requests.get(RESHET_ROOT + path,
                                 headers={'Referrer': 'https://13tv.co.il/live/'},
                                 params=request.args
                                 ).text
    return text_response, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}

@app.route('/')
def root():
    url = request.base_url
    parsed_url = parse.urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    playlist = PLAYLIST.replace('$HOST', base_url)
    for tvg, channel in CHANNELS['kan'].items():
        if not channel.get('enabled'):
            continue
        id_ = channel['id']
        name = channel['name']
        stream = channel['stream']
        playlist += f'#EXTINF:-1 tvg-chno={tvg} tvg-id="{tvg}" group-title="TV" tvg-logo="{base_url}/static/kan_pngs/{id_}.png", {name}\n'
        playlist += f'{stream}\n\n'
    return make_response(playlist, 200, {'Content-Type': 'application/vnd.apple.mpegurl'})

@app.route('/epg.xml')
def get_epg():
    if os.path.exists(get_channel_path('epg')):
        with open(get_channel_path('epg'), 'r') as f:
            base_json_data = json.load(f)
    else:
        base_json_data = {}
    for channel in GUIDES.keys():
        if channel == 'epg':
            continue
        if os.path.exists(get_channel_path(channel)):
            with open(get_channel_path(channel), 'r', encoding='utf-8') as f:
                channel_json_data = json.load(f)
                base_json_data[channel] = channel_json_data
    return epg_json_to_xml_tv(base_json_data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
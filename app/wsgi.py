import datetime
import json
import logging
import os
from typing import List
from urllib import parse
from flask import Flask, request, redirect
from constants import UTC
import models
from abc import ABC, abstractmethod
import base_classes
import common_providers
import kan
from channels import channel_providers
from xml.etree import ElementTree as ET
from sqlalchemy.orm import Session


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



app = Flask(__name__, static_folder='static', static_url_path='/static')

for provider in channel_providers:
    provider.get_stream_provider().add_helper_routes(app)

@app.after_request
def my_after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route('/')
def index():
    base_url = get_base_url()
    return '#EXTM3U\n' + '\n'.join(
        [
            provider.get_m3u8_lines(base_url)
            for provider in channel_providers
        ]
    ), 200, {'Content-Type': 'application/vnd.apple.mpegurl'}

@app.route('/epg.xml')
def epg():
    root = ET.Element('tv')
    for channel in channel_providers:
        channel_element = ET.SubElement(root, "channel", id=channel.get_stream_provider().tvg_id)
        display_name = ET.SubElement(channel_element, "display-name")
        display_name.text = channel.get_stream_provider().name
        # root.append(channel_element)
    with Session(models.engine) as session:
        guide_entries = session.query(models.GuideEntry).all()
    programs = guide_entries
    for program in programs:
        start_datetime = program.start.replace(tzinfo=UTC)
        stop_datetime = program.end.replace(tzinfo=UTC)
        programme_element = ET.SubElement(root, "programme", start=start_datetime.strftime("%Y%m%d%H%M%S %z"),
                                        stop=stop_datetime.strftime("%Y%m%d%H%M%S %z"),
                                        channel=program.channel)
        title_element = ET.SubElement(programme_element, "title")
        title_element.text = program.name
        desc_element = ET.SubElement(programme_element, "desc")
        desc_element.text = program.description if program.description else ''
        if program.picture:
            icon_element = ET.SubElement(programme_element, "icon", src=program.picture)
            
    xml_str = ET.tostring(root, encoding='utf-8', method='xml')
    response = app.response_class(xml_str, mimetype='application/xml')
    response.headers['Content-Disposition'] = 'attachment; filename=epg.xml'
    return response

def get_base_url():
    url = request.base_url
    parsed_url = parse.urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    return base_url

    


if __name__ == '__main__':
    logging.info('Starting Flask app...')
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('DEBUG', 'false').lower() == 'true')
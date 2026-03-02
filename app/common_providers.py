from base_classes import *
from typing import List
from datetime import datetime, timedelta
import requests
from flask import Flask, request
import urllib.parse


class DirectStreamProvider(StreamProvider):
    def __init__(self, stream: str, **kwargs):
        super().__init__(**kwargs)
        self.stream = stream
        
    def get_stream_url(self, request_base_url: str = 'http://localhost:5000') -> str:
        return self.stream
    
class ExternalLogoProvider(LogoProvider):
    def __init__(self, img: str, **kwargs):
        self.img = img
        
    def get_img(self, request_base_url: str = 'http://localhost:5000') -> str:
        return self.img
    
class StreamWithAdditionalHeadersProvider(StreamProvider):
    def __init__(self, additional_headers: dict, root: str, index_stream: str, **kwargs):
        super().__init__(**kwargs)
        self.additional_headers = additional_headers
        self.root = root
        self.index_stream = index_stream
        
    def get_stream_url(self, request_base_url: str = 'http://localhost:5000') -> str:
        return f'{request_base_url}/{self.tvg_id}/{self.index_stream}'
    
    def _my_route(self, path):
        req = requests.get(
            f'{self.root}/{path}',
            headers=self.additional_headers,
            params=request.args
        )
        if req.status_code != 200:
            raise ValueError(f'Failed to fetch {path} from {self.root}')
        return req.content, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}
    
    
    def add_helper_routes(self, app):
        @app.route(f'/{self.tvg_id}/<path:path>')
        def my_route(path):
            return self._my_route(path)
        
class MPDProvider(StreamProvider):
    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.mpd_url = url
        
    def get_stream_url(self, request_base_url: str = 'http://localhost:5000') -> str:
        return f'{request_base_url}/proxy/mpd/manifest.m3u8?{urllib.parse.urlencode({"d": self.mpd_url,"remux_to_ts": "true"})}'
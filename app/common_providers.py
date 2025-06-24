from base_classes import *
from typing import List
from datetime import datetime, timedelta
import requests
from flask import Flask, request


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
    
class StreamWithRefererProvider(StreamProvider):
    def __init__(self, referer: str, root: str, index_stream: str, **kwargs):
        super().__init__(**kwargs)
        self.referer = referer
        self.root = root
        self.index_stream = index_stream
        
    def get_stream_url(self, request_base_url: str = 'http://localhost:5000') -> str:
        return f'{request_base_url}/{self.tvg_id}/{self.index_stream}'
    
    def _my_route(self, path):
        req = requests.get(
            f'{self.root}/{path}',
            headers={'Referer': self.referer},
            params=request.args
        )
        if req.status_code != 200:
            raise ValueError(f'Failed to fetch {path} from {self.root}')
        return req.content, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}
    
    
    def add_helper_routes(self, app):
        @app.route(f'/{self.tvg_id}/<path:path>')
        def my_route(path):
            return self._my_route(path)
        

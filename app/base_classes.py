from abc import ABC, abstractmethod
from flask import Flask
import datetime
from models import GuideEntry
from typing import List

class StreamProvider(ABC):
    """
    Abstract base class for stream providers.
    """
    def __init__(self, name: str, id: str, **kwargs):
        """
        Initializes the StreamProvider with a name, image, and TVG ID.
        
        :param name: The name of the stream provider.
        :param img: The image URL or path for the stream provider.
        :param tvg_id: The TVG ID for the stream provider.
        :param kwargs: Additional keyword arguments for future extensions.
        """
        self.name = name
        self.tvg_id = id
        self.kwargs = kwargs
    
    @abstractmethod
    def get_stream_url(self, request_base_url: str='http://localhost:5000') -> str:
        """
        Returns the stream URL for the provider.
        If the URL is static, it should return a static URL.
        If the URL is dynamic, it should return a dynamic URL based on the request base URL.
        """
        raise NotImplementedError()
    
    def add_helper_routes(self, app: Flask):
        """
        Adds helper routes to the Flask app.
        This method should be implemented by subclasses to add any necessary routes.
        """
        pass
        
    

class LogoProvider(ABC):
    @abstractmethod
    def get_img(self, request_base_url: str='http://localhost:5000') -> str:
        """
        Returns the image URL for the provider.
        If the image is static, it should return a static URL.
        If the image is dynamic, it should return a dynamic URL based on the request base URL.
        
        :param request_base_url: The base URL of the request, used to construct full URLs.
        :return: The image URL as a string.
        """
        raise NotImplementedError()

class GuideProvider(ABC):
    """
    Abstract base class for guide providers.
    """
    def __init__(self, id: str,  **kwargs):
        """
        Initializes the GuideProvider with a TVG ID and guide.
        
        :param tvg_id: The TVG ID for the guide provider.
        :param guide: The guide information.
        :param kwargs: Additional keyword arguments for future extensions.
        """
        self.tvg_id = id
        self.kwargs = kwargs
        
    @abstractmethod
    def get_guide(self) -> List[GuideEntry]:
        """
        Returns a list of GuideEntry objects for the provider.
        
        :param request_base_url: The base URL of the request, used to construct full URLs.
        :return: A list of GuideEntry objects.
        """
        raise NotImplementedError()
    
class ChannelProvider(ABC):
    @abstractmethod
    def get_guide_provider(self) -> GuideProvider:
        """
        Returns the guide provider for the channel.
        
        :return: An instance of GuideProvider.
        """
        raise NotImplementedError()
    @abstractmethod
    def get_stream_provider(self) -> StreamProvider:
        """
        Returns the stream provider for the channel.
        
        :return: An instance of StreamProvider.
        """
        raise NotImplementedError()
    
    @abstractmethod
    def get_logo_provider(self) -> LogoProvider:
        raise NotImplementedError()
    
    def get_m3u8_lines(self, request_base_url: str='http://localhost:5000') -> list:
        """
        Returns a list of M3U8 lines for the stream provider.
        
        :param request_base_url: The base URL of the request, used to construct full URLs.
        :return: A list of M3U8 lines.
        """
        return '\n'.join([
            f'#EXTINF:-1 tvg-chno={self.get_stream_provider().tvg_id} tvg-id="{self.get_stream_provider().tvg_id}" tvg-logo="{self.get_logo_provider().get_img(request_base_url)}" group-title="TV", {self.get_stream_provider().name}',
            self.get_stream_provider().get_stream_url(request_base_url)
        ])+ '\n\n'
    

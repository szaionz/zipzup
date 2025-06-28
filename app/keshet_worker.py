from channels import channel_providers
from keshet import KeshetChannelProvider, KeshetStreamProvider
import logging

def health_check_and_refresh_keshet():
    for provider in channel_providers:
        if isinstance(provider, KeshetChannelProvider):
            stream_provider: KeshetStreamProvider = provider.get_stream_provider()
            max_retries = 5
            i=0
            while not stream_provider.health_check() and i < max_retries:
                logging.error(f"Keshet stream provider {stream_provider.tvg_id} health check failed. Refreshing")
                stream_provider.refresh_metadata_cache()
                i += 1
                if i >= max_retries:
                    logging.error(f"Keshet stream provider {stream_provider.tvg_id} health check failed after {max_retries} retries. Giving up.")
                    break
                
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    try:
        health_check_and_refresh_keshet()
    except Exception as e:
        logging.error(f"Error during health check and refresh: {e}")
                
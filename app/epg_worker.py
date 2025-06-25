from models import *
from channels import channel_providers
from sqlalchemy.orm import Session
import logging
from sqlalchemy import func
import datetime
from keshet import KeshetChannelProvider, KeshetStreamProvider


GUIDE_COOLDOWN = datetime.timedelta(hours=12)
KEEP_BACKLOGS = datetime.timedelta(days=14)
def main():
    with Session(engine) as session:
        q = session.query(GuideEntry).filter(GuideEntry.end < datetime.datetime.now(UTC) - KEEP_BACKLOGS)
        logging.info(f"Deleting {q.count()} old guide entries.")
        q.delete(synchronize_session=False)
        for provider in channel_providers:
            last_updated = session.query(func.max(GuideEntry.updated)).filter_by(channel=provider.get_guide_provider().tvg_id).first()[0]
            if not last_updated or datetime.datetime.now(UTC) - UTC.localize(last_updated) >= GUIDE_COOLDOWN or os.environ.get('DEBUG', 'false').lower() == 'true':
                try:
                    entries = provider.get_guide_provider().get_guide()
                except Exception as e:
                    logging.error(f"Failed to fetch guide for provider {provider.get_guide_provider().tvg_id}: {e}")
                    continue
                if entries:
                    # session.query(GuideEntry).filter_by(channel=provider.get_guide_provider().tvg_id).delete()
                    max_datetime = max(entry.end for entry in entries)
                    min_datetime = min(entry.start for entry in entries)
                    q=session.query(GuideEntry).filter(
                        (GuideEntry.channel == provider.get_guide_provider().tvg_id)
                        &
                        (
                            (GuideEntry.end > min_datetime) | (GuideEntry.start < max_datetime)
                        )
                    )
                    logging.info(f"Deleting {q.count()} existing guide entries for provider {provider.get_guide_provider().tvg_id} since they overlap with new entries.")
                    q.delete(synchronize_session=False)
                    session.add_all(entries)
                logging.info(f"Processed provider {provider.get_guide_provider().tvg_id} with {len(entries)} entries.")
            else:
                logging.info(f"Skipping provider {provider.get_guide_provider().tvg_id} due to cooldown.")

        session.commit()

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
    main()

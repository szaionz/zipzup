from models import *
from channels import channel_providers
from sqlalchemy.orm import Session
import logging
from sqlalchemy import func
import datetime


GUIDE_COOLDOWN = datetime.timedelta(hours=12)

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    with Session(engine) as session:
        for provider in channel_providers:
            last_updated = session.query(func.max(GuideEntry.updated)).filter_by(channel=provider.get_guide_provider().tvg_id).first()[0]
            if not last_updated or datetime.datetime.now(UTC) - last_updated.replace(tzinfo=UTC) >= GUIDE_COOLDOWN:
                entries = provider.get_guide_provider().get_guide()
                if entries:
                    session.query(GuideEntry).filter_by(channel=provider.get_guide_provider().tvg_id).delete()
                    session.add_all(entries)
                logging.info(f"Processed provider {provider.get_guide_provider().tvg_id} with {len(entries)} entries.")
            else:
                logging.info(f"Skipping provider {provider.get_guide_provider().tvg_id} due to cooldown.")

        session.commit()
        
if __name__ == '__main__':
    main()
import time
import requests
from constants import UTC
from datetime import datetime, timedelta
import logging
import asyncio
import aiohttp

SYNC_BACK = timedelta(minutes=10)
SYNC_FORWARD = timedelta(minutes=10)

CATCHUP_FORWARD = timedelta(minutes=1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')




async def single_head(url, session):
    try:
        async with session.head(url=url) as response:
            return response.status
    except Exception as e:
        print("Unable to get url {} due to {}.".format(url, e.__class__))
        
async def bulk_head(urls):
    async with aiohttp.ClientSession() as session:
        return await asyncio.gather(*(single_head(url, session) for url in urls))

class KeshetStreamSimulator:
    def most_recent_media_sequence(self, dt: datetime):
        time_delta = dt - self.program_date_time
        seconds = time_delta.total_seconds()
        media_sequence_delta = seconds // self.target_duration
        return self.media_sequence + int(media_sequence_delta) - 1 
    
    def __init__(self, profile_manifest_url=None, rewind_time=timedelta(minutes=30), datetime_output_period=8, json=None):
        if json:
            self.profile_root = json['profile_root']
            self.media_sequence = json['media_sequence']
            self.program_date_time = datetime.fromisoformat(json['program_date_time']).astimezone(UTC)
            self.target_duration = json['target_duration']
            self.rewind_time = timedelta(seconds=json['rewind_time'])
            self.datetime_output_period = json['datetime_output_period']
            self.major_index_num_digits = json['major_index_num_digits']
            self.minor_index_num_digits = json['minor_index_num_digits']
            self.ts_name_stem = json['ts_name_stem']
            self.extension = json['extension']
            self.divisor = json['divisor']
            return
        text = requests.get(profile_manifest_url).text
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if line.startswith('#EXT-X-TARGETDURATION'):
                self.target_duration = float(line.split(':')[1])
                continue
            if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
                self.media_sequence = int(line.split(':')[1])
                continue
            if line.startswith('#EXT-X-PROGRAM-DATE-TIME'):
                self.program_date_time = UTC.localize(datetime.strptime(':'.join(line.split(':')[1:]), '%Y-%m-%dT%H:%M:%S.%fZ'))
                continue
            if line.startswith('https://'):
                example_url = line
                break
        # self.profile_root, unique = example_url.rsplit('/', 2)
        *profile_root, major_index, ts_name = example_url.split('/')
        self.profile_root = '/'.join(profile_root)
        # major_index, ts_name = unique.split('/')
        self.major_index_num_digits = len(major_index)
        major_index = int(major_index)
        self.ts_name_stem, ts_name_tail = ts_name.rsplit('_', 1)
        minor_index, self.extension = ts_name_tail.split('.')
        self.minor_index_num_digits = len(minor_index)
        minor_index = int(minor_index)
        self.divisor = (self.media_sequence-minor_index)//major_index
        self.rewind_time = rewind_time
        self.datetime_output_period = datetime_output_period
        self.sync_and_health_check()
        # old_media_sequence = self.media_sequence
        # now = datetime.now(UTC)
        # while requests.head(self.media_sequence_to_url(self.most_recent_media_sequence(now))).status_code==200:
        #     self.media_sequence += 1
        #     now = datetime.now(UTC)
        # self.media_sequence = self.most_recent_media_sequence(now)
        
        
        
    def media_sequence_to_url(self, media_sequence):
        major_index = (media_sequence-1) // self.divisor
        minor_index = (media_sequence-1) % self.divisor+1
        return f"{self.profile_root}/{major_index:0{self.major_index_num_digits}d}/{self.ts_name_stem}_{minor_index:0{self.minor_index_num_digits}}.{self.extension}"
    

    
    def media_sequence_to_datetime(self, media_sequence):
        return self.program_date_time + (media_sequence - self.media_sequence) * self.target_duration * timedelta(seconds=1)
    
    def generate_playlist(self):
        now = datetime.now(UTC)
        start_media_sequence = self.most_recent_media_sequence(now - self.rewind_time)
        # start_datetime = self.media_sequence_to_datetime(start_media_sequence)
        lines = [
            '#EXTM3U',
            '#EXT-X-VERSION:3',
            f'#EXT-X-TARGETDURATION:{self.target_duration}',
            f'#EXT-X-MEDIA-SEQUENCE:{start_media_sequence}',
             '#EXT-X-DISCONTINUITY-SEQUENCE:1',
            # f'#EXT-X-PROGRAM-DATE-TIME:{start_datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")}'
        ]
        first_after_offset = int((now-self.program_date_time)/ timedelta(seconds=self.target_duration)-(start_media_sequence - self.media_sequence)+1)
        urls = [self.media_sequence_to_url(start_media_sequence + offset) for offset in range(first_after_offset, CATCHUP_FORWARD//timedelta(seconds=self.target_duration) + first_after_offset + 1)]
        status_codes = list(asyncio.run(bulk_head(urls)))
        offset = 0
        def should_get_extra_ts():
            a = status_codes.pop(0)
            if a == 200:
                logging.info(f"Adding extra TS segment")
                return True
            return False
        while self.media_sequence_to_datetime(start_media_sequence + offset) <= now or should_get_extra_ts():
            if offset % self.datetime_output_period == 0:
                lines.append(f'#EXT-X-PROGRAM-DATE-TIME:{(self.media_sequence_to_datetime(start_media_sequence + offset)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}')
            lines.append(f'#EXTINF:{self.target_duration:.12f},')
            lines.append(self.media_sequence_to_url(start_media_sequence + offset))
            offset += 1
        return '\n'.join(lines) + '\n'
    
    def sync_and_health_check(self):
        now = datetime.now(UTC)
        now_media_sequence = self.most_recent_media_sequence(now)
        offsets = range(-SYNC_BACK//timedelta(seconds=self.target_duration),
                                                                                             SYNC_FORWARD//timedelta(seconds=self.target_duration) + 1)
          
        urls = [self.media_sequence_to_url(now_media_sequence + offset) for offset in offsets]
        status_codes = asyncio.run(bulk_head(urls))
        if all(status!=200 for status in status_codes):
            logging.error(f"Failed to sync: no valid media sequences found in the range {now_media_sequence-SYNC_BACK//timedelta(seconds=self.target_duration)} to {now_media_sequence + SYNC_FORWARD//timedelta(seconds=self.target_duration)}.")
            logging.error(f"Status codes: {status_codes}")
            logging.error(f"URLs: {urls}")
            return False
        last_ts = max(offsets, key=lambda offset: (status_codes[offsets.index(offset)] == 200, offset)) + now_media_sequence 
        old_dt_of_last_ts_plus_one = self.media_sequence_to_datetime(last_ts+1)
        self.media_sequence = last_ts+1
        self.program_date_time = now
        while requests.head(self.media_sequence_to_url(self.most_recent_media_sequence(datetime.now(UTC)))).status_code!=200:
            self.program_date_time = datetime.now(UTC)
            time.sleep(0.1)
        self.program_date_time+= timedelta(seconds=self.target_duration)
        logging.info(f"Sync complete: fixed drift of {(self.program_date_time - old_dt_of_last_ts_plus_one).total_seconds()} seconds.")
        return True

    def to_json(self):
        return {
            'profile_root': self.profile_root,
            'media_sequence': self.media_sequence,
            'program_date_time': self.program_date_time.isoformat(),
            'target_duration': self.target_duration,
            'rewind_time': self.rewind_time.total_seconds(),
            'datetime_output_period': self.datetime_output_period,
            'major_index_num_digits': self.major_index_num_digits,
            'minor_index_num_digits': self.minor_index_num_digits,
            'ts_name_stem': self.ts_name_stem,
            'extension': self.extension,
            'divisor': self.divisor,
        }
            
        
            

            
    

# def main():
#     keshet_web_url="https://www.mako.co.il/mako-vod-live-tv/"
#     with webdriver.Remote(command_executor='http://selenium:4444/wd/hub', options=webdriver.ChromeOptions()) as driver:
#         stream = get_stream(keshet_web_url, driver)
#     stream_root = stream.rsplit('/', 1)[0]
#     profile = requests.get(stream).text.splitlines()[-1]
#     profile = stream_root + '/' + profile
#     simulator = KeshetStreamSimulator(profile)
#     pass

# if __name__ == "__main__":
#     main()
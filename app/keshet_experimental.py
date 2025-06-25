import time
import requests
from constants import UTC
from datetime import datetime, timedelta
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


TIMESHIFT_BACK = timedelta(seconds=20)
class KeshetStreamSimulator:
    def most_recent_media_sequence(self, dt: datetime):
        time_delta = dt - self.program_date_time
        seconds = time_delta.total_seconds()
        media_sequence_delta = seconds // self.target_duration
        return self.media_sequence + int(media_sequence_delta) - 1 
    
    def __init__(self, profile_manifest_url, rewind_time=timedelta(minutes=30), datetime_output_period=8):
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
        old_media_sequence = self.media_sequence
        now = datetime.now(UTC)
        while requests.head(self.media_sequence_to_url(self.most_recent_media_sequence(now))).status_code==200:
            self.media_sequence += 1
            now = datetime.now(UTC)
        self.media_sequence = self.most_recent_media_sequence(now)
        self.program_date_time = now
        while requests.head(self.media_sequence_to_url(self.most_recent_media_sequence(datetime.now(UTC)))).status_code!=200:
            self.program_date_time = datetime.now(UTC)
            time.sleep(0.1)
        logging.info(f'Pushed media sequence by {self.media_sequence - old_media_sequence} to {self.media_sequence} based on current time.')
        
        
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
        offset = 0
        while self.media_sequence_to_datetime(start_media_sequence + offset) <= now:
            if offset % self.datetime_output_period == 0:
                lines.append(f'#EXT-X-PROGRAM-DATE-TIME:{(self.media_sequence_to_datetime(start_media_sequence + offset)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}')
            lines.append(f'#EXTINF:{self.target_duration:.12f},')
            lines.append(self.media_sequence_to_url(start_media_sequence + offset))
            offset += 1
        return '\n'.join(lines) + '\n'
    
    def health_check(self):
        now = datetime.now(UTC)
        now_media_sequence = self.most_recent_media_sequence(now)
        url = self.media_sequence_to_url(now_media_sequence)
        try:
            response = requests.head(url, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
            

            
    

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
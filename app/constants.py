import pytz
import os

LOCAL_TZ = pytz.timezone('Asia/Jerusalem')
UTC = pytz.utc
BASE_URL = os.environ.get('BASE_URL')


FROM python:3.13-alpine3.21

RUN adduser -D abc && mkdir /app && chown abc /app && mkdir -p /etc/crontabs && echo '*/10 * * * * python3 /app/epg.py' > /etc/crontabs/abc
RUN crontab -u abc /etc/crontabs/abc

USER abc 

WORKDIR /app
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY app.py epg.py tuner.m3u /app/

ENTRYPOINT ["python3", "-m", "flask", "run", "-h", "0.0.0.0"]

LABEL version="0.1.0"
LABEL description="M3U tuner for Israeli IPTV channels with guide"
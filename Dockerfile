

FROM python:3.11-alpine

RUN adduser -D abc && mkdir /app && chown abc /app && mkdir -p /etc/crontabs && echo '*/10 * * * * python3 /app/epg_worker.py' > /etc/crontabs/abc
RUN crontab -u abc /etc/crontabs/abc

USER abc 

WORKDIR /app
COPY app/requirements.txt /app/
RUN pip install --no-cache --upgrade pip setuptools && pip install -r requirements.txt
COPY app /app

ENTRYPOINT ["python3", "-m", "flask", "run", "-h", "0.0.0.0"]

ENV DEBUG=false
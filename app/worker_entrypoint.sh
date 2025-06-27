#!/bin/sh
su abc -c 'python3 /app/epg_worker.py'
su abc -c 'python3 /app/keshet_worker.py'
crond -f

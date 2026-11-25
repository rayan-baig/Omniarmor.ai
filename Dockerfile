FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMNIARMOR_ENV=production \
    DATABASE_PATH=/data/omniarmor.db \
    BACKUP_DIR=/data/backups \
    PORT=8000 \
    WEB_CONCURRENCY=1 \
    WEB_THREADS=8

WORKDIR /srv/omniarmor
RUN useradd --create-home --uid 10001 omniarmor && mkdir -p /data && chown omniarmor /data
# constraints.txt pins every package, including the ones requirements.txt
# pulls in, so the image installs exactly what CI tested.
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
COPY omni_armor_platform.py wsgi.py ./
COPY omni_armor_rules ./omni_armor_rules
COPY omniarmor_app ./omniarmor_app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Starts as root only so the entrypoint can give a root-owned disk to
# `omniarmor`, then drops to that user with setpriv before the app starts.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8000'), timeout=4).status == 200 else 1)"
# One process with threads keeps memory low (fits a free or smallest VM).
# Raise WEB_CONCURRENCY only if one process can't keep up.
# With threads, gunicorn's --timeout only restarts a worker that stopped
# responding or took over 60 s to start (schema upgrades run at start-up:
# about 2 s for a million audit rows); it never cuts a page off. The slowest
# page, a 500,000-row audit CSV, streams its first bytes at once.
CMD ["sh", "-c", "exec gunicorn --workers ${WEB_CONCURRENCY} --threads ${WEB_THREADS} --timeout 60 --bind 0.0.0.0:${PORT} --access-logfile - --logger-class omniarmor_app.access_log.RedactingLogger wsgi:app"]

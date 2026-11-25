FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5000 \
    HOST=0.0.0.0 \
    DATA_DIR=/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py config.py ./
COPY core ./core
COPY utils ./utils
COPY crawler ./crawler

RUN useradd --system --uid 10001 --home /nonexistent --shell /usr/sbin/nologin appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data

USER appuser
VOLUME ["/data"]
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=3).read()"]

CMD ["sh", "-c", "exec gunicorn --workers 1 --threads 4 --bind ${HOST}:${PORT} --timeout 120 --graceful-timeout 30 --access-logfile - --error-logfile - app:app"]

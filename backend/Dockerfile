FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DEBUG=False \
    UPLOAD_DIR=/app/uploads \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Fail the build (not the first request) if a native dependency cannot load on this image.
RUN python -c "import cv2, shapely, PIL, pypdfium2, psycopg2, fastapi, sqlalchemy; print('dependencies OK')"

COPY app ./app

# Uploaded plans live here; mount a persistent volume at this path on the hosting platform.
RUN mkdir -p /app/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'), timeout=4)" || exit 1

# Hosting platforms inject PORT; fall back to 8000 for local `docker run`.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 시스템 의존성(필요 시 추가)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -U pip && pip install -r requirements.txt

COPY . .

ENV DJANGO_SETTINGS_MODULE=config.settings
# 엔트리포인트에서 migrate/collectstatic 실행
ENTRYPOINT ["bash", "-c", "python manage.py migrate --noinput && \
  python manage.py collectstatic --noinput && \
  gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-4} --threads ${GUNICORN_THREADS:-2}"]

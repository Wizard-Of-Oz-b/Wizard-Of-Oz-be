#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# venv
if [ -d ".venv" ]; then source .venv/bin/activate; fi
# 로컬일 때 .env 로드
if [ -f ".env" ]; then set -a; source .env; set +a; fi

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings}"
export PYTHONPATH="$PROJECT_DIR"

cmd="${1:-dev}"
BIND="${BIND:-0.0.0.0:8000}"
WORKERS="${GUNICORN_WORKERS:-4}"
THREADS="${GUNICORN_THREADS:-2}"

case "$cmd" in
  dev)
    python manage.py migrate --noinput
    python manage.py runserver 0.0.0.0:8000
    ;;
  dev-uvicorn)
    python manage.py migrate --noinput
    uvicorn config.asgi:application --reload --host 0.0.0.0 --port 8000
    ;;
  prod-uvicorn)
    python manage.py migrate --noinput
    [ "${RUN_COLLECTSTATIC:-1}" = "1" ] && python manage.py collectstatic --noinput
    python manage.py check --deploy || true
    uvicorn config.asgi:application --host 0.0.0.0 --port "${BIND##*:}" --workers "${WORKERS}" --timeout-keep-alive 5
    ;;
  prod-gunicorn)
    python manage.py migrate --noinput
    [ "${RUN_COLLECTSTATIC:-1}" = "1" ] && python manage.py collectstatic --noinput
    python manage.py check --deploy || true
    gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker \
      --bind "${BIND}" --workers "${WORKERS}" --threads "${THREADS}" \
      --log-level "${GUNICORN_LOG_LEVEL:-info}"
    ;;
  *)
    echo "Usage: $0 {dev|dev-uvicorn|prod-uvicorn|prod-gunicorn}"
    exit 2
    ;;
esac

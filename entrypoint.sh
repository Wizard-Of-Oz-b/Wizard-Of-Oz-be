#!/usr/bin/env bash
set -euo pipefail

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn -c gunicorn.conf.py config.asgi:application

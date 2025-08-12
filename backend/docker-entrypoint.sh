#!/usr/bin/env sh
set -e

python manage.py migrate --noinput

# Start Celery worker in background
celery -A resumeai worker -l info &

# Start Django server
python manage.py runserver 0.0.0.0:8000

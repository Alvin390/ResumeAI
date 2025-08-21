#!/usr/bin/env sh
set -e

python manage.py migrate --noinput

# Optionally start Celery worker in background
# Enable by setting CELERY_ENABLED=true in the environment
if [ "${CELERY_ENABLED}" = "true" ] || [ "${CELERY_ENABLED}" = "1" ]; then
  # Default to low concurrency on small instances
  : "${CELERY_CONCURRENCY:=1}"
  # Use a low-memory pool by default; override with CELERY_POOL
  : "${CELERY_POOL:=solo}"
  echo "Starting Celery worker (concurrency=${CELERY_CONCURRENCY}, pool=${CELERY_POOL})..."
  celery -A resumeai worker -l info --pool="${CELERY_POOL}" --concurrency="${CELERY_CONCURRENCY}" &
else
  echo "CELERY_ENABLED is not set. Skipping Celery worker startup."
fi

# Start Django server
PORT="${PORT:-8000}"
python manage.py runserver 0.0.0.0:"${PORT}"

#!/bin/sh

set -e  # Exit immediately on error

echo "Checking PostgreSQL status at $POSTGRES_HOST:$POSTGRES_PORT..."

MAX_TRIES=30
TRIES=0

#until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" > /dev/null 2>&1; do
#  echo "Waiting for PostgreSQL to be ready..."
#  sleep 2
#done

while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
  TRIES=$((TRIES+1))
  if [ $TRIES -ge $MAX_TRIES ]; then
    echo "PostgreSQL is still not available after $MAX_TRIES attempts. Exiting."
    exit 1
  fi
  echo "Waiting for PostgreSQL... ($TRIES/$MAX_TRIES)"
  sleep 2
done

echo "PostgreSQL is up - applying migrations..."
python manage.py migrate --noinput

echo "Running 'get_crops' command..."
python manage.py get_crops

echo "Collecting static files..."
python manage.py collectstatic --noinput


if [ "$RUNNING_IN_DOCKER" = "true" ]; then
  echo "Starting Gunicorn..."
  exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4 --threads 4
else
    echo "Running in development mode..."
    exec python manage.py runserver 0.0.0.0:8000
fi

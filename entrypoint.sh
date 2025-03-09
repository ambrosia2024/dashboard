#!/bin/sh

# Check if we are running inside Docker
if [ "$RUNNING_IN_DOCKER" = "true" ]; then
    echo "Checking PostgreSQL status..."

    while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
      echo "Waiting for PostgreSQL..."
      sleep 2
    done

    echo "PostgreSQL is up - applying migrations..."
    python manage.py migrate --noinput

    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    echo "Starting Gunicorn..."
    exec gunicorn config.wsgi:application --bind 0.0.0.0:8000
else
    echo "Running in development mode..."
    exec python manage.py runserver 0.0.0.0:8000
fi

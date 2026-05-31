#!/bin/bash
set -e

# Wait for database directory to be available
while [ ! -d "/data" ]; do
    echo "Waiting for /data directory to be available..."
    sleep 1
done

# Run database migrations
echo "Running database migrations..."
uv run python manage.py migrate

# Create superuser if it doesn't exist (optional)
echo "Checking for superuser..."
uv run python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print('Creating superuser...')
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Superuser created: admin/admin123')
else:
    print('Superuser already exists')
" || echo "Superuser creation skipped"

# Start Huey consumer in the background
echo "Starting Huey consumer..."
uv run huey_consumer.py rag.huey.huey --workers 2 --logfile - &
HUEY_PID=$!
echo "Huey consumer started (PID: $HUEY_PID)"

# Start the application
echo "Starting LLTeacher application..."
exec "$@"

#!/bin/sh

# Exit if any command fails
set -e

# Set correct permissions for the logs directory at runtime.
# This ensures the 'nobody' user can write to the volume.
chown -R nobody:nogroup /app/logs

# Run Alembic migrations
echo "Running database migrations..."
if ! alembic upgrade head; then
  echo "⚠️ Warning: Alembic migration failed. Continuing without shutdown."
fi

# Use gosu to drop from root to the 'nobody' user and run the main command
exec gosu nobody "$@"


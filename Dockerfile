FROM python:3.12-slim

WORKDIR /app

# Define build-time arguments
ARG ARG_CLERK_JWT_PUBLIC_KEY
ARG ARG_CLERK_API_KEY
ARG ARG_CLERK_API_URL
ARG ARG_DEBUG_LOGGING=false

# Set runtime environment variables from build-time arguments
# WARNING: These values will be baked into the image. For sensitive data, prefer runtime injection.
ENV CLERK_JWT_PUBLIC_KEY=${ARG_CLERK_JWT_PUBLIC_KEY}
ENV CLERK_API_KEY=${ARG_CLERK_API_KEY}
# Example with a default value if ARG is not set for CLERK_API_URL
ENV CLERK_API_URL=${ARG_CLERK_API_URL:-https://api.clerk.dev/v1}
ENV FORGE_DEBUG_LOGGING=${ARG_DEBUG_LOGGING}

# Database connection optimization environment variables
# These settings optimize for PostgreSQL connection limits
ENV DB_POOL_SIZE=3
ENV DB_MAX_OVERFLOW=2
ENV DB_POOL_TIMEOUT=30
ENV DB_POOL_RECYCLE=1800
ENV DB_POOL_PRE_PING=true

# Reduced worker count to manage database connections
# With 5 workers: max 60 connections (5 × 3 × 2 engines + 5 × 2 × 2 overflow = 50 connections)
ENV WORKERS=5

# Install system dependencies including PostgreSQL client and gosu for user privilege management
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/logs && \
    chown -R nobody:nogroup /app/logs && \
    chmod -R 777 /app/logs

# Copy project files
COPY . .

# Install dependencies using pip
RUN pip install -e .

# Switch to non-root user for security
USER nobody

# Expose port
EXPOSE 8000

# Use environment variable for workers count and optimize for database connections
CMD ["sh", "-c", "gunicorn app.main:app -k uvicorn.workers.UvicornWorker --workers ${WORKERS:-5} --bind 0.0.0.0:8000 --timeout 120 --max-requests 1000 --max-requests-jitter 100"]

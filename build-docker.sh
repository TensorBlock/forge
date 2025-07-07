#!/bin/bash
set -e

# Configuration
IMAGE_NAME="tensorblockai/forge"
VERSION=$(date +"%Y%m%d-%H%M%S")
LATEST_TAG="latest"

# Check if DOCKER_USERNAME and DOCKER_PASSWORD environment variables are set
if [ -z "$DOCKER_USERNAME" ] || [ -z "$DOCKER_PASSWORD" ]; then
    echo "DOCKER_USERNAME and DOCKER_PASSWORD environment variables must be set" >&2
    echo "Run the script with:" >&2
    echo "DOCKER_USERNAME=yourusername DOCKER_PASSWORD=yourpassword ./build-docker.sh" >&2
    exit 1
fi

# Check for Clerk environment variables
if [ -z "$CLERK_API_KEY" ] || [ -z "$CLERK_JWT_PUBLIC_KEY" ]; then
    echo "Error: CLERK_API_KEY and CLERK_JWT_PUBLIC_KEY environment variables must be set." >&2
    echo "Please export them before running this script." >&2
    echo "CLERK_API_URL will default if not set." >&2
    exit 1
fi

# Optional debug logging flag
DEBUG_LOGGING=${DEBUG_LOGGING:-false}

# Login to Docker Hub
echo "Logging in to Docker Hub..."
echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin

# Build the Docker image
echo "Building Docker image: $IMAGE_NAME:$VERSION..."
docker build \
  --build-arg ARG_CLERK_JWT_PUBLIC_KEY="$CLERK_JWT_PUBLIC_KEY" \
  --build-arg ARG_CLERK_API_KEY="$CLERK_API_KEY" \
  --build-arg ARG_CLERK_API_URL="${CLERK_API_URL:-https://api.clerk.dev/v1}" \
  --build-arg ARG_DEBUG_LOGGING="$DEBUG_LOGGING" \
  -t "$IMAGE_NAME:$VERSION" -t "$IMAGE_NAME:$LATEST_TAG" .

# Push the Docker image to Docker Hub
echo "Pushing Docker image to Docker Hub..."
docker push "$IMAGE_NAME:$VERSION"
docker push "$IMAGE_NAME:$LATEST_TAG"

echo "Image successfully built and pushed to Docker Hub:"
echo "  $IMAGE_NAME:$VERSION"
echo "  $IMAGE_NAME:$LATEST_TAG"
echo ""
echo "To run the image, use:"
echo "docker run -p 8000:8000 \\"
echo "  -e PORT=8000 \\"
echo "  -e DATABASE_URL=postgresql://forge:forge@db:5432/forge \\"
echo "  -e FORGE_DEBUG_LOGGING=false \\"
echo "  -v $(pwd)/logs:/app/logs \\"
echo "  --network=forge-network \\"
echo "  $IMAGE_NAME:$LATEST_TAG"
echo ""
echo "Or use docker-compose:"
echo "docker-compose up -d"

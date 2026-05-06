#!/bin/sh
set -eu

# Build and push the Ambrosia dashboard image to a container registry.
#
# Usage:
#   ./scripts/build_and_push.sh          # tag = latest
#   ./scripts/build_and_push.sh v1.2.3   # tag = v1.2.3
#
# Optional environment overrides:
#   REGISTRY=ghcr.io/ambrosia2024
#   IMAGE_NAME=ghcr.io/ambrosia2024/ambrosia-dashboard
#   PLATFORM=linux/amd64
#   DOCKERFILE=Dockerfile
#   CONTEXT=.
#
# Prerequisites:
#   docker login ghcr.io -u <github-user> -p <PAT-with-write:packages>
#
# Notes:
# - The image is built explicitly for linux/amd64 by default so it can run on
#   common x86_64 servers regardless of the local machine architecture.
# - This script builds directly from the Dockerfile instead of docker compose so
#   the pushed image tag is always explicit.

REGISTRY="${REGISTRY:-ghcr.io/ambrosia2024}"
IMAGE_NAME="${IMAGE_NAME:-${REGISTRY}/ambrosia-dashboard}"
TAG="${1:-latest}"
PLATFORM="${PLATFORM:-linux/amd64}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
CONTEXT="${CONTEXT:-.}"

FULL_IMAGE="${IMAGE_NAME}:${TAG}"

echo "Building image: ${FULL_IMAGE} (${PLATFORM})"
docker build --platform "${PLATFORM}" -f "${DOCKERFILE}" -t "${FULL_IMAGE}" "${CONTEXT}"

echo "Pushing image: ${FULL_IMAGE}"
docker push "${FULL_IMAGE}"

echo "Done."
echo "Image: ${FULL_IMAGE}"

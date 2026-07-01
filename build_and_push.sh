#!/bin/bash
# Build for linux/amd64 (OpenShift, x86) and linux/arm64 (Apple Silicon, ARM)
# and push to Quay.io as a multi-platform image.
# Requires: Docker with buildx (recommended) or Podman with buildah.

set -e
IMAGE="quay.io/vraste/indian-bank-pnb-kpi:latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
PLATFORMS="linux/amd64,linux/arm64"

# ---- Docker buildx (multi-arch in one go) ----
if command -v docker &>/dev/null && docker buildx version &>/dev/null; then
  echo "Using Docker buildx for multi-platform: $PLATFORMS"
  echo "Log in to Quay if needed: docker login quay.io"
  docker buildx create --use --name indian-bank-multi 2>/dev/null || docker buildx use indian-bank-multi 2>/dev/null || true
  APP_BUILD="${APP_BUILD:-$(date +%s)}"
  echo "Building with APP_BUILD=$APP_BUILD"
  docker buildx build --platform "$PLATFORMS" --build-arg APP_BUILD="$APP_BUILD" -t "$IMAGE" --push .
  echo "Done. Image $IMAGE (amd64 + arm64)"
  exit 0
fi

# ---- Podman: build each platform, push, then manifest ----
if command -v podman &>/dev/null; then
  echo "Using Podman: building amd64 and arm64..."
  podman login quay.io -u vraste -p 'Jobchange@123456789' 2>/dev/null || true
  podman build --platform linux/amd64 -t "${IMAGE}-amd64" .
  podman build --platform linux/arm64 -t "${IMAGE}-arm64" .
  podman push "${IMAGE}-amd64"
  podman push "${IMAGE}-arm64"
  podman manifest create "$IMAGE" "${IMAGE}-amd64" "${IMAGE}-arm64"
  podman manifest push "$IMAGE" "docker://$IMAGE"
  echo "Done. Image $IMAGE (amd64 + arm64)"
  exit 0
fi

echo "Need Docker (with buildx) or Podman. Falling back to single-arch amd64 with docker..."
docker build --platform linux/amd64 -t "$IMAGE" .
echo "Log in to Quay and push: docker push $IMAGE"
exit 1

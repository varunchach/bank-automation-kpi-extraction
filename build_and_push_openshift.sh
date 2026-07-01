#!/bin/bash
# Build OpenShift image (fast Docling: tables only, no OCR) and push to Quay.
# Use this image in OpenShift to avoid long runs and timeouts.
set -e
IMAGE_OPENSHIFT="quay.io/vraste/indian-bank-pnb-kpi:openshift"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
APP_BUILD="${APP_BUILD:-$(date +%s)}"
echo "Building OpenShift image (fast Docling) with APP_BUILD=$APP_BUILD"

if command -v docker &>/dev/null && docker buildx version &>/dev/null; then
  docker buildx create --use --name indian-bank-multi 2>/dev/null || docker buildx use indian-bank-multi 2>/dev/null || true
  docker buildx build --platform linux/amd64 --build-arg APP_BUILD="$APP_BUILD" -f Dockerfile.openshift -t "$IMAGE_OPENSHIFT" --push .
  echo "Done. Image $IMAGE_OPENSHIFT"
  exit 0
fi

if command -v podman &>/dev/null; then
  podman build --platform linux/amd64 --build-arg APP_BUILD="$APP_BUILD" -f Dockerfile.openshift -t "$IMAGE_OPENSHIFT" .
  podman push "$IMAGE_OPENSHIFT"
  echo "Done. Image $IMAGE_OPENSHIFT"
  exit 0
fi

echo "Need Docker buildx or Podman."
exit 1

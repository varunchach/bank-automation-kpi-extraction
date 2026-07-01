#!/bin/bash
# Build OpenShift GPU image (PyTorch CUDA 12.1) and push to Quay.
# Use with openshift/deployment_openshift_gpu.yaml on a cluster with nvidia.com/gpu.
set -e
IMAGE="quay.io/vraste/indian-bank-pnb-kpi:openshift-gpu"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
APP_BUILD="${APP_BUILD:-$(date +%s)}"
echo "Building OpenShift GPU image (PyTorch cu121) with APP_BUILD=$APP_BUILD"

if command -v docker &>/dev/null && docker buildx version &>/dev/null; then
  docker buildx create --use --name indian-bank-multi 2>/dev/null || docker buildx use indian-bank-multi 2>/dev/null || true
  docker buildx build --platform linux/amd64 --build-arg APP_BUILD="$APP_BUILD" -f Dockerfile.openshift.gpu -t "$IMAGE" --push .
  echo "Done. Image $IMAGE"
  exit 0
fi

if command -v podman &>/dev/null; then
  podman build --platform linux/amd64 --build-arg APP_BUILD="$APP_BUILD" -f Dockerfile.openshift.gpu -t "$IMAGE" .
  podman push "$IMAGE"
  echo "Done. Image $IMAGE"
  exit 0
fi

echo "Need Docker buildx or Podman."
exit 1

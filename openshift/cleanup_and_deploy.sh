#!/bin/bash
# Free resources and redeploy: delete project then recreate and apply.
# Use when pods are stuck Pending (Insufficient CPU) or you want a clean slate.
set -e
PROJECT=indian-bank-kpi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deleting project $PROJECT (frees all resources)..."
oc delete project $PROJECT --ignore-not-found --wait=false 2>/dev/null || true
echo "Waiting for project to be gone..."
sleep 15
while oc get project $PROJECT 2>/dev/null; do sleep 5; done
echo "Creating project and deploying..."
oc new-project $PROJECT 2>/dev/null || true
oc apply -f "$SCRIPT_DIR/deployment.yaml" -n $PROJECT
echo "Waiting for rollout..."
oc rollout status deployment/indian-bank-pnb-kpi -n $PROJECT --timeout=120s
echo "Done. URL: https://$(oc get route indian-bank-pnb-kpi -n $PROJECT -o jsonpath='{.spec.host}')"

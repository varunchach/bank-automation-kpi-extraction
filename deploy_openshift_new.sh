#!/bin/bash
# Deploy to any OpenShift cluster using env vars. For a new instance, set OCP_SERVER and OCP_TOKEN.
# Usage:
#   export OCP_SERVER="https://api.cluster-XXX....:6443"
#   export OCP_TOKEN="sha256~..."
#   ./deploy_openshift_new.sh [cpu|gpu]   # default: cpu
set -e
MODE="${1:-cpu}"
if [[ -z "$OCP_SERVER" || -z "$OCP_TOKEN" ]]; then
  echo "Set OCP_SERVER and OCP_TOKEN for your cluster, then run: $0 [cpu|gpu]"
  echo "Example: export OCP_SERVER=https://api.cluster-xxx:6443 OCP_TOKEN=sha256~..."
  exit 1
fi
oc login --token="$OCP_TOKEN" --server="$OCP_SERVER" --insecure-skip-tls-verify
oc new-project indian-bank-kpi 2>/dev/null || oc project indian-bank-kpi
if [[ "$MODE" == "gpu" ]]; then
  oc apply -f openshift/deployment_openshift_gpu.yaml
else
  oc apply -f openshift/deployment_openshift.yaml
  oc set resources deployment/indian-bank-pnb-kpi --limits=cpu=6,memory=8Gi --requests=cpu=2,memory=2Gi 2>/dev/null || true
fi
echo "Waiting for deployment..."
oc rollout status deployment/indian-bank-pnb-kpi --timeout=300s
ROUTE=$(oc get route indian-bank-pnb-kpi -o jsonpath='{.spec.host}' 2>/dev/null || true)
if [[ -n "$ROUTE" ]]; then
  echo "App available at: https://$ROUTE"
else
  echo "Get route: oc get route indian-bank-pnb-kpi"
fi

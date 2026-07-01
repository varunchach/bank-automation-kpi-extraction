# Deploy to OpenShift

## Prerequisites
- Podman (or Docker) with `podman machine start` on Mac
- `oc` CLI installed

## 1. Build and Push Image (linux/amd64)

```bash
# Ensure podman machine is running
podman machine start

# Build for amd64 (required for OpenShift on Mac)
./build_and_push.sh
```

Or manually:
```bash
podman build --platform linux/amd64 -t quay.io/vraste/indian-bank-pnb-kpi:latest .
podman login quay.io -u vraste
podman push quay.io/vraste/indian-bank-pnb-kpi:latest
```

## 2. Deploy to OpenShift

```bash
./deploy_openshift.sh
```

Or manually:
```bash
oc login --token=sha256~WIDp1k9_zC0Fstw4eiXWq0jPSsiTUVjmY3LCXB3ENnE --server=https://api.ocp.5gqpx.sandbox203.opentlc.com:6443
oc new-project indian-bank-kpi 2>/dev/null || oc project indian-bank-kpi
oc apply -f openshift/deployment.yaml
oc rollout status deployment/indian-bank-pnb-kpi --timeout=300s
oc get route indian-bank-pnb-kpi
```

## 3. Access the App

After deployment, get the route URL:
```bash
oc get route indian-bank-pnb-kpi -o jsonpath='{.spec.host}'
```

Open `https://<route-host>` in a browser.

## Features Deployed
- KPI extraction (IB & PNB)
- RAG with Milvus Lite (milvus.db) + sentence-transformers
- Entities passed to LLM as JSON (kpis + retrieved_chunks)
- Web search (Tavily) & Yahoo Finance tools
- Template report format, drops None rows

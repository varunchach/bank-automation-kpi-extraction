# Deploy to OpenShift

See **[RUNBOOK.md](RUNBOOK.md)** for the current deploy flow. This file covers image build only.

## Prerequisites

- Podman or Docker
- `oc` CLI logged into your cluster
- Quay.io (or your registry) access if pushing images

## 1. Build and push image

**Full Docling + OCR (local parity):**

```bash
./build_and_push.sh
```

**Fast mode (OpenShift CPU — tables only, recommended for cluster timeout):**

```bash
./build_and_push_openshift.sh
```

**GPU mode:**

```bash
./build_and_push_openshift_gpu.sh
```

Default image: `quay.io/vraste/indian-bank-pnb-kpi` with tags `:latest`, `:openshift`, `:openshift-gpu`.  
Update the image name in build scripts if using your own registry.

Manual build example:

```bash
docker build --platform linux/amd64 -t quay.io/YOUR_USER/bank-kpi-analyst:latest .
docker push quay.io/YOUR_USER/bank-kpi-analyst:latest
```

## 2. Deploy

```bash
export OCP_SERVER="https://api.YOUR_CLUSTER:6443"
export OCP_TOKEN="sha256~YOUR_TOKEN"
./deploy_openshift_new.sh cpu    # or: gpu
```

## 3. Get app URL

```bash
oc get route indian-bank-pnb-kpi -o jsonpath='{.spec.host}'
```

Open `https://<route-host>` in a browser.

## What gets deployed

- Multi-bank KPI extraction (IB, PNB, HDFC)
- Streamlit UI with BSE URL download
- RAG (Milvus Lite) + optional LLM chat
- Tavily web search + Yahoo Finance tools

Configure LLM/Tavily via environment variables on the deployment if needed.

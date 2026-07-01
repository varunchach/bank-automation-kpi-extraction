# OpenShift deployment

**Quick start:** See **[../RUNBOOK.md](../RUNBOOK.md)** for running locally and deploying to any OpenShift instance (CPU or GPU).

## Why it works on Mac but can fail or behave differently on OCP

| Factor | Mac | OCP (container) |
|--------|-----|------------------|
| **CPU** | **All cores** (e.g. 8–10 on Apple Silicon/Intel). No limit. | **Capped at 2 cores** (request 500m, limit 2). Cluster had no room for 4 cores. |
| **Speed** | Same pipeline runs in **~5 minutes** because Docling + OCR + RAG use many cores. | Same workload on 2 cores takes **10–20+ minutes** (CPU-bound). |
| **LLM API** | Your Mac can reach `LLM_BASE_URL` (e.g. on VPN/corporate network). | The pod may **not** be able to reach that URL (e.g. `*.rhoai.rh-aiservices-bu.com` is internal). Chat then fails or falls back to rule-based answers. |
| **PDF downloads** | Same network as BSE; downloads usually succeed. | BSE might block or throttle requests from cloud IPs; you can get 403 or timeouts. |
| **Memory** | No hard limit. | Pod has a limit (e.g. 6Gi); heavy runs can hit OOMKilled. |
| **Writable paths** | Any path is writable. | Only `/tmp` is writable; app uses `/tmp/kpi_app`. |

## What to do on OCP

1. **LLM reachable from the cluster**  
   If your default `LLM_BASE_URL` is only reachable from your Mac (e.g. VPN), set an endpoint that the pod can reach. In `deployment.yaml` (or via ConfigMap/Secret), set:
   - `LLM_BASE_URL` – e.g. an OpenAI-compatible API URL that is reachable from OCP (same cluster, or a public URL).
   - `LLM_API_KEY` – API key for that endpoint (if required).

2. **PDFs**  
   If BSE blocks the pod, use different PDF URLs (e.g. internal copy or a proxy) and paste them in the app’s URL inputs.

3. **Slowness**  
   Report generation is CPU-bound (docling + OCR + RAG). On a small pod it will take several minutes. Use the progress messages in the UI; consider increasing CPU/memory if the cluster allows.

4. **OOM**  
   If the pod is OOMKilled, increase the deployment’s memory limit (and request) so the pod has enough headroom for extraction + RAG.

## Manifests

| File | Image | Use |
|------|--------|-----|
| `deployment.yaml` | `:latest` | Full Docling + OCR (CPU) |
| `deployment_openshift.yaml` | `:openshift` | Fast Docling, no OCR (CPU) |
| `deployment_openshift_gpu.yaml` | `:openshift-gpu` | Fast Docling on GPU (`nvidia.com/gpu`) |

For a **new cluster**, use `../deploy_openshift_new.sh` with `OCP_SERVER` and `OCP_TOKEN` set; see [../RUNBOOK.md](../RUNBOOK.md).

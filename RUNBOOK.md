# Multi-Bank KPI Analyst — Runbook

Deploy and run the KPI extraction Streamlit app **locally** or on **OpenShift**.

---

## 1. Run locally (Mac / Linux)

**Prerequisites:** Python 3.11+, pip. Apple Silicon can use MPS where PyTorch supports it.

```bash
git clone https://github.com/varunchach/bank-automation-kpi-extraction.git
cd bank-automation-kpi-extraction
make setup && make run
```

Open **http://localhost:8501**. See **[GETTING_STARTED.md](GETTING_STARTED.md)** for the full walkthrough.

| Mode | How | Notes |
|------|-----|-------|
| **Full (recommended)** | `./run_local.sh` | Full Docling + OCR — best accuracy |
| **Fast (tables only)** | See below | Same as OpenShift fast mode |

Fast local mode:

```bash
cd combined_soln
PYTHONPATH=..:.:../IB:../PNB:../HDFC streamlit run streamlit_app_openshift.py --server.headless=false
```

---

## 2. Deploy to OpenShift

Use **`deploy_openshift_new.sh`** with cluster credentials (no hardcoded tokens in repo).

1. Get **OCP server URL** and **token** from your OpenShift console.

2. Deploy:

```bash
export OCP_SERVER="https://api.cluster-XXXX:6443"
export OCP_TOKEN="sha256~your-token"
./deploy_openshift_new.sh cpu    # or: gpu
```

3. Build/push the container image first if this is a fresh cluster (Section 3).

---

## 3. Build and push images

Default registry: **quay.io/vraste/indian-bank-pnb-kpi** (update in build scripts if you use your own registry).

| Tag | Use case | Script |
|-----|----------|--------|
| `:latest` | Full Docling + OCR | `./build_and_push.sh` |
| `:openshift` | Fast Docling, CPU | `./build_and_push_openshift.sh` |
| `:openshift-gpu` | Fast Docling, GPU | `./build_and_push_openshift_gpu.sh` |

---

## 4. OpenShift manifests

| File | Image | When |
|------|-------|------|
| `openshift/deployment.yaml` | `:latest` | Full OCR, CPU |
| `openshift/deployment_openshift.yaml` | `:openshift` | Fast mode, CPU |
| `openshift/deployment_openshift_gpu.yaml` | `:openshift-gpu` | Fast mode, NVIDIA GPU |

---

## 5. App URL after deploy

```bash
oc get route indian-bank-pnb-kpi -o jsonpath='{.spec.host}'
```

---

## 6. GPU check

```bash
oc logs deployment/indian-bank-pnb-kpi --tail=100 | grep -i cuda
```

---

## 7. Troubleshooting

- **Import errors:** Run from repo root; `run_local.sh` sets `PYTHONPATH` for IB, PNB, HDFC, combined_soln.
- **Image pull errors:** Configure `imagePullSecret` for Quay if the image is private.
- **New cluster:** Always export `OCP_SERVER` and `OCP_TOKEN` before deploy.

See also [README.md](README.md) and [DEPLOY.md](DEPLOY.md).

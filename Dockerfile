# Indian Bank & PNB KPI Analyst - Streamlit + RAG (Milvus)
# Multi-platform: linux/amd64 (OpenShift, x86) and linux/arm64 (Apple Silicon, ARM)

FROM python:3.11-slim-bookworm

WORKDIR /app

# System deps for docling (PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU PyTorch (faster build; for GPU use cu121 image and uncomment GPU in deployment.yaml)
RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# App code (ARG forces rebuild of app layers when you pass different APP_BUILD)
ARG APP_BUILD=0
RUN echo "App build: ${APP_BUILD}"
COPY combined_soln/ combined_soln/
COPY IB/ IB/
COPY PNB/ PNB/
COPY .streamlit/ combined_soln/.streamlit/

# Ensure combined_soln is on path
ENV PYTHONPATH=/app:/app/IB:/app/PNB
WORKDIR /app/combined_soln

# Streamlit
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501
EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.headless=true"]

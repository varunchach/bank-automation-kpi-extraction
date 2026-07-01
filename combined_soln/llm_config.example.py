"""LLM and tool credentials — copy to llm_config.py and fill in, or set env vars."""

import os

# OpenAI-compatible chat endpoint (e.g. LiteLLM, vLLM, OpenAI)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://your-llm-endpoint/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "your-model-name")

# Tavily web search (https://tavily.com)
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

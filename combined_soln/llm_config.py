"""LLM and tool credentials. Override via env: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, TAVILY_API_KEY."""

import os

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

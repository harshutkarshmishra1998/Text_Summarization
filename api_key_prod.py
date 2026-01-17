import os
from pathlib import Path


def _load_local_env():
    """
    Load .env only in local environments.
    Safe no-op in Streamlit Cloud.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent / ".env")
    except Exception:
        # dotenv not available or running in cloud
        pass


def _get_secret(key: str) -> str | None:
    """
    Unified secret loader:
    1. Streamlit Cloud secrets
    2. Environment variables (.env locally)
    """
    # Try Streamlit secrets first (cloud)
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass

    # Fallback to OS environment (local)
    return os.getenv(key)


def require_env(key: str) -> str:
    value = _get_secret(key)
    if not value:
        raise RuntimeError(f"Missing required secret: {key}")
    return value


# Load local .env if present
_load_local_env()


# ---- REQUIRED ENV VARS ----
ENV_KEYS = {
    "OPENAI_API_KEY": "OPENAI_API",
    "LANGCHAIN_API_KEY": "LANGCHAIN_API",
    "HUGGING_FACE_API": "HUGGING_FACE_API",
    "GROQ_API_KEY": "GROQ_API",
    "ASTRA_DB_API_ENDPOINT": "ASTRA_DB_API_ENDPOINT",
    "ASTRA_DB_APPLICATION_TOKEN": "ASTRA_DB_APPLICATION_TOKEN",
    "ASTRA_DB_KEYSPACE": "ASTRA_DB_KEYSPACE",
    "WB_API": "WB_API",
    "SERPAI_API": "SERPAI_API",
}

# ---- LOAD + EXPORT ----
_loaded = {}

for env_name, source_key in ENV_KEYS.items():
    value = require_env(source_key)
    os.environ[env_name] = value
    _loaded[env_name] = value


# ---- OPTIONAL: SAFE DEBUG (NO LEAKS) ----
if __name__ == "__main__":
    for k in _loaded:
        print(f"{k}: loaded")


# ---- RUNTIME CONFIG ----
os.environ["LANGCHAIN_TRACING_V2"] = "1"
os.environ["LANGCHAIN_PROJECT"] = "QA RAG Chatbot"
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["USE_TORCH"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["USER_AGENT"] = "qa-search-engine/1.0"
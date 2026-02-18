# Installation

## Requirements

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- An LLM API key (Anthropic, OpenAI, Gemini, etc.)

## Install

=== "uv"

    ```bash
    uv add retrai
    ```

=== "pip"

    ```bash
    pip install retrai
    ```

=== "From source"

    ```bash
    git clone https://github.com/dominikpeter/retrAI
    cd retrAI
    uv sync
    ```

## API Keys

retrAI uses [LiteLLM](https://docs.litellm.ai) to talk to any LLM provider.
Set the appropriate environment variable:

```bash
# Anthropic (default)
export ANTHROPIC_API_KEY="sk-ant-..."

# OpenAI
export OPENAI_API_KEY="sk-..."

# Google
export GEMINI_API_KEY="..."
```

Or create a `.env` file in your project — retrAI loads it automatically.

## Frontend (optional)

The web dashboard is pre-built and served by `retrai serve`. To develop it:

```bash
cd frontend
bun install
bun run dev    # dev server on :5173, proxies /api to :8000
```

# Installation

## Requirements

- **Python ≥ 3.12**
- An LLM API key (Anthropic, OpenAI, Google, Azure, or any [LiteLLM](https://docs.litellm.ai) provider)

## Install

=== "uv (recommended)"

    ```bash
    uv add retrai
    ```

=== "pip"

    ```bash
    pip install retrai
    ```

=== "pipx (global CLI)"

    ```bash
    pipx install retrai
    ```

=== "From source"

    ```bash
    git clone https://github.com/bmsuisse/retrAI
    cd retrAI
    uv sync
    ```

## Configure Your LLM

retrAI uses [LiteLLM](https://docs.litellm.ai) under the hood, so it works with **any provider** — just set the right env var:

| Provider | Env Variable | Example Model |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Google | `GEMINI_API_KEY` | `gemini/gemini-2.0-flash` |
| Azure OpenAI | `AZURE_API_KEY` + `AZURE_API_BASE` | `azure/gpt-4o` |
| Ollama | *(no key needed)* | `ollama/llama3` |
| GitHub Copilot | *(auto via OAuth)* | `copilot/gpt-4o` |

Set it via environment variable or `.env` file (auto-loaded):

```bash
# Pick your provider
export ANTHROPIC_API_KEY="sk-ant-..."

# Or create a .env file (retrAI loads it automatically)
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env
```

!!! tip "First-time setup"
    Run `retrai init` for an interactive wizard that helps you pick a provider, model, and API key.

## Verify Installation

```bash
retrai --help
```

You should see the available commands: `run`, `serve`, `tui`, `init`, `generate-eval`.

## Frontend (optional)

The web dashboard is served automatically by `retrai serve`. For frontend development:

```bash
cd frontend
bun install
bun run dev    # dev server on :5173, proxies /api → :8000
```

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-02-18

### Added

- **Autonomous agent loop** — LangGraph StateGraph with plan → act → evaluate → reflect cycle
- **12 goal types** — `pytest`, `pyright`, `bun-test`, `npm-test`, `cargo-test`, `go-test`, `make-test`, `shell-goal`, `perf-check`, `sql-benchmark`, `ai-eval`, `ml-optimize`
- **Auto-detection** — scans project files to pick the right goal automatically
- **AI eval harness** — describe a goal in plain English, agent generates the test harness and then implements the solution
- **Multi-model support** — any LiteLLM-compatible model (Claude, GPT, Gemini, Ollama, etc.)
- **Textual TUI** — rich terminal dashboard with live event streaming
- **Web dashboard** — FastAPI + Vue 3 with WebSocket real-time updates, agent graph visualization, HITL modal
- **Human-in-the-loop** — optional checkpoints before each iteration
- **CLI** — `retrai run`, `retrai serve`, `retrai tui`, `retrai init`, `retrai generate-eval`
- **File watcher** — auto-triggers agent on file changes
- **Benchmark mode** — compare models on the same task across rounds
- **Tool system** — pluggable tool registry with `bash_exec`, `read_file`, `write_file`, `grep_search`, `find_files`, `git_diff`, `js_exec`, `sql_bench`, `web_search`
- **Pipeline mode** — chain multiple goals in sequence
- **Agent memory** — persist learned strategies across runs
- **Code review** — static analysis integration
- **Event bus** — async fan-out to CLI, TUI, and WebSocket consumers
- **MkDocs documentation site** — getting started, architecture, API reference
- **6 example projects** — SQL, pytest, ML, perf, pyright, shell linting

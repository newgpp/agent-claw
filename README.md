# agent-claw

Python agent framework with a ReAct core, shared runtime utilities, and app-level agents built from reusable skills and tools.

## Overview

`agent-claw` is a layered Python project for building agents with a ReAct-style
planning and execution loop.

- `common`: shared infrastructure such as logging, tracing, and utility helpers
- `clawcore`: the runtime layer that coordinates thoughts, actions, tools, and
  final answers
- `agents`: business-facing agents built on top of `clawcore`

## Project Structure

```text
agent-claw/
├── DEV_NOTES.md
├── configs/
├── examples/
├── pyproject.toml
├── skills/
├── src/
│   ├── agents/
│   ├── apps/
│   ├── clawcore/
│   └── common/
└── tests/
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python3 examples/openai_runtime.py
pytest
```

Set `OPENAI_API_KEY` in `.env` before running OpenAI-backed agents. You can also
override:

- `OPENAI_BASE_URL`
- `TAVILY_API_KEY`
- `TAVILY_API_URL`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_USE_TLS`
- `SMTP_USE_SSL`
- `AGENT_CLAW_AGENTS_DIR`
- `AGENT_CLAW_API_HOST`
- `AGENT_CLAW_API_PORT`

## Gmail SMTP for `send_email`

If you want to test the `send_email` agent tool with Gmail, use this `.env`
setup:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=yourname@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM=yourname@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

Notes:

- `SMTP_PASSWORD` should be a Gmail App Password, not your normal Google account password
- Gmail SMTP usually requires Google 2-Step Verification to be enabled before App Passwords are available
- `SMTP_FROM` should match the Gmail address you authenticated with for the simplest local testing setup

## Agent Configs

Runtime agents are configured from JSON files in `configs/agents/`.

- `configs/agents/openai_runtime.json`
  - minimal OpenAI-compatible runtime agent example
- `configs/agents/weather.json`
  - weather-focused agent that enables the `weather` skill and the agent-level `curl` tool

Each config currently controls:

- `type`
- `model`
- `tools`
- `skills`
- `base_instructions`
- `max_steps`
- `include_read_skill`
- `temperature`

Built-in tools are loaded by default. The `tools` field is for agent-level tools
defined under `src/agents/tools/`.

## Running

Run the example OpenAI-backed agent:

```bash
python3 examples/openai_runtime.py
```

Run a weather-focused agent through the API after installing the weather skill:

```bash
python examples/install_skill.py \
  "https://github.com/openclaw/openclaw/tree/main/skills/weather" \
  --skills-root skills
python3 -m apps.api.run
curl -X POST http://127.0.0.1:8000/runs \
  -H 'Content-Type: application/json' \
  -d '{"agent_id":"weather","user_input":"香港的天气怎么样？"}'
```

Run the FastAPI API locally:

```bash
python3 -m apps.api.run
```

The API exposes:

- `GET /health`
- `GET /agents`
- `POST /runs`
- `POST /runs/debug`

`POST /runs/debug` returns the final answer plus runtime debug state:

- `scratchpad`
- `tool_results`
- `events`
- `trace`

## Logging and Trace IDs

The API configures a shared Loguru formatter on startup. Console logs show a
single `trace_id` so one HTTP request can be followed across:

- API request logging
- LLM request and response logging
- runtime completion logging

The request trace is bound once at the API middleware layer and reused by the
runtime for downstream logs.

## Install Skills

`agent-claw` currently supports installing document-skills from GitHub directory
URLs.

Example:

```bash
python examples/install_skill.py \
  "https://github.com/anthropics/skills/tree/main/skills/xlsx" \
  --skills-root skills
```

If you use a local proxy, pass it explicitly:

```bash
python examples/install_skill.py \
  "https://github.com/anthropics/skills/tree/main/skills/xlsx" \
  --skills-root skills \
  --proxy http://127.0.0.1:7890
```

```bash
python examples/install_skill.py \
  "https://github.com/openclaw/openclaw/tree/main/skills/weather" \
  --skills-root skills \
  --proxy http://127.0.0.1:7890
```

The installer will:

- parse the GitHub skill URL
- download the target skill directory
- require `SKILL.md`
- preserve the skill's `scripts/` directory
- generate a local `skill.json`

Installed skills live under the repo-level `skills/` directory and can be
reviewed, versioned, or customized alongside the rest of the project.

## Initial Goal

This repository starts with a minimal runtime skeleton so the architecture is
clear from day one:

- `common` owns shared concerns
- `clawcore` owns the execution model
- `agents` owns business behavior

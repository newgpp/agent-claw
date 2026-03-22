# agent-claw

Python agent framework with a ReAct runtime, reusable skills/tools, and API-facing agents configured from JSON.

## Overview

- `common`: shared infrastructure such as logging, tracing, and utility helpers
- `clawcore`: runtime loop, planner/LLM adapters, and tool execution
- `agents`: business-facing agents built on top of `clawcore`

```mermaid
flowchart TD
    A[User Input] --> B[Agent Config<br/>tools + skills + base_instructions + planning.mode]
    B --> C{planning.mode}

    C -->|disabled| D[Direct ReAct Runtime]
    C -->|auto| E{Simple request?}
    C -->|always| F[Planned Runtime]

    E -->|yes| D
    E -->|no| F

    D --> G[LLM Step]
    G --> H{Need full skill?}
    H -->|yes| I[read_skill]
    H -->|no| J[Select Tool]
    I --> J
    J --> K[Tool Execution]
    K --> L[Observation -> Scratchpad]
    L --> G
    G -->|final_answer| M[Response]

    F --> N[Planner]
    N --> O[Execution Plan<br/>subgoals + success_criteria]
    O --> P[Execute Current Subgoal via ReAct]
    P --> Q{Need full skill?}
    Q -->|yes| I2[read_skill]
    Q -->|no| J2[Select Tool]
    I2 --> J2
    J2 --> K2[Tool Execution]
    K2 --> L2[Observation / Artifact]
    L2 --> P
    P -->|subgoal done| R{More subgoals?}
    R -->|yes| P
    R -->|no| M
```

```mermaid
flowchart LR
    A[configs/agents/*.json] --> B[agents]
    S[skills/] --> B
    B --> C[clawcore]
    C --> D[LLM Adapters]
    C --> E[Runtime / Planner / Tool Executor]
    E --> F[agent tools]
    B --> F
    B --> G[apps/api]
    C --> H[common]
    B --> H
    G --> H
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python3 -m apps.api.run
```

Set `OPENAI_API_KEY` in `.env` before running OpenAI-backed agents.

## Environment

Common variables:

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

Gmail SMTP example for `send_email`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=yourname@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM=yourname@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

`SMTP_PASSWORD` should be a Gmail App Password, not your normal account password.

## Agent Configs

Agents are configured from `configs/agents/*.json`.

- `openai_runtime.json`: minimal OpenAI-compatible runtime agent
- `weather.json`: weather-focused direct agent
- `research_email_auto.json`: auto-plan agent using weather/research/email tools

Common fields:

- `type`
- `model`
- `tools`
- `skills`
- `base_instructions`
- `max_steps`
- `include_read_skill`
- `temperature`
- `planning.mode`

Built-in tools are loaded by default. The `tools` field is for agent-level tools
defined under `src/agents/tools/`.

## API

Run locally:

```bash
python3 -m apps.api.run
```

Endpoints:

- `GET /health`
- `GET /agents`
- `POST /runs`
- `POST /runs/debug`

`/runs/debug` returns the final answer plus runtime state such as `scratchpad`,
`tool_results`, `plan`, `events`, `trace`, and `token_usage`.

Example:

```bash
curl -X POST http://127.0.0.1:8000/runs/debug \
  -H 'Content-Type: application/json' \
  -d '{"agent_id":"weather","user_input":"香港的天气怎么样？"}'
```

## Skills

Skills live under `skills/` and are versioned with the repo.

Install a skill from GitHub:

```bash
python examples/install_skill.py \
  "https://github.com/openclaw/openclaw/tree/main/skills/weather" \
  --skills-root skills
```

With a proxy:

```bash
python examples/install_skill.py \
  "https://github.com/openclaw/openclaw/tree/main/skills/weather" \
  --skills-root skills \
  --proxy http://127.0.0.1:7890
```

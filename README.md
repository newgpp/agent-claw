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
├── examples/
├── pyproject.toml
├── src/
│   ├── agents/
│   ├── clawcore/
│   └── common/
└── tests/
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python3 examples/openai_runtime.py
pytest
```

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

Installed skills are meant to be local runtime assets and are ignored by git
through `skills/` in `.gitignore`.

## Initial Goal

This repository starts with a minimal runtime skeleton so the architecture is
clear from day one:

- `common` owns shared concerns
- `clawcore` owns the execution model
- `agents` owns business behavior

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
python3 examples/basic_run.py
pytest
```

## Initial Goal

This repository starts with a minimal runtime skeleton so the architecture is
clear from day one:

- `common` owns shared concerns
- `clawcore` owns the execution model
- `agents` owns business behavior

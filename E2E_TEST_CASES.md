# E2E Test Cases

## Common Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python examples/install_skill.py \
  "https://github.com/openclaw/openclaw/tree/main/skills/weather" \
  --skills-root skills
python3 -m apps.api.run
```

`.env` minimum:

```env
OPENAI_API_KEY=...
TAVILY_API_KEY=...

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=yourname@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM=yourname@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

## Case 1: Research Email Auto

Environment:

- agent config: [research_email_auto.json](/Users/mini/Documents/py_projects/agent-claw/configs/agents/research_email_auto.json)
- agent id: `research_email_auto`

Input:

```bash
curl -X POST http://127.0.0.1:8000/runs/debug \
  -H 'Content-Type: application/json' \
  -d '{
    "agent_id": "research_email_auto",
    "user_input": "Please check today'\''s Hong Kong weather, add a short commute tip, write a concise English email, and send it to yourname@gmail.com"
  }'
```

Output:

- returns `final_answer`
- debug payload contains non-null `plan`
- `plan.subgoals` includes weather, drafting, and sending related steps
- `tool_results` includes weather retrieval and may include Tavily search
- `artifacts` contains intermediate subgoal outputs
- if SMTP config is valid, the email is sent to the target inbox

## Template

Environment:

- agent config:
- agent id:

Input:

```bash
curl -X POST http://127.0.0.1:8000/runs/debug \
  -H 'Content-Type: application/json' \
  -d '{
    "agent_id": "",
    "user_input": ""
  }'
```

Output:

- 

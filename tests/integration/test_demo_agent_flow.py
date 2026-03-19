import asyncio
import json
from pathlib import Path

from agents import EchoAgent, FileSummaryAgent


def test_demo_agent_flow_matches_fixture_cases(tmp_path: Path) -> None:
    fixture_cases = json.loads(Path("tests/fixtures/agents/demo_agent_cases.json").read_text(encoding="utf-8"))

    for case in fixture_cases:
        if case["agent"] == "echo-agent":
            agent = EchoAgent()
            assert asyncio.run(agent.run(case["input"])) == case["expected"]
        elif case["agent"] == "file-summary-agent":
            file_path = tmp_path / case["workspace_file"]
            file_path.write_text(case["workspace_content"], encoding="utf-8")
            agent = FileSummaryAgent(target_path=case["workspace_file"])
            assert asyncio.run(agent.run(case["input"], workspace_dir=tmp_path)) == case["expected"]

import asyncio

from agents import FileSummaryAgent


def test_file_summary_agent_binds_file_summary_skill() -> None:
    agent = FileSummaryAgent()

    assert [skill.name for skill in agent.config.skills] == ["file-summary"]
    assert "read" in agent.runtime.tool_executor.registry.names()
    assert "read_skill" in agent.runtime.tool_executor.registry.names()


def test_file_summary_agent_summarizes_after_loading_skill(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "note.txt").write_text("release note", encoding="utf-8")
    agent = FileSummaryAgent(target_path="note.txt")

    result = asyncio.run(agent.run("summarize the note", workspace_dir=tmp_path))

    assert result == "Summary of note.txt: release note"

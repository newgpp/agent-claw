import asyncio
import zipfile
from io import BytesIO
from pathlib import Path

from clawcore.skilling.github import GitHubSkillRef
from clawcore.skilling.install import GitHubArchiveDownloader


def _build_zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_archive_downloader_extracts_target_skill_directory(tmp_path: Path, monkeypatch) -> None:
    downloader = GitHubArchiveDownloader()
    skill_ref = GitHubSkillRef(
        repo="anthropics/skills",
        ref="main",
        path="skills/xlsx",
        url="https://github.com/anthropics/skills/tree/main/skills/xlsx",
    )
    archive_bytes = _build_zip_bytes(
        {
            "skills-main/skills/xlsx/SKILL.md": b"# XLSX\nUse this skill.\n",
            "skills-main/skills/xlsx/scripts/recalc.py": b"print('ok')\n",
            "skills-main/skills/other/SKILL.md": b"# Other\n",
        }
    )

    async def fake_download_archive(self, archive_url):  # type: ignore[no-untyped-def]
        return archive_bytes

    monkeypatch.setattr(GitHubArchiveDownloader, "_download_archive", fake_download_archive)
    extracted = asyncio.run(downloader.fetch(skill_ref, tmp_path))

    assert extracted.joinpath("SKILL.md").exists()
    assert extracted.joinpath("scripts/recalc.py").exists()
    assert not extracted.joinpath("../other").exists()


def test_archive_downloader_respects_explicit_proxy(monkeypatch) -> None:
    downloader = GitHubArchiveDownloader(proxy_url="http://127.0.0.1:7890")
    captured: dict[str, object] = {}

    def fake_build_opener(*handlers):  # type: ignore[no-untyped-def]
        captured["handlers"] = handlers

        class FakeOpener:
            def open(self, request, timeout=None):  # type: ignore[no-untyped-def]
                captured["request"] = request
                captured["timeout"] = timeout

                class Response:
                    def __enter__(self_inner):
                        return self_inner

                    def __exit__(self_inner, exc_type, exc, tb):
                        return False

                    def read(self_inner):
                        return b""

                return Response()

        return FakeOpener()

    monkeypatch.setattr("urllib.request.build_opener", fake_build_opener)
    asyncio.run(downloader._download_archive("https://example.com/archive.zip"))

    handlers = captured["handlers"]
    assert handlers

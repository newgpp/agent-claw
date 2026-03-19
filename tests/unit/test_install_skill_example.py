from clawcore.skilling.cli import build_install_skill_parser


def test_install_skill_example_parser_accepts_proxy_and_root() -> None:
    parser = build_install_skill_parser()

    args = parser.parse_args(
        [
            "https://github.com/anthropics/skills/tree/main/skills/xlsx",
            "--skills-root",
            "tmp-skills",
            "--proxy",
            "http://127.0.0.1:7890",
        ]
    )

    assert args.url == "https://github.com/anthropics/skills/tree/main/skills/xlsx"
    assert args.skills_root == "tmp-skills"
    assert args.proxy == "http://127.0.0.1:7890"

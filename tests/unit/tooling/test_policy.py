from clawcore.tooling.policy import ToolPolicy


def test_policy_blocks_denied_tools() -> None:
    policy = ToolPolicy(deny={"write"})

    assert policy.is_allowed("read") is True
    assert policy.is_allowed("write") is False


def test_policy_uses_allowlist_when_present() -> None:
    policy = ToolPolicy(allow={"read"})

    assert policy.is_allowed("read") is True
    assert policy.is_allowed("write") is False

from __future__ import annotations

from noesis_agent.runtime import identity


def test_git_branch_uses_local_branch(monkeypatch) -> None:
    monkeypatch.setattr(
        identity,
        "_git",
        lambda *args: "local-feature" if args == ("branch", "--show-current") else None,
    )

    assert identity._git_branch() == "local-feature"


def test_git_branch_uses_github_pull_request_head(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_HEAD_REF", "noesis-ci-cd-standardization")
    monkeypatch.setenv("GITHUB_REF_NAME", "7/merge")
    monkeypatch.setattr(identity, "_git", lambda *args: None)

    assert identity._git_branch() == "noesis-ci-cd-standardization"


def test_git_branch_uses_github_push_ref(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setattr(identity, "_git", lambda *args: None)

    assert identity._git_branch() == "main"


def test_git_branch_reports_detached_commit(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)

    def fake_git(*args: str) -> str | None:
        if args == ("rev-parse", "--short", "HEAD"):
            return "abc1234"
        return None

    monkeypatch.setattr(identity, "_git", fake_git)

    assert identity._git_branch() == "detached@abc1234"


def test_git_branch_has_safe_final_fallback(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_HEAD_REF", raising=False)
    monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    monkeypatch.setattr(identity, "_git", lambda *args: None)

    assert identity._git_branch() == "unknown"
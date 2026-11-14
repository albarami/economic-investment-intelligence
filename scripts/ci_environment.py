"""The environment of a GitHub-hosted runner, shared by the checks that need it."""

from __future__ import annotations

from collections.abc import Mapping

HOSTED_RUNNER = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted"}


def is_hosted_runner(environ: Mapping[str, str]) -> bool:
    """Return whether every hosted-runner variable holds its exact value."""
    return all(environ.get(key) == value for key, value in HOSTED_RUNNER.items())

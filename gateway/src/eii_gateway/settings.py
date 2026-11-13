"""Only explicit offline tooling reads this environment variable."""

import os


def configured_provider() -> str:
    provider = os.environ.get("EII_DECISION_PROVIDER", "none")
    if provider not in ("none", "recorded", "jev"):
        raise ValueError("unknown configured provider")
    return provider

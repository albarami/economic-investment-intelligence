"""Every product test runs under the provider request log (S3-T16)."""

from pytest_no_provider import provider_request_log

__all__ = ["provider_request_log"]

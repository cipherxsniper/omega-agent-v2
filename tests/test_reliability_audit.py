import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.omega_reliability_audit import redact_headers, validate_url


def test_redacts_sensitive_values():
    value = redact_headers({"Authorization": "Bearer abc", "api_key": "secret", "safe": "ok"})
    assert value["Authorization"] == "[REDACTED]"
    assert value["api_key"] == "[REDACTED]"
    assert value["safe"] == "ok"


def test_rejects_credentials_and_unsupported_scheme():
    try:
        validate_url("https://user:password@example.com")
        raise AssertionError("credential-bearing URL should be rejected")
    except ValueError:
        pass
    try:
        validate_url("file:///etc/passwd")
        raise AssertionError("file URL should be rejected")
    except ValueError:
        pass


if __name__ == "__main__":
    test_redacts_sensitive_values()
    test_rejects_credentials_and_unsupported_scheme()
    print("RELIABILITY_AUDIT_POLICY_SMOKE_OK")

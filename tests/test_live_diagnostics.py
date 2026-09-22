import httpx
from ops.demo_live_server import safe_error_diagnostic


def test_probe_error_diagnostics_keep_types_and_drop_sensitive_messages():
    outer=ValueError("secret-password-and-url")
    outer.__cause__=httpx.ReadTimeout("Authorization: SECRET")
    assert safe_error_diagnostic(outer)=="ValueError/ReadTimeout"


def test_probe_error_diagnostics_bound_cycles_and_unknown_classes():
    class SecretNamedError(Exception):
        pass
    error=SecretNamedError("SECRET")
    error.__cause__=error
    assert safe_error_diagnostic(error)=="OtherError"

# Design Document: ALLOWED_EMAIL_DOMAINS as Environment Variable

## 1. Summary

Replace the hardcoded `ALLOWED_EMAIL_DOMAINS = ["uw.edu"]` in Django settings with a value parsed from the `ALLOWED_EMAIL_DOMAINS` environment variable, falling back to `["uw.edu"]` as the default. An empty-string value disables domain restrictions entirely.

## 2. Current State

| File | Line | Current Value |
|---|---|---|
| `src/llteacher/settings.py` | 117 | `ALLOWED_EMAIL_DOMAINS = ["uw.edu"]` |
| `src/llteacher/production.py` | 153 | `ALLOWED_EMAIL_DOMAINS = ["uw.edu"]` |

The setting is consumed in three places in `src/accounts/forms.py` via `getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])`, and the utility `is_email_domain_allowed()` in `src/accounts/utils.py`. Error messages in forms are hardcoded with UW-specific text.

## 3. Design

### 3.1 Env Variable Format

- **Variable name**: `ALLOWED_EMAIL_DOMAINS`
- **Format**: Comma-separated list of domain strings (e.g. `uw.edu,washington.edu`)
- **Default**: `uw.edu` (preserves existing behavior)
- **Empty string**: Disables all domain restrictions (allows every domain)

### 3.2 Parser Function: `parse_allowed_email_domains()`

**Location**: `src/accounts/utils.py`

```python
import os

ALLOWED_EMAIL_DOMAINS_ENV_VAR = "ALLOWED_EMAIL_DOMAINS"
_DEFAULT_ALLOWED_DOMAINS = ["uw.edu"]


def parse_allowed_email_domains() -> list[str]:
    """
    Read ALLOWED_EMAIL_DOMAINS from the environment and parse into a list.

    Format: comma-separated domains, e.g. "uw.edu,washington.edu"
    Empty string returns [] (all domains allowed).
    Absent or unparseable returns the default ["uw.edu"].

    Returns:
        list[str]: Parsed list of allowed domains.
    """
    raw = os.getenv(ALLOWED_EMAIL_DOMAINS_ENV_VAR)
    if raw is None:
        return _DEFAULT_ALLOWED_DOMAINS.copy()
    stripped = raw.strip()
    if not stripped:
        return []
    domains = [d.strip().lower() for d in stripped.split(",") if d.strip()]
    if not domains:
        return _DEFAULT_ALLOWED_DOMAINS.copy()
    return domains
```

**Edge cases handled**:
| Input | Result |
|---|---|
| env var not set (`os.getenv` returns `None`) | `["uw.edu"]` |
| `""` (empty string) | `[]` (all domains allowed) |
| `"uw.edu"` | `["uw.edu"]` |
| `"uw.edu,washington.edu"` | `["uw.edu", "washington.edu"]` |
| `"  UW.EDU ,  "` (whitespace, trailing comma) | `["uw.edu"]` (blank entries filtered) |
| `"  ,  ,  "` (only commas/whitespace) | `["uw.edu"]` (fallback to default) |

### 3.3 Settings File Modifications

#### `src/llteacher/settings.py` (line 117)

Replace:
```python
ALLOWED_EMAIL_DOMAINS = ["uw.edu"]
```
with:
```python
from accounts.utils import parse_allowed_email_domains

ALLOWED_EMAIL_DOMAINS = parse_allowed_email_domains()
```

#### `src/llteacher/production.py` (line 153)

Same replacement. Both settings files now derive the value from the environment.

### 3.4 Form Error Messages

The error messages in `src/accounts/forms.py` are currently UW-specific:

```python
# Line 121 (RegistrationForm.clean_email)
"Email must be from University of Washington domain (@uw.edu or subdomain). "
"Please use your UW email address."

# Line 207 (ProfileForm.clean_email)
"New email domain must be from University of Washington (@uw.edu or subdomain). "
"Please use your UW email address."
```

Replace these with dynamic messages that reflect the actual configured domains. The `__init__` method of `RegistrationForm` already builds a human-readable domain list for the `title` attribute (`domain_text` at line 53-58). Extract that logic into a shared helper so both the title and the error message stay in sync.

**New helper in `src/accounts/forms.py`**:

```python
def _format_allowed_domains_text(allowed_domains: list[str]) -> str:
    """Build a human-readable string from the allowed domains list.
    
    E.g. ['uw.edu'] -> '@uw.edu or subdomain'
    E.g. ['uw.edu', 'washington.edu'] -> '@uw.edu or @washington.edu (including subdomains)'
    """
    if len(allowed_domains) == 1:
        return f"@{allowed_domains[0]} or subdomain"
    domain_list = ", ".join(f"@{d}" for d in allowed_domains[:-1])
    return f"{domain_list}, or @{allowed_domains[-1]} (including subdomains)"
```

**Updated error message in `RegistrationForm.clean_email`** (line 120-123):

```python
allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])
if allowed_domains and email and not is_email_domain_allowed(email, allowed_domains):
    domain_text = _format_allowed_domains_text(allowed_domains)
    raise ValidationError(
        f"Email must be from an allowed domain ({domain_text}). "
        "Please use an email address from an allowed domain."
    )
```

**Updated error message in `ProfileForm.clean_email`** (line 206-209):

```python
if allowed_domains and not is_email_domain_allowed(email, allowed_domains):
    domain_text = _format_allowed_domains_text(allowed_domains)
    raise ValidationError(
        f"New email domain must be from an allowed domain ({domain_text}). "
        "Please use an email address from an allowed domain."
    )
```

The `__init__` method of `RegistrationForm` can also be refactored to use `_format_allowed_domains_text` for the `title` attribute, eliminating the inline duplicate logic at lines 52-58.

### 3.5 `load_dotenv()` Support

`python-dotenv` is already a dependency in `pyproject.toml` but is never imported. Add `load_dotenv()` to `manage.py` so that `.env` files are loaded in development:

```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from dotenv import load_dotenv


def main():
    """Run administrative tasks."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
    load_dotenv()  # Load .env file before Django settings are evaluated
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "llteacher.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

This ensures that in local development, a `.env` file in the project root is loaded before the settings module is imported.

### 3.6 `.env.example`

Create a new file `.env.example` at the project root with documentation:

```bash
# Allowed email domains for registration.
# Comma-separated list of domains (supports subdomains).
# Default: uw.edu
# Set to empty to allow all domains.
ALLOWED_EMAIL_DOMAINS=uw.edu,washington.edu
```

## 4. Files Changed

| File | Action |
|---|---|
| `src/accounts/utils.py` | Add `parse_allowed_email_domains()` and `ALLOWED_EMAIL_DOMAINS_ENV_VAR` constant |
| `src/llteacher/settings.py` | Replace hardcoded list with `parse_allowed_email_domains()` |
| `src/llteacher/production.py` | Replace hardcoded list with `parse_allowed_email_domains()` |
| `src/accounts/forms.py` | Add `_format_allowed_domains_text()` helper; use it for error messages and title; remove hardcoded UW text |
| `manage.py` | Add `load_dotenv()` call |
| `.env.example` | New file documenting the env var |
| `src/accounts/tests/test_domain_validation.py` | Update tests to use `parse_allowed_email_domains()` and match new error messages |

## 5. Test Updates

### 5.1 New Tests for `parse_allowed_email_domains()`

Add to `src/accounts/tests/test_domain_validation.py`:

```python
class TestParseAllowedEmailDomains(TestCase):
    """Test the env var parsing function."""

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_env_not_set_returns_default(self):
        """When env var is not set, return default [uw.edu]."""
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu"])

    @mock.patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": ""}, clear=True)
    def test_empty_string_allows_all(self):
        """When env var is empty string, return [] (allow all)."""
        result = parse_allowed_email_domains()
        self.assertEqual(result, [])

    @mock.patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": "uw.edu"}, clear=True)
    def test_single_domain(self):
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu"])

    @mock.patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": "uw.edu,washington.edu"}, clear=True)
    def test_multiple_domains(self):
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu", "washington.edu"])

    @mock.patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": "  UW.EDU ,  "}, clear=True)
    def test_whitespace_and_trailing_comma(self):
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu"])

    @mock.patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": "  ,  ,  "}, clear=True)
    def test_only_commas_falls_back_to_default(self):
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu"])

    @mock.patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": "  "}, clear=True)
    def test_whitespace_only_allows_all(self):
        result = parse_allowed_email_domains()
        self.assertEqual(result, [])

    @mock.patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": "UW.EDU"}, clear=True)
    def test_case_insensitive_normalization(self):
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu"])
```

### 5.2 Update Existing Tests

**`TestDomainValidationIntegration.test_settings_configuration`** (line 240-245): Should use `mock.patch.dict` on the env var instead of relying on the hardcoded setting value. However, since `test_settings.py` inherits from `settings.py` via `from .settings import *`, and `settings.py` now calls `parse_allowed_email_domains()` at import time, the test settings will evaluate the env var at import time. During test runs, the env var is typically not set, so the default `["uw.edu"]` will be used. This test should either be removed or adapted.

**`test_no_allowed_domains_setting`** (line 247-262): Uses `self.settings(ALLOWED_EMAIL_DOMAINS=[])` — this will still work because `self.settings()` overrides at runtime regardless of how the setting was initially defined.

**`TestClientSideValidationPatterns`** (line 265+): All tests use `self.settings()` context managers and test the behavior, not the origin of the value. These remain unchanged.

**Tests that check error message text** (lines 123-126, 177-179, 210-212): Must be updated to match the new dynamic error message format. For example:

```python
# Before:
self.assertIn("Email must be from University of Washington domain", str(form.errors))
# After:
self.assertIn("Email must be from an allowed domain", str(form.errors))
```

## 6. Implementation Order

1. Add `parse_allowed_email_domains()` to `src/accounts/utils.py`
2. Update `src/accounts/forms.py` with `_format_allowed_domains_text()` and dynamic error messages
3. Update `src/llteacher/settings.py` to use `parse_allowed_email_domains()`
4. Update `src/llteacher/production.py` to use `parse_allowed_email_domains()`
5. Add `load_dotenv()` to `manage.py`
6. Create `.env.example`
7. Add new tests for `parse_allowed_email_domains()`
8. Update existing tests to match new error messages
9. Run full test suite to verify

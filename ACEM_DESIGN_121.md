# Implementation Plan: ALLOWED_EMAIL_DOMAINS as Environment Variable

## 1. Overview

**Objective**: Make the `ALLOWED_EMAIL_DOMAINS` Django setting configurable via an environment variable instead of being hardcoded.

**Current state**: The setting is hardcoded as `["uw.edu"]` in two files (`settings.py` and `production.py`). The consuming code in `accounts/forms.py` reads it via `getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])`.

## 2. Files to Modify

| File | Change |
|------|--------|
| `src/llteacher/settings.py` | Replace hardcoded list with `os.getenv()` + parser |
| `src/llteacher/production.py` | Same change |
| `src/accounts/forms.py` | Update hardcoded UW-specific error message to be domain-agnostic |
| `src/accounts/utils.py` | Add a helper function to parse env var string into list |
| (optional) `manage.py` | Add `load_dotenv()` call to enable `.env` file support |
| (new) `.env.example` | Document the new env variable |
| `src/accounts/tests/test_domain_validation.py` | Add tests for env var parsing |

## 3. Detailed Changes

### 3.1 Add parser helper in `src/accounts/utils.py`

Add a function that converts the raw env var string into a list of domains:

```python
import os


def parse_allowed_email_domains(env_var: str = "ALLOWED_EMAIL_DOMAINS") -> list[str]:
    """
    Parse ALLOWED_EMAIL_DOMAINS from environment variable.

    The env var should be a comma-separated list of domains.
    Whitespace around each domain is stripped. Empty strings
    and the empty-string default produce an empty list.

    Returns:
        List of allowed domains (lowercased).
    """
    raw = os.getenv(env_var, "")
    if not raw or not raw.strip():
        return []
    domains = [d.strip().lower() for d in raw.split(",") if d.strip()]
    return domains
```

This function:
- Returns `[]` when the env var is unset, empty, or whitespace-only (same as the current `getattr(settings, ..., [])` default).
- Strips whitespace from each domain.
- Lowercases all domains (consistent with `is_email_domain_allowed`).
- Filters out empty entries from malformed input like `"uw.edu,,example.com"`.

### 3.2 Update `src/llteacher/settings.py` (line 117)

**Before**:
```python
ALLOWED_EMAIL_DOMAINS = ["uw.edu"]
```

**After**:
```python
from accounts.utils import parse_allowed_email_domains

ALLOWED_EMAIL_DOMAINS = parse_allowed_email_domains()
```

### 3.3 Update `src/llteacher/production.py` (line 153)

**Before**:
```python
ALLOWED_EMAIL_DOMAINS = ["uw.edu"]
```

**After**:
```python
from accounts.utils import parse_allowed_email_domains

ALLOWED_EMAIL_DOMAINS = parse_allowed_email_domains()
```

> **Circular import note**: Settings files are evaluated at Django startup, before any app is loaded. Importing from `accounts.utils` is safe because `utils.py` has no Django imports (only `os` and pure Python). No models, forms, or settings are referenced — only `os.getenv`. This avoids any circular dependency.

### 3.4 Update hardcoded error message in `src/accounts/forms.py`

The `ProfileForm.clean_email()` method (line 207) contains a hardcoded UW-specific error message:

```python
raise ValidationError(
    "New email domain must be from University of Washington (@uw.edu or subdomain). "
    "Please use your UW email address."
)
```

This should be made domain-agnostic. Since the form already has access to `allowed_domains` at line 202, we can use that to build a dynamic message:

```python
if allowed_domains:
    domain_list = ", ".join(f"@{d}" for d in allowed_domains)
    msg = (
        f"New email domain must be from one of the allowed domains: "
        f"{domain_list} (including subdomains)."
    )
else:
    msg = "New email domain is not allowed."
raise ValidationError(msg)
```

Similarly, update the `RegistrationForm.clean_email()` method if it has hardcoded error messages (currently at lines 114-118). Let's check — the RegistrationForm's `clean_email` uses `is_email_domain_allowed` and raises a generic message. Let me verify: looking at lines 106-118 of forms.py.

### 3.5 (Optional) Enable `.env` file support in `manage.py`

`python-dotenv` is already listed as a dependency in `pyproject.toml` but never imported. Add a `load_dotenv()` call to `manage.py`:

```python
#!/usr/bin/env python
import os
import sys

from dotenv import load_dotenv

def main():
    load_dotenv()  # Load .env file if present
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "llteacher.settings")
    ...
```

This allows developers to set `ALLOWED_EMAIL_DOMAINS` in a `.env` file locally without exporting it in their shell.

> **Production note**: In Docker/container environments, env vars are passed through the container runtime, so `.env` is only for local development convenience. The production settings (production.py or Dockerfile) would still rely on OS-level environment variables.

### 3.6 Create `.env.example`

```
# Email domain restrictions for user registration
# Comma-separated list of allowed email domains (subdomains are also allowed)
# Example: ALLOWED_EMAIL_DOMAINS=uw.edu,washington.edu
# Leave empty or unset to allow all domains
ALLOWED_EMAIL_DOMAINS=uw.edu
```

## 4. Usage Examples

```bash
# Single domain
export ALLOWED_EMAIL_DOMAINS=uw.edu

# Multiple domains
export ALLOWED_EMAIL_DOMAINS=uw.edu,washington.edu,example.org

# Allow all domains (empty/unset)
export ALLOWED_EMAIL_DOMAINS=
```

## 5. Test Plan

### 5.1 Add new unit tests in `src/accounts/tests/test_domain_validation.py`

```python
class TestParseAllowedEmailDomains(TestCase):
    """Test the env var parsing utility."""

    @patch("accounts.utils.os.getenv")
    def test_single_domain(self, mock_getenv):
        mock_getenv.return_value = "uw.edu"
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu"])

    @patch("accounts.utils.os.getenv")
    def test_multiple_domains(self, mock_getenv):
        mock_getenv.return_value = "uw.edu,washington.edu,example.org"
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu", "washington.edu", "example.org"])

    @patch("accounts.utils.os.getenv")
    def test_whitespace_handling(self, mock_getenv):
        mock_getenv.return_value = "  uw.edu  ,  washington.edu  "
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu", "washington.edu"])

    @patch("accounts.utils.os.getenv")
    def test_empty_env_var(self, mock_getenv):
        mock_getenv.return_value = ""
        result = parse_allowed_email_domains()
        self.assertEqual(result, [])

    @patch("accounts.utils.os.getenv")
    def test_unset_env_var(self, mock_getenv):
        # Simulate os.getenv returning default
        result = parse_allowed_email_domains()
        # When env var is unset, getenv returns ""
        self.assertEqual(result, [])

    @patch("accounts.utils.os.getenv")
    def test_lowercasing(self, mock_getenv):
        mock_getenv.return_value = "UW.EDU,Washington.EDU"
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu", "washington.edu"])

    @patch("accounts.utils.os.getenv")
    def test_skips_empty_entries(self, mock_getenv):
        mock_getenv.return_value = "uw.edu,,washington.edu"
        result = parse_allowed_email_domains()
        self.assertEqual(result, ["uw.edu", "washington.edu"])

    @patch("accounts.utils.os.getenv")
    def test_all_whitespace(self, mock_getenv):
        mock_getenv.return_value = "  ,  ,  "
        result = parse_allowed_email_domains()
        self.assertEqual(result, [])
```

### 5.2 Existing tests should continue passing

All existing tests in `test_domain_validation.py` use `self.settings(ALLOWED_EMAIL_DOMAINS=[...])` context managers, which override the Django setting regardless of how its default value is constructed. These tests require zero modification.

### 5.3 Manual verification

1. Run tests: `uv run coverage run manage.py test --settings=src.llteacher.test_settings src`
2. Verify with no env var set → `ALLOWED_EMAIL_DOMAINS` resolves to `[]`
3. Verify with `ALLOWED_EMAIL_DOMAINS=uw.edu` → resolves to `["uw.edu"]`
4. Verify with `ALLOWED_EMAIL_DOMAINS=uw.edu,washington.edu` → resolves to `["uw.edu", "washington.edu"]`

## 6. Error Handling & Edge Cases

| Scenario | Behavior |
|----------|----------|
| Env var unset | Returns `[]` (empty list — no restrictions) |
| Env var set to empty string | Returns `[]` |
| Env var set to whitespace only | Returns `[]` |
| Malformed commas (`"uw.edu,,foo"`) | Skips empty entries, returns `["uw.edu", "foo"]` |
| Trailing/leading whitespace | Stripped per domain |
| Mixed case domains | Lowercased consistently |

## 7. Backward Compatibility

| Aspect | Compatible? | Reason |
|--------|-------------|--------|
| Existing `settings.ALLOWED_EMAIL_DOMAINS` consumers | Yes | Value is still a `list[str]` — same type |
| `getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])` | Yes | `getattr` with default still works |
| `self.settings()` in tests | Yes | Test context manager overrides work regardless of source |
| Existing deployments without env var | Yes | Falls back to `[]` (was `["uw.edu"]`) — **note**: this is a behavior change, no restrictions by default |

> **⚠️ Default changes**: The default changes from `["uw.edu"]` to `[]` (no restrictions). To preserve the existing behavior for existing deployments, set `ALLOWED_EMAIL_DOMAINS=uw.edu` in the environment. The `.env.example` documents `uw.edu` as the default, so developers and operators see the expected value.

## 8. Implementation Order

1. Add `parse_allowed_email_domains()` to `src/accounts/utils.py`
2. Update `src/llteacher/settings.py` to use it
3. Update `src/llteacher/production.py` to use it
4. Update hardcoded error message in `src/accounts/forms.py`
5. (Optional) Add `load_dotenv()` to `manage.py`
6. Create `.env.example`
7. Add tests to `test_domain_validation.py`
8. Run full test suite
9. Commit

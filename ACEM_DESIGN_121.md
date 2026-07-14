# Design Document: ALLOWED_EMAIL_DOMAINS as Env Variable

## Summary

Replace the hardcoded `ALLOWED_EMAIL_DOMAINS = ["uw.edu"]` in both settings files with runtime parsing from the `ALLOWED_EMAIL_DOMAINS` environment variable, keeping `["uw.edu"]` as the default fallback and supporting empty-string semantics (allow all domains).

---

## Requirements (from Issue + Feedback)

| Requirement | Detail |
|---|---|
| **Env-variable driven** | `ALLOWED_EMAIL_DOMAINS` setting must be read from an env variable |
| **Default fallback** | When the env var is not set → `["uw.edu"]` |
| **Empty = allow-all** | When the env var is set to `""` (empty string) → `[]` (no restrictions) |
| **Comma-separated** | Multiple domains separated by commas, whitespace trimmed |
| **Existing behavior preserved** | Validated emails still support exact match + subdomain matching |

---

## Files to Modify

### 1. `src/accounts/utils.py` — Add `parse_allowed_email_domains()`

Add a public helper function that encapsulates the parsing logic. This keeps the email-domain concern inside the `accounts` app (where `is_email_domain_allowed` already lives).

**New function:**

```python
import os


def parse_allowed_email_domains() -> list[str]:
    """
    Parse the ALLOWED_EMAIL_DOMAINS environment variable.

    Behavior:
        - Env var not set   → fallback to ['uw.edu']
        - Env var is ""     → [] (allow all domains)
        - Env var is "uw.edu" → ['uw.edu']
        - Env var is "uw.edu,washington.edu" → ['uw.edu', 'washington.edu']
        - Whitespace around values is stripped.

    Returns:
        list[str]: Parsed list of allowed domains (lowercased).
    """
    raw = os.getenv("ALLOWED_EMAIL_DOMAINS")
    if raw is None:
        return ["uw.edu"]
    if raw.strip() == "":
        return []
    return [domain.strip().lower() for domain in raw.split(",") if domain.strip()]
```

**Edge cases handled:**
- `raw is None` (variable never exported) → `["uw.edu"]`
- `raw = ""` → `[]`
- `raw = "uw.edu"` → `["uw.edu"]`
- `raw = "UW.EDU"` → `["uw.edu"]` (lowercased)
- `raw = " uw.edu , Washington.EDU "` → `["uw.edu", "washington.edu"]`
- `raw = "uw.edu,"` → `["uw.edu"]` (trailing comma, empty segment filtered)
- `raw = ",,"` → `[]` (all segments empty after strip)

---

### 2. `src/llteacher/settings.py` — Replace hardcoded value

**Line 117 (currently):**
```python
ALLOWED_EMAIL_DOMAINS = ["uw.edu"]
```

**Replace with:**
```python
from accounts.utils import parse_allowed_email_domains

ALLOWED_EMAIL_DOMAINS = parse_allowed_email_domains()
```

---

### 3. `src/llteacher/production.py` — Replace hardcoded value

**Line 153 (currently):**
```python
ALLOWED_EMAIL_DOMAINS = ["uw.edu"]
```

**Replace with:**
```python
from accounts.utils import parse_allowed_email_domains

ALLOWED_EMAIL_DOMAINS = parse_allowed_email_domains()
```

---

### 4. `manage.py` — Add `load_dotenv()` call

Python-dotenv is already listed in `pyproject.toml` as a dependency but is never invoked. Adding `load_dotenv()` to `manage.py` ensures that a `.env` file placed next to `manage.py` is loaded before Django settings are evaluated.

**Add to `manage.py` (at the top of `main()`, before `setdefault`):**

```python
from dotenv import load_dotenv


def main():
    """Run administrative tasks."""
    load_dotenv()  # Load .env before accessing settings
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "llteacher.settings")
    ...
```

**Note:** `wsgi.py` and `asgi.py` may also need `load_dotenv()` if they are the entry point in production. However, production uses Docker, and env variables are injected via Docker environment, not a `.env` file. The `manage.py` change covers development and local testing.

---

### 5. `.env.example` — Create example file

Create a new file at the project root:

```
# Email domain restrictions for registration.
# Comma-separated list of allowed email domains (subdomains are automatically allowed).
# Leave empty to allow all domains.
# Default (when not set): uw.edu
# ALLOWED_EMAIL_DOMAINS=uw.edu,washington.edu
```

---

### 6. `src/accounts/forms.py` — Make error messages dynamic (recommended)

The current hardcoded error messages reference "University of Washington / @uw.edu" even when other domains are configured. This should be made dynamic.

**`RegistrationForm.__init__`** (lines 52-53): The title/pattern generation already uses the actual domain names — no change needed for the client-side pattern.

**`RegistrationForm.clean_email`** (lines 120-122): Replace:

```python
raise ValidationError(
    "Email must be from University of Washington domain (@uw.edu or subdomain). "
    "Please use your UW email address."
)
```

With a dynamic message:

```python
allowed_domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])
if allowed_domains:
    domain_list = ", ".join(f"@{d}" for d in allowed_domains)
    msg = (
        f"Email must be from an allowed domain ({domain_list} or subdomain). "
        f"Please use an email address from one of the allowed domains."
    )
else:
    msg = "Email domain is not allowed."
raise ValidationError(msg)
```

**`ProfileForm.clean_email`** (lines 206-208): Apply the same dynamic message pattern.

---

### 7. `test_settings.py` — No change needed

`test_settings.py` inherits from `settings.py` via `from .settings import *`, so `ALLOWED_EMAIL_DOMAINS` will automatically resolve through `parse_allowed_email_domains()`. When tests run, the env var is typically unset, so the default `["uw.edu"]` will be used — preserving existing test behavior.

For tests that need different domain configurations, `self.settings(ALLOWED_EMAIL_DOMAINS=[...])` continues to work as before because `override_settings` replaces the attribute after import.

---

## Testing

### New tests for `parse_allowed_email_domains()`

Add to `src/accounts/tests/test_domain_validation.py`:

```python
class TestParseAllowedEmailDomains(TestCase):
    """Test env-var parsing for ALLOWED_EMAIL_DOMAINS."""

    def test_env_var_not_set_returns_default(self):
        """When env var is absent, fallback to ['uw.edu']."""
        with self.settings(ALLOWED_EMAIL_DOMAINS=parse_allowed_email_domains()):
            from django.conf import settings
            self.assertEqual(settings.ALLOWED_EMAIL_DOMAINS, ["uw.edu"])

    @patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": ""})
    def test_empty_string_returns_empty_list(self):
        """When env var is empty, return [] (allow all)."""
        self.assertEqual(parse_allowed_email_domains(), [])

    @patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": "uw.edu"})
    def test_single_domain(self):
        self.assertEqual(parse_allowed_email_domains(), ["uw.edu"])

    @patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": "uw.edu,washington.edu"})
    def test_multiple_domains(self):
        self.assertEqual(
            parse_allowed_email_domains(), ["uw.edu", "washington.edu"]
        )

    @patch.dict(os.environ, {"ALLOWED_EMAIL_DOMAINS": "  UW.EDU , Washington.EDU  "})
    def test_whitespace_and_case(self):
        self.assertEqual(
            parse_allowed_email_domains(), ["uw.edu", "washington.edu"]
        )
```

**Note:** The `@patch.dict` decorator requires `from unittest.mock import patch`. Alternatively, these tests can simply call `parse_allowed_email_domains()` directly as a unit test without Django settings involvement (since the function only uses `os.getenv`).

### Existing test adjustments

- `test_settings_configuration` (line 240-245): Uses `getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])` and checks `"uw.edu" in allowed_domains`. With the default fallback still `["uw.edu"]`, this test passes unchanged.
- `test_no_allowed_domains_setting` (line 247-262): Already uses `self.settings(ALLOWED_EMAIL_DOMAINS=[])` → passes unchanged.
- `TestClientSideValidationPatterns`: All use `self.settings(ALLOWED_EMAIL_DOMAINS=[...])` → passes unchanged.

### Test command

Run using the canonical test command:

```bash
uv run coverage run manage.py test --settings=src.llteacher.test_settings src
```

---

## Migration / Rollout

| Step | Action |
|---|---|
| 1 | Add `parse_allowed_email_domains()` to `accounts/utils.py` |
| 2 | Update both settings files to use the new function |
| 3 | Add `load_dotenv()` to `manage.py` |
| 4 | Create `.env.example` |
| 5 | Update error messages in `forms.py` (recommended) |
| 6 | Write tests for `parse_allowed_email_domains()` |
| 7 | Run full test suite to confirm no regressions |
| 8 | Document the new env variable in deployment docs |

No database migrations are required — this is a runtime configuration change only.

---

## Future Considerations

- **`wsgi.py` / `asgi.py`**: If a `.env` file is needed in production (non-Docker deployments), `load_dotenv()` should be added there too.
- **`docker-compose.yml`**: If one is added to the project, the `ALLOWED_EMAIL_DOMAINS` variable should be listed under `environment:` for visibility.
- **Instrumentation**: The new env variable could be logged at startup for debugging (e.g., `logger.info("Allowed email domains: %s", ALLOWED_EMAIL_DOMAINS)`) — though this is beyond the current scope.

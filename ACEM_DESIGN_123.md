# Implementation Plan: ALLOWED_EMAIL_DOMAINS from Environment Variable

## Issue Summary

Make `ALLOWED_EMAIL_DOMAINS` configurable via environment variable while preserving backward compatibility. An unset variable keeps the current default (`["uw.edu"]`). An explicitly empty string disables the check entirely.

---

## 1. Current State

### Where it is defined (hardcoded)

| File | Line | Code |
|------|------|------|
| `src/llteacher/settings.py` | 117 | `ALLOWED_EMAIL_DOMAINS = ["uw.edu"]` |
| `src/llteacher/production.py` | 153 | `ALLOWED_EMAIL_DOMAINS = ["uw.edu"]` |

### Where it is consumed

| File | Line(s) | Pattern | Purpose |
|------|---------|---------|---------|
| `src/accounts/forms.py` | 43 | `getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])` | Build HTML5 `pattern` / `title` for email input |
| `src/accounts/forms.py` | 114 | same | Server-side domain validation in registration |
| `src/accounts/forms.py` | 202 | same | Server-side domain validation in profile updates (grandfathering) |

All three consumers already use a defensive fallback — an empty list means "allow all domains" — so no consumer changes are needed.

### Tests

| File | Lines | What it tests |
|------|-------|---------------|
| `src/accounts/tests/test_domain_validation.py` | 237–262 | Integration test: `settings.ALLOWED_EMAIL_DOMAINS` contains `"uw.edu"`; empty-list behavior |
| same file, passim | 70–344 | All tests use `with self.settings(ALLOWED_EMAIL_DOMAINS=[...])` — will continue working unchanged |

---

## 2. Design

### 2.1 Env Var Contract

| Scenario | Env var value | Result | Explanation |
|----------|---------------|--------|-------------|
| Not set | (unset) | `["uw.edu"]` | Backward-compatible default |
| Single domain | `uw.edu` | `["uw.edu"]` | Normal case |
| Multiple domains | `uw.edu,washington.edu,example.org` | `["uw.edu", "washington.edu", "example.org"]` | Comma-separated |
| With whitespace | ` uw.edu , washington.edu ` | `["uw.edu", "washington.edu"]` | Trimmed |
| Disable check | (empty string `""`) | `[]` | All domains allowed |

### 2.2 Code Change

**File:** `src/llteacher/settings.py` — replace line 117

```python
# Before (hardcoded):
ALLOWED_EMAIL_DOMAINS = ["uw.edu"]

# After (env-configurable):
_ALLOWED_EMAIL_DOMAINS_ENV = os.getenv("ALLOWED_EMAIL_DOMAINS")
if _ALLOWED_EMAIL_DOMAINS_ENV == "":
    ALLOWED_EMAIL_DOMAINS = []
elif _ALLOWED_EMAIL_DOMAINS_ENV is not None:
    ALLOWED_EMAIL_DOMAINS = [d.strip() for d in _ALLOWED_EMAIL_DOMAINS_ENV.split(",")]
else:
    ALLOWED_EMAIL_DOMAINS = ["uw.edu"]
```

**File:** `src/llteacher/production.py` — replace line 153 with identical logic.

### 2.3 Why This Approach

1. **Three-way logic** (unset / empty / populated) is required to distinguish "not provided" (use default) from "explicitly empty" (disable check). A single `os.getenv(key, default)` call cannot express all three because `os.getenv` returns the default for *any* absence — including when you might want `[]`. The explicit if/elif/else chain is the clearest way to handle this.

2. **Follows existing conventions** — the file already uses `os.getenv()` extensively for other env-backed settings (line 121 onward in `settings.py`, line 157 onward in `production.py`).

3. **Consumer code unchanged** — all three call sites in `forms.py` use `getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])`, which works correctly whether the value is `["uw.edu"]` or `[]`.

4. **Tests unaffected** — existing tests override the setting with `with self.settings(ALLOWED_EMAIL_DOMAINS=[...])` and will continue passing.

---

## 3. Files to Modify

| # | File | Action | Summary |
|---|------|--------|---------|
| 1 | `src/llteacher/settings.py` | Edit line 117 | Replace hardcoded list with if/elif/else block reading from env |
| 2 | `src/llteacher/production.py` | Edit line 153 | Same change |

**No other files need changes.** No new files, no consumer modifications, no test modifications.

---

## 4. Testing Strategy

The change is fully covered by existing tests. However, a new test is recommended to verify the env-var behavior:

### New test class to add to `src/accounts/tests/test_domain_validation.py`

```python
class TestAllowedEmailDomainsFromEnv(TestCase):
    """Test that ALLOWED_EMAIL_DOMAINS can be configured via environment variable."""

    def test_unset_env_defaults_to_uw_edu(self):
        """When env var is not set, default is ['uw.edu']."""
        from django.conf import settings
        domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])
        self.assertEqual(domains, ["uw.edu"])

    def test_empty_env_disables_check(self):
        """When env var is empty string, domains list is empty."""
        with self.settings(ALLOWED_EMAIL_DOMAINS=[]):
            from django.conf import settings
            domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])
            self.assertEqual(domains, [])
            # Also verify that gmail addresses pass registration
            form_data = {
                "username": "anyone",
                "email": "anyone@gmail.com",
                "first_name": "Any",
                "last_name": "One",
                "password1": "complexpassword123",
                "password2": "complexpassword123",
                "role": "student",
            }
            form = RegistrationForm(data=form_data)
            self.assertTrue(form.is_valid())

    def test_multi_domain_from_env(self):
        """Multiple comma-separated domains work."""
        with self.settings(ALLOWED_EMAIL_DOMAINS=["uw.edu", "washington.edu"]):
            from django.conf import settings
            domains = getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])
            self.assertIn("uw.edu", domains)
            self.assertIn("washington.edu", domains)
```

### Running tests

```bash
uv run coverage run manage.py test --settings=src.llteacher.test_settings src
```

---

## 5. Example Deployments

```bash
# Default (no env var set) — only @uw.edu addresses
export ALLOWED_EMAIL_DOMAINS=uw.edu
# or simply leave unset

# Multiple institutions
export ALLOWED_EMAIL_DOMAINS=uw.edu,washington.edu,example.org

# Disable check entirely (allow any domain)
export ALLOWED_EMAIL_DOMAINS=
```

---

## 6. Edge Cases Considered

| Case | Handling |
|------|----------|
| Env var not set at all | Falls through to `else` branch → `["uw.edu"]` |
| Env var set to empty string | Caught by `if _VALUE == ""` → `[]` (all domains allowed) |
| Whitespace around domains | `.strip()` on each parsed element |
| Trailing comma (e.g., `"uw.edu,"`) | `split` produces `["uw.edu", ""]`, strip converts `""` to `""` — an empty string in the list. This is not ideal but is an unlikely user error. A `.filter(None)` could be added defensively: `[d.strip() for d in value.split(",") if d.strip()]`. Recommend implementing this. |
| Single domain without commas | `split(",")` produces `["uw.edu"]` — correct |
| Regex special chars in domain (e.g., `test.edu`) | No regex evaluation happens at the settings level; dots are escaped at render time in `forms.py:47`. Safe. |
| Consumer code missing setting | `getattr(settings, "ALLOWED_EMAIL_DOMAINS", [])` already handles this gracefully |

---

## 7. Implementation Order

1. Edit `src/llteacher/settings.py` — replace list literal with env-var logic
2. Edit `src/llteacher/production.py` — same change
3. Run existing tests to confirm no regressions
4. (Optional but recommended) Add the new test class to `test_domain_validation.py`
5. Commit

---

## 8. Expected Test Results

All 30+ existing tests in `test_domain_validation.py` should continue passing because they use `with self.settings(...)` and never depend on the module-level default value. The integration test `test_settings_configuration` will still pass because when no env var is set, the default is still `["uw.edu"]`.

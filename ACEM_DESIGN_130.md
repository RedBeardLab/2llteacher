# Design Document: Set Default Key for Populate DB Command

**Issue**: When passing an OpenRouter key to the `populate_test_database` management command, the key should be stored as a default so that new LLM configurations created via the UI are pre-filled with a valid key.

## 1. Summary

The `populate_test_database --api-key <key>` command currently creates `LLMConfig` records with the provided key, but the key is discarded after the command runs. There is no mechanism to persist the key for future use, so teachers creating new LLM configurations via the UI must always retype the key.

This design adds a persistence layer using the existing `GlobalLLMDefault` model, which already has an `api_key` field and serves as a template for course-scoped configs. The populate command will update the `GlobalLLMDefault` record with the provided key, and the create config form will pre-fill the API key field from that record.

## 2. Files to Modify

| File | Change |
|------|--------|
| `src/llteacher/management/commands/populate_test_database.py` | Store the resolved API key in `GlobalLLMDefault` |
| `src/llm/views.py` | Pre-fill API key in create form from `GlobalLLMDefault` |
| `src/llm/templates/llm/config_form.html` | Display default API key when creating new config |
| `src/llm/services.py` | Add a `get_default_api_key()` service method |
| `src/llm/tests/test_views.py` | Add tests for default API key pre-fill |
| `src/llm/tests/test_services.py` | Add tests for `get_default_api_key()` |

## 3. Detailed Design

### 3.1. Populate Command: Store Key in GlobalLLMDefault

**File**: `src/llteacher/management/commands/populate_test_database.py`

**Change**: After resolving the API key, create or update a `GlobalLLMDefault` record with the key. This ensures the key persists in the database for future use.

**New method**:

```python
def set_default_api_key(self, api_key):
    """Store the API key in GlobalLLMDefault for future use."""
    defaults = GlobalLLMDefault.objects.filter(is_active=True)
    if defaults.exists():
        default = defaults.first()
        default.api_key = api_key
        default.save(update_fields=["api_key"])
    else:
        GlobalLLMDefault.objects.create(
            name="Default Configuration",
            model_name="gpt-4o-mini",
            api_key=api_key,
            base_prompt="You are an AI tutor helping students learn programming.",
            temperature=0.7,
            max_completion_tokens=1000,
            is_active=True,
        )
```

**Modified `handle()` method**:

```python
def handle(self, *args, **options):
    api_key = self.resolve_api_key(options["api_key"])
    self.set_default_api_key(api_key)  # NEW: persist key for future use
    # ... rest of method unchanged
```

**Edge cases**:
- If `GlobalLLMDefault` already exists with a different name/model, we only update the `api_key` field — other fields are preserved.
- If no `GlobalLLMDefault` exists, we create one with sensible defaults. The `model_name` defaults to `"gpt-4o-mini"` (the recommended model in the UI). The `base_prompt` uses a minimal default tutor prompt.

**Why this approach**: The `GlobalLLMDefault` model is the natural place for a "sticky" default key because:
- It already has an `api_key` field
- It is already used as a template for creating course-scoped configs via `create_course_config()`
- It is a singleton pattern (one active record at a time)

### 3.2. Service Layer: Add get_default_api_key()

**File**: `src/llm/services.py`

**New method on `LLMService`**:

```python
@staticmethod
@traced
def get_default_api_key() -> Optional[str]:
    """Get the default API key from the active GlobalLLMDefault record.

    Returns:
        The API key string if a GlobalLLMDefault exists, None otherwise.
    """
    from .models import GlobalLLMDefault

    try:
        default = GlobalLLMDefault.objects.filter(is_active=True).first()
        if default and default.api_key:
            return default.api_key
        return None
    except Exception as e:
        logger.error(f"Error getting default API key: {str(e)}")
        record_exception(e)
        return None
```

**Design notes**:
- Returns `Optional[str]` (None if no active `GlobalLLMDefault` exists or its key is empty).
- Uses `@traced` for observability, consistent with other service methods.
- Catches exceptions gracefully, consistent with patterns in `LLMService`.

### 3.3. Create View: Pre-fill API Key from GlobalLLMDefault

**File**: `src/llm/views.py`

**Change 1**: Add `default_api_key` to `LLMConfigFormData` dataclass.

```python
@dataclass
class LLMConfigFormData:
    config: Optional[LLMConfigData] = None
    is_edit: bool = False
    form_title: str = "Create LLM Configuration"
    course_id: Optional[UUID] = None
    courses: List[dict] | None = None
    default_api_key: Optional[str] = None  # NEW
```

**Change 2**: Modify `LLMConfigCreateView._get_form_data()` to populate `default_api_key`.

```python
def _get_form_data(self, course_id: UUID) -> LLMConfigFormData:
    from courses.models import Course

    try:
        course = Course.objects.get(id=course_id)
        courses = [{"id": str(course.id), "name": course.name}]
    except Course.DoesNotExist:
        courses = []

    # NEW: fetch default API key for pre-fill
    default_api_key = LLMService.get_default_api_key()

    return LLMConfigFormData(
        is_edit=False,
        form_title="Create LLM Configuration",
        course_id=course_id,
        courses=courses,
        default_api_key=default_api_key,  # NEW
    )
```

**Design notes**:
- The key is only pre-filled in **create mode** (not edit mode).
- In edit mode, the existing config's `api_key` is already shown via `data.config.api_key`.
- If no `GlobalLLMDefault` exists, `default_api_key` is `None` and no pre-fill occurs.

### 3.4. Template: Display Default API Key

**File**: `src/llm/templates/llm/config_form.html`

**Change**: Modify the API key input field to fall back to `data.default_api_key` when no existing config or submitted form data is available.

```html
<div class="mb-3">
    <label for="api_key" class="form-label">OpenRouter API Key *</label>
    <input type="password" class="form-control" id="api_key" name="api_key" 
           value="{% if data.config %}{{ data.config.api_key }}{% elif form_data %}{{ form_data.api_key }}{% elif data.default_api_key %}{{ data.default_api_key }}{% endif %}" 
           required>
    <div class="form-text">Your OpenRouter API key (will be stored securely)</div>
</div>
```

**Priority order** (highest to lowest):
1. `data.config.api_key` — existing config (edit mode)
2. `form_data.api_key` — previously submitted form data (POST failure)
3. `data.default_api_key` — global default key (fresh create form)
4. (empty) — fallback if no default exists

### 3.5. Create View Validation: Fall Back to Default Key

**File**: `src/llm/views.py`

**Change**: In `LLMConfigCreateView._create_config()`, if the submitted API key is empty, fall back to the default key from `GlobalLLMDefault` before returning an error.

```python
def _create_config(self, data: LLMConfigCreateData) -> LLMConfigCreateResult:
    if not data.name:
        return LLMConfigCreateResult(success=False, error="Name is required.")
    if not data.model_name:
        return LLMConfigCreateResult(success=False, error="Model name is required.")
    if not data.api_key:
        # NEW: fall back to default key before rejecting
        default_key = LLMService.get_default_api_key()
        if default_key:
            data.api_key = default_key
        else:
            return LLMConfigCreateResult(
                success=False, error="API key is required."
            )
    if not data.base_prompt:
        return LLMConfigCreateResult(
            success=False, error="Base prompt is required."
        )

    return LLMService.create_config(data)
```

**Why this fallback is needed**: If a user clears the pre-filled API key field and submits, the validation would reject it. The fallback ensures the default key is still used even if the field is cleared. This is important because:
- The field is `type="password"`, so the pre-filled value is obscured
- A user might accidentally clear it while typing other fields
- The intent of the "default key" feature is that the key should be automatically available

### 3.6. Edit View: No Change Needed

The edit view (`LLMConfigEditView`) already preserves the existing `api_key` when the field is left empty (lines 340-342 of `views.py`):

```python
api_key = request.POST.get("api_key")
if api_key:
    data["api_key"] = api_key.strip()
```

This means the existing key is kept when the edit form is submitted without changing the key. No change is needed here.

## 4. Testing

### 4.1. Tests for populate command

Create a new test file or add to an existing test module for the populate command:

```python
# src/llteacher/tests/test_populate_database.py

from django.test import TestCase
from django.core.management import call_command
from io import StringIO
from llm.models import GlobalLLMDefault


class PopulateDatabaseCommandTest(TestCase):
    def test_command_stores_api_key_in_global_default(self):
        """Test that --api-key stores the key in GlobalLLMDefault."""
        out = StringIO()
        call_command("populate_test_database", "--api-key=sk-test-key-123", stdout=out)

        default = GlobalLLMDefault.objects.filter(is_active=True).first()
        self.assertIsNotNone(default)
        self.assertEqual(default.api_key, "sk-test-key-123")

    def test_command_updates_existing_global_default_key(self):
        """Test that running the command twice updates the key."""
        GlobalLLMDefault.objects.create(
            name="Existing",
            model_name="gpt-4",
            api_key="old-key",
            is_active=True,
        )

        out = StringIO()
        call_command("populate_test_database", "--api-key=new-key-456", stdout=out)

        default = GlobalLLMDefault.objects.filter(is_active=True).first()
        self.assertEqual(default.api_key, "new-key-456")
        self.assertEqual(default.name, "Existing")  # other fields preserved
```

### 4.2. Tests for get_default_api_key()

**File**: `src/llm/tests/test_services.py`

```python
class TestGetDefaultAPIKey(LLMServiceTestCase):
    def test_get_default_api_key_returns_key(self):
        """Test that the default API key is returned."""
        from llm.models import GlobalLLMDefault

        GlobalLLMDefault.objects.create(
            name="Global Default",
            model_name="gpt-4",
            api_key="global-key-789",
            is_active=True,
        )

        key = LLMService.get_default_api_key()
        self.assertEqual(key, "global-key-789")

    def test_get_default_api_key_returns_none_when_no_default(self):
        """Test that None is returned when no GlobalLLMDefault exists."""
        key = LLMService.get_default_api_key()
        self.assertIsNone(key)

    def test_get_default_api_key_returns_none_when_key_empty(self):
        """Test that None is returned when the default has an empty key."""
        from llm.models import GlobalLLMDefault

        GlobalLLMDefault.objects.create(
            name="Global Default",
            model_name="gpt-4",
            api_key="",
            is_active=True,
        )

        key = LLMService.get_default_api_key()
        self.assertIsNone(key)
```

### 4.3. Tests for Create View Pre-fill

**File**: `src/llm/tests/test_views.py`

```python
class TestLLMConfigCreateViewDefaultKey(LLMViewsTestCase):
    def test_create_form_prefills_api_key(self):
        """Test that the create form pre-fills the API key from GlobalLLMDefault."""
        self.client.login(username="teacher", password="testpass123")

        response = self.client.get(
            reverse("llm:config-create", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "global-api-key")

    def test_create_form_has_no_prefill_when_no_global_default(self):
        """Test that no pre-fill occurs when no GlobalLLMDefault exists."""
        from llm.models import GlobalLLMDefault

        GlobalLLMDefault.objects.all().delete()

        self.client.login(username="teacher", password="testpass123")

        response = self.client.get(
            reverse("llm:config-create", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 200)
        # The API key field should not contain the old key
        self.assertNotContains(response, "global-api-key")

    def test_create_config_without_providing_key_uses_default(self):
        """Test that creating a config without an API key falls back to the default."""
        self.client.login(username="teacher", password="testpass123")

        form_data = {
            "name": "Default Key Config",
            "model_name": "gpt-4",
            "api_key": "",  # Intentionally empty
            "base_prompt": "You are a test tutor.",
            "temperature": 0.7,
            "max_completion_tokens": 1000,
            "is_default": False,
        }

        response = self.client.post(
            reverse("llm:config-create", kwargs={"course_id": self.course.id}),
            form_data,
        )

        self.assertEqual(response.status_code, 302)

        new_config = LLMConfig.objects.get(
            name="Default Key Config", course=self.course
        )
        self.assertEqual(new_config.api_key, "global-api-key")
```

## 5. Edge Cases

| Edge Case | Handling |
|-----------|----------|
| No `GlobalLLMDefault` exists | `get_default_api_key()` returns `None`; form shows empty field; create validation rejects empty key |
| `GlobalLLMDefault` has empty `api_key` | `get_default_api_key()` returns `None` |
| Multiple `GlobalLLMDefault` records | `.filter(is_active=True).first()` picks the first active one |
| User clears pre-filled key and submits | Fallback in `_create_config()` catches empty key and uses default |
| Populate command runs without `--api-key` | `resolve_api_key()` returns placeholder; that placeholder is stored in `GlobalLLMDefault` (existing behavior) |
| Edit mode shows pre-filled key | No change; edit mode already shows existing config key, never the global default |
| Non-ASCII API key | The existing `LLMConfigData.from_model()` already logs a warning for non-ASCII keys; no change needed |

## 6. Data Flow

```
populate_test_database --api-key <key>
    │
    ├─ resolve_api_key()          → returns key (or placeholder)
    ├─ set_default_api_key(key)   → creates/updates GlobalLLMDefault.api_key
    └─ create_llm_configs()       → creates LLMConfig records with key

Teacher visits "Create LLM Configuration" page
    │
    ├─ _get_form_data()           → calls LLMService.get_default_api_key()
    ├─ LLMConfigFormData          → includes default_api_key
    └─ Template renders           → <input value="{{ data.default_api_key }}">

Teacher submits form without API key
    │
    ├─ _create_config()           → data.api_key is empty
    ├─ get_default_api_key()      → returns key from GlobalLLMDefault
    ├─ data.api_key = key         → filled silently
    └─ LLMService.create_config() → creates config with default key
```

## 7. Migration

No database migration is required. The `GlobalLLMDefault` model already has an `api_key` field. The change is purely in application logic.

## 8. Implementation Order

1. Add `get_default_api_key()` to `LLMService` in `services.py`
2. Add `set_default_api_key()` to populate command in `populate_test_database.py`
3. Add `default_api_key` to `LLMConfigFormData` and update `_get_form_data()` in `views.py`
4. Add fallback in `_create_config()` in `views.py`
5. Update template `config_form.html` to show `default_api_key`
6. Write tests for all changes
7. Run existing tests to verify no regressions
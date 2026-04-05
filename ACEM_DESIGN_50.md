# Implementation Plan: Filter LLM Configs by Course in Homework Edit View

## Issue Summary

**Title**: LLM config in editing of homework shows all available configs instead of only those belonging to the course

**Problem**: When editing an existing homework assignment, the `HomeworkEditForm` displays ALL active LLM configs in the system, rather than filtering to only show LLM configs that belong to the homework's course. This is inconsistent with homework creation, which correctly filters LLM configs by course.

**Expected Behavior**: When editing a homework, the LLM config dropdown should only show LLMConfigs that belong to the homework's course (same as during creation).

---

## Current Code Analysis

### 1. Homework Creation (Correct Behavior)

**File**: `src/homeworks/forms.py` - `HomeworkCreateForm`

```python
def __init__(self, *args, **kwargs):
    course = kwargs.pop("course", None)
    super().__init__(*args, **kwargs)
    self.fields["llm_config"].required = False

    if course:
        from llm.models import LLMConfig
        self.fields["llm_config"].queryset = LLMConfig.objects.filter(
            course=course, is_active=True
        ).order_by("name")
```

When creating a homework, the form receives the `course` as a kwarg and filters LLM configs accordingly.

### 2. Homework Editing (Bug)

**File**: `src/homeworks/forms.py` - `HomeworkEditForm`

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields["llm_config"].required = False
    # NOTE: No course filtering is performed!
```

The edit form does NOT filter LLM configs by course. Since `HomeworkEditForm` is always used with a `Homework` instance (via `instance=homework`), we can access the course through `self.instance.course`.

---

## Implementation Plan

### Step 1: Modify `HomeworkEditForm.__init__()` in `src/homeworks/forms.py`

Add course-based filtering to the LLM config queryset when an instance exists with a course.

**File**: `src/homeworks/forms.py`
**Location**: Lines 152-158

**Change**:
```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields["llm_config"].required = False

    # Filter LLM configs by course if instance has a course
    if self.instance and self.instance.course:
        from llm.models import LLMConfig
        self.fields["llm_config"].queryset = LLMConfig.objects.filter(
            course=self.instance.course, is_active=True
        ).order_by("name")
```

### Step 2: Add Unit Test

**File**: `src/homeworks/tests/test_edit_view.py`

Add a new test case to verify that the LLM config dropdown only shows configs belonging to the homework's course.

**Test Case**: `HomeworkEditLLMConfigFilterTests`

```python
class HomeworkEditLLMConfigFilterTests(TestCase):
    """Test that LLM configs are filtered by course in the edit view."""

    def setUp(self):
        """Set up test data with multiple courses and LLM configs."""
        # Create teacher
        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="password"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create courses
        from courses.models import Course, CourseTeacher
        self.course = Course.objects.create(name="Test Course", code="TEST101", description="")
        self.other_course = Course.objects.create(name="Other Course", code="OTHER101", description="")

        CourseTeacher.objects.create(course=self.course, teacher=self.teacher, role="owner")
        CourseTeacher.objects.create(course=self.other_course, teacher=self.teacher, role="owner")

        # Create LLM configs for each course
        from llm.models import LLMConfig
        self.course_llm_config = LLMConfig.objects.create(
            name="Course LLM Config",
            course=self.course,
            is_active=True,
        )
        self.other_course_llm_config = LLMConfig.objects.create(
            name="Other Course LLM Config",
            course=self.other_course,
            is_active=True,
        )
        self.global_llm_config = LLMConfig.objects.create(
            name="Global LLM Config",
            course=None,  # Global config
            is_active=True,
        )

        # Create homework assigned to self.course
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            course=self.course,
            due_date=datetime.datetime(2030, 1, 1),
        )

        self.client = Client()
        self.client.login(username="teacher", password="password")
        self.url = reverse("homeworks:edit", kwargs={"homework_id": self.homework.id})

    def test_edit_view_only_shows_course_llm_configs(self):
        """Edit view should only show LLM configs belonging to the homework's course."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        # Get the form from context
        form = response.context["data"].form

        # Get the LLM config queryset from the form
        llm_config_queryset = form.fields["llm_config"].queryset

        # Should contain the course's LLM config
        self.assertIn(self.course_llm_config, llm_config_queryset)

        # Should NOT contain the other course's LLM config
        self.assertNotIn(self.other_course_llm_config, llm_config_queryset)

        # For backward compatibility: global configs (course=None) should NOT be shown
        # since homework is tied to a specific course
        self.assertNotIn(self.global_llm_config, llm_config_queryset)

    def test_edit_view_allows_selecting_course_llm_config(self):
        """Teacher can update homework to use a course LLM config."""
        post_data = {
            "title": "Updated Homework",
            "description": "Updated description",
            "due_date": "2030-02-01T00:00:00",
            "llm_config": str(self.course_llm_config.id),
            "sections-TOTAL_FORMS": "0",
            "sections-INITIAL_FORMS": "0",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
        }

        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 302)

        self.homework.refresh_from_db()
        self.assertEqual(self.homework.llm_config, self.course_llm_config)
```

---

## Edge Cases to Consider

1. **Homework with no course assigned**: If `homework.course` is `NULL`/`None`, the form should either:
   - Show no LLM configs (restrictive approach), OR
   - Show all active LLM configs as a fallback (permissive approach)

   **Decision**: Use the restrictive approach - if homework has no course, don't show any LLM configs. This maintains consistency with the principle that LLM configs should be course-scoped.

2. **LLM config from a different course is already assigned**: When editing a homework that currently has an LLM config from a different course:
   - The dropdown won't show that config (since it filters by homework's course)
   - The selected value won't be in the queryset, which may cause validation issues

   **Decision**: Handle this in the form's `__init__` by including the currently selected config even if it doesn't match the course filter. This ensures backward compatibility when editing existing data.

3. **LLM config is deactivated after being selected**: If the selected LLM config becomes inactive:
   - Similar to edge case 2, include the selected config in the queryset to prevent validation errors

---

## Implementation Details for Edge Case Handling

**Updated `HomeworkEditForm.__init__()`**:

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields["llm_config"].required = False

    # Filter LLM configs by course if instance has a course
    if self.instance and self.instance.course:
        from llm.models import LLMConfig
        queryset = LLMConfig.objects.filter(
            course=self.instance.course, is_active=True
        ).order_by("name")

        # Include currently selected config even if it doesn't match the filter
        # This handles cases where:
        # 1. The homework's course was changed (rare, course is not editable)
        # 2. The previously selected config was deactivated
        if self.instance.llm_config:
            queryset = queryset | LLMConfig.objects.filter(
                id=self.instance.llm_config.id
            )

        self.fields["llm_config"].queryset = queryset
```

---

## Files to Modify

| File | Change |
|------|--------|
| `src/homeworks/forms.py` | Add course filtering in `HomeworkEditForm.__init__()` |
| `src/homeworks/tests/test_edit_view.py` | Add `HomeworkEditLLMConfigFilterTests` class |

---

## Testing Checklist

- [ ] Existing tests still pass
- [ ] New test `test_edit_view_only_shows_course_llm_configs` passes
- [ ] New test `test_edit_view_allows_selecting_course_llm_config` passes
- [ ] Edge case: homework with no course shows no LLM configs
- [ ] Edge case: previously selected config from different course is still accessible

---

## Verification

Run tests with:
```bash
uv run python run_tests.py --settings=src.llteacher.test_settings homeworks.tests.test_edit_view
```

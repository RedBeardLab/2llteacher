# ACEM_DESIGN_38: Filter LLM Configs by Course in Homework Forms

## Issue Summary

**Title**: When creating a homework, teacher can see all the LLM configs

**Problem**: When teachers create or edit homework assignments, the `llm_config` dropdown displays ALL LLM configurations in the system, regardless of which course they belong to. Teachers should only see LLM configs associated with the specific course they're creating homework for.

## Root Cause

The `HomeworkCreateForm` and `HomeworkEditForm` in `src/homeworks/forms.py` do not filter the `llm_config` queryset based on the course context:

1. `HomeworkCreateForm` - Created in `CourseHomeworkCreateView` with only course pre-populated via `initial`, but `llm_config` queryset is not filtered
2. `HomeworkEditForm` - Created with `instance=homework`, but `llm_config` queryset is not filtered to `homework.course`

## Files to Modify

### 1. `src/homeworks/forms.py`

Modify `HomeworkCreateForm` and `HomeworkEditForm` to filter the `llm_config` queryset by course.

#### HomeworkCreateForm Changes

```python
class HomeworkCreateForm(forms.ModelForm):
    class Meta:
        model = Homework
        fields = ["title", "description", "course", "due_date", "llm_config"]
        # ... widgets ...

    def __init__(self, *args, **kwargs):
        self._course = kwargs.pop("course", None)  # Extract course parameter
        super().__init__(*args, **kwargs)
        self.fields["llm_config"].required = False
        
        # Filter llm_config queryset to only show configs for the given course
        if self._course:
            self.fields["llm_config"].queryset = LLMConfig.objects.filter(
                course=self._course, is_active=True
            )
        
        # ... datetime conversion ...
```

#### HomeworkEditForm Changes

```python
class HomeworkEditForm(forms.ModelForm):
    class Meta:
        model = Homework
        fields = ["title", "description", "due_date", "llm_config"]
        # ... widgets ...

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["llm_config"].required = False
        
        # Filter llm_config queryset to only show configs for the homework's course
        if self.instance and self.instance.course:
            self.fields["llm_config"].queryset = LLMConfig.objects.filter(
                course=self.instance.course, is_active=True
            )
        
        # ... datetime conversion ...
```

**Note**: We need to import `LLMConfig` model at the top of the file.

### 2. `src/homeworks/views.py`

#### HomeworkEditView Changes (line ~381)

```python
def _get_view_data(self, request: TeacherRequest, homework: Homework) -> HomeworkFormData:
    """Prepare data for the form view with existing homework data."""
    # Create homework form with instance - queryset filtering happens in form's __init__
    form = HomeworkEditForm(instance=homework)
    # ... rest unchanged ...
```

**No changes needed to `HomeworkEditView`** since `HomeworkEditForm` now self-filters based on `self.instance.course`.

### 3. `src/courses/views.py`

#### CourseHomeworkCreateView Changes (line ~508)

```python
def _get_view_data(self, request: TeacherRequest, course: Course) -> HomeworkFormData:
    """Prepare data for the form view."""
    from homeworks.forms import HomeworkCreateForm, SectionForm, SectionFormSet
    from django.forms import formset_factory

    # Create homework form with course pre-populated and filtered llm_config queryset
    form = HomeworkCreateForm(initial={"course": course}, course=course)
    # ... rest unchanged ...
```

## Edge Cases to Handle

### 1. HomeworkEditForm with no course
If a homework exists with `course=None`, the `llm_config` dropdown should be empty or show a "No configs available" message. This is already handled since `LLMConfig.objects.filter(course=None, is_active=True)` would return an empty queryset.

### 2. LLMConfig with course=None (global configs)
The issue states teachers should only see "LLM config for the course, not all of them." This means we intentionally exclude global configs (configs with `course=None`). If a course has no LLM configs, the dropdown will be empty.

### 3. Inactive LLM configs
Only active configs (`is_active=True`) should be shown, as implemented in the form filters.

### 4. Form submission with invalid llm_config
If a teacher selects an LLM config that doesn't belong to their course (via API manipulation), the form validation should catch this. We should add validation to ensure the selected `llm_config.course == homework.course`.

## Security Considerations

1. **Form validation**: The `clean` method should validate that if `llm_config` is selected, it belongs to the homework's course
2. **Service layer validation**: `HomeworkService.create_homework_with_sections` and `update_homework` should also validate the `llm_config` belongs to the course

## Testing Plan

### Unit Tests

1. **HomeworkCreateForm tests**
   - Test that form accepts `course` parameter
   - Test that `llm_config` queryset is filtered when `course` is provided
   - Test that `llm_config` queryset is NOT filtered when `course` is None
   - Test that only active configs are shown

2. **HomeworkEditForm tests**
   - Test that `llm_config` queryset is filtered by `instance.course`
   - Test that only active configs are shown

3. **Form validation tests**
   - Test that selecting a config from a different course fails validation

### Integration Tests

1. **CourseHomeworkCreateView test**
   - Create two courses with different LLM configs
   - Create homework for course A, verify only course A's configs are available

2. **HomeworkEditView test**
   - Edit homework, verify only the homework's course configs are available

## Implementation Order

1. Modify `src/homeworks/forms.py`:
   - Add `LLMConfig` import
   - Update `HomeworkCreateForm.__init__` to filter by course
   - Update `HomeworkEditForm.__init__` to filter by `self.instance.course`

2. Modify `src/courses/views.py`:
   - Pass `course=course` to `HomeworkCreateForm` constructor in `_get_view_data`

3. Run existing tests to ensure no regressions

4. Add new unit tests for the form queryset filtering

5. Add integration tests for views

## Summary of Changes

| File | Change |
|------|--------|
| `src/homeworks/forms.py` | Add `LLMConfig` import; update `HomeworkCreateForm.__init__` to accept `course` kwarg and filter queryset; update `HomeworkEditForm.__init__` to filter queryset by `self.instance.course` |
| `src/courses/views.py` | Pass `course=course` when instantiating `HomeworkCreateForm` in `CourseHomeworkCreateView._get_view_data` |
| `src/homeworks/views.py` | No changes needed (form handles filtering internally) |

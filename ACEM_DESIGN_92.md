# Design Document: Submitted Assignments Labels

**Issue**: When an overdue assignment has been fully submitted by a student, the label should show "Submitted" (green) instead of "Overdue" (red). Non-submitted overdue assignments should remain red.

**Author**: AI Architect  
**Date**: 2026-05-16

---

## 1. Current Behavior

### 1.1 Homework List Page (student view)

The homework list template (`src/homeworks/templates/homeworks/list.html`) currently has logic that checks `is_submitted` before `is_overdue`:

**Card border** (line 32):
```html
<div class="card h-100 {% if homework.is_submitted %}border-success{% elif homework.is_overdue %}border-danger{% else %}border-primary{% endif %}">
```

**Badge** (lines 53-58):
```html
{% if homework.is_submitted %}
    <span class="badge bg-success">Submitted</span>
{% elif homework.is_overdue %}
    <span class="badge bg-danger">Overdue</span>
{% else %}
    <span class="badge bg-info">Student</span>
{% endif %}
```

This logic is **correct** in its prioritization — it checks `is_submitted` first. However, the `is_submitted` flag may be `False` when all sections are actually submitted, depending on data calculation.

### 1.2 Data Flow for `is_submitted`

1. `HomeworkListView._get_view_data()` calls `HomeworkService.get_student_homework_progress()`
2. The service returns `HomeworkProgressData` containing per-section status
3. The view counts sections with `SectionStatus.SUBMITTED` and sets `is_submitted = True` when all sections are submitted

### 1.3 Current Display Outcome

| Scenario | Badge | Card Border | Correct? |
|----------|-------|-------------|----------|
| Submitted, overdue | Depends on `is_submitted` flag | Depends on `is_submitted` flag | Should be green "Submitted" |
| Not submitted, overdue | "Overdue" (red) | `border-danger` (red) | Yes |
| Submitted, not overdue | "Submitted" (green) | `border-success` (green) | Yes |
| Not submitted, not overdue | "Student" (blue) | `border-primary` (blue) | Yes |

---

## 2. Root Cause Analysis

The core issue is that **when a student has submitted all sections** of a homework that is past its due date, the `is_submitted` flag may not be computed correctly in all cases.

### 2.1 `is_submitted` Calculation in `views.py` (lines 277-279)

```python
is_submitted = (
    total_sections > 0 and completed_sections == total_sections
)
```

This logic depends on:
- `progress_data.sections_progress` containing all sections
- Each section's `status` being `SectionStatus.SUBMITTED`

### 2.2 Potential Failure Modes

1. **Empty homework** (zero sections): `is_submitted` remains `False` (default). No bug here since there's nothing to submit.
2. **Mixed section types**: Non-interactive sections require the service to count `SectionAnswer` records. If the answer exists, status is `SUBMITTED`. This looks correct.
3. **Deleted conversations**: The service filters `is_deleted=False` for conversations, which is correct — a deleted conversation doesn't count as submitted.
4. **Partial submission**: If only some sections are submitted, `is_submitted` is `False`, and if overdue, the badge shows "Overdue". This is **correct** behavior — incomplete work that's overdue should be marked overdue.

### 2.3 Confirmed Issue

After review, the primary issue is **not** in the template logic (which correctly prioritizes `is_submitted`) but rather:

1. **Missing tests** for the submitted+overdue edge case — no existing test verifies that an overdue homework with all-submitted sections shows the correct label.
2. **The `is_submitted` calculation relies on per-section `SectionStatus` from `get_student_homework_progress()`**, which uses different logic for conversation vs. non-interactive sections. Edge cases exist where sections might not be counted.

---

## 3. Proposed Changes

### 3.1 Files to Modify

| File | Change |
|------|--------|
| `src/homeworks/tests/test_views.py` | Add tests for submitted+overdue scenario |
| `src/homeworks/views.py` | No changes needed (logic is correct) |
| `src/homeworks/templates/homeworks/list.html` | No changes needed (logic is correct) |

### 3.2 Detailed Changes

#### 3.2.1 New Test: `test_is_submitted_overdue_scenario`

**File**: `src/homeworks/tests/test_views.py`  
**Location**: After the existing `test_is_submitted_false_when_no_sections_submitted` test (around line 338)

This test should:
1. Create a homework with a **past** due date (overdue)
2. Mock all sections as `SectionStatus.SUBMITTED`
3. Verify that `is_submitted` is `True`
4. Verify that the rendered response contains "Submitted" badge, NOT "Overdue"

```python
@patch("homeworks.services.HomeworkService.get_student_homework_progress")
def test_is_submitted_overrides_overdue_label(self, mock_get_progress):
    """Test that submitted label overrides overdue when all sections submitted."""
    from homeworks.services import SectionStatus

    # Create a homework with past due date to simulate overdue
    self.homework.due_date = timezone.now() - timedelta(days=1)
    self.homework.save()

    # Mock progress data with all sections submitted
    mock_progress_data = MagicMock()
    mock_progress_data.sections_progress = [
        MagicMock(
            id=self.section1.id,
            title=self.section1.title,
            content=self.section1.content,
            order=self.section1.order,
            solution_content=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            status=SectionStatus.SUBMITTED,
            conversation_id=uuid.uuid4(),
        ),
        MagicMock(
            id=self.section2.id,
            title=self.section2.title,
            content=self.section2.content,
            order=self.section2.order,
            solution_content=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            status=SectionStatus.SUBMITTED,
            conversation_id=uuid.uuid4(),
        ),
    ]
    mock_get_progress.return_value = mock_progress_data

    view = HomeworkListView()
    data = view._get_view_data(self.student_user)

    self.assertEqual(len(data.homeworks), 1)
    self.assertTrue(data.homeworks[0].is_submitted)
    self.assertTrue(data.homeworks[0].is_overdue)
    self.assertEqual(data.homeworks[0].completed_percentage, 100)
```

#### 3.2.2 New Integration Test: `test_submitted_overdue_displays_correctly`

Verify the rendered HTML contains the correct badge and card border classes.

```python
@patch("homeworks.services.HomeworkService.get_student_homework_progress")
def test_submitted_overdue_displays_correctly_in_html(self, mock_get_progress):
    """Test that the HTML shows 'Submitted' badge for submitted+overdue homework."""
    from homeworks.services import SectionStatus

    # Set homework as overdue
    self.homework.due_date = timezone.now() - timedelta(days=1)
    self.homework.save()

    mock_progress_data = MagicMock()
    mock_progress_data.sections_progress = [
        MagicMock(
            id=self.section1.id,
            title=self.section1.title,
            content=self.section1.content,
            order=self.section1.order,
            solution_content=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            status=SectionStatus.SUBMITTED,
            conversation_id=uuid.uuid4(),
        ),
        MagicMock(
            id=self.section2.id,
            title=self.section2.title,
            content=self.section2.content,
            order=self.section2.order,
            solution_content=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            status=SectionStatus.SUBMITTED,
            conversation_id=uuid.uuid4(),
        ),
    ]
    mock_get_progress.return_value = mock_progress_data

    self.client.login(username="teststudent", password="password123")
    response = self.client.get(reverse("homeworks:list"))

    self.assertEqual(response.status_code, 200)

    # Should show "Submitted" badge
    self.assertContains(response, '<span class="badge bg-success">Submitted</span>')
    # Should NOT show "Overdue" badge
    self.assertNotContains(response, '<span class="badge bg-danger">Overdue</span>')
    # Card should have border-success, not border-danger
    self.assertContains(response, "border-success")
```

#### 3.2.3 New Test: Non-submitted overdue still shows "Overdue"

```python
@patch("homeworks.services.HomeworkService.get_student_homework_progress")
def test_not_submitted_overdue_shows_overdue(self, mock_get_progress):
    """Test that non-submitted overdue homework still shows Overdue badge."""
    from homeworks.services import SectionStatus

    self.homework.due_date = timezone.now() - timedelta(days=1)
    self.homework.save()

    mock_progress_data = MagicMock()
    mock_progress_data.sections_progress = [
        MagicMock(
            id=self.section1.id,
            title=self.section1.title,
            content=self.section1.content,
            order=self.section1.order,
            solution_content=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            status=SectionStatus.OVERDUE,
            conversation_id=None,
        ),
        MagicMock(
            id=self.section2.id,
            title=self.section2.title,
            content=self.section2.content,
            order=self.section2.order,
            solution_content=None,
            created_at=timezone.now(),
            updated_at=timezone.now(),
            status=SectionStatus.OVERDUE,
            conversation_id=None,
        ),
    ]
    mock_get_progress.return_value = mock_progress_data

    view = HomeworkListView()
    data = view._get_view_data(self.student_user)

    self.assertEqual(len(data.homeworks), 1)
    self.assertFalse(data.homeworks[0].is_submitted)
    self.assertTrue(data.homeworks[0].is_overdue)
    self.assertEqual(data.homeworks[0].completed_percentage, 0)

    self.client.login(username="teststudent", password="password123")
    response = self.client.get(reverse("homeworks:list"))

    # Should show "Overdue" badge
    self.assertContains(response, '<span class="badge bg-danger">Overdue</span>')
    # Card should have border-danger
    self.assertContains(response, "border-danger")
```

---

## 4. Verification Checklist

1. Run the existing test suite to confirm no regressions:
   ```
   uv run coverage run manage.py test --settings=src.llteacher.test_settings src
   ```
2. Verify new tests pass.
3. Manual verification:
   - Create a homework with a past due date (or use `timezone.now() - timedelta(days=1)`)
   - As a student, submit all sections of the homework
   - Verify the homework list shows "Submitted" (green badge, green border)
   - Verify the homework detail page does NOT show "Overdue" at the top if submitted
   - Create another overdue homework with no submissions
   - Verify it shows "Overdue" (red badge, red border)

---

## 5. Edge Cases Considered

| Edge Case | Expected Behavior | Handled? |
|-----------|------------------|----------|
| All sections submitted, homework overdue | Green "Submitted" | ✅ Template logic prioritizes `is_submitted` |
| Some sections submitted, homework overdue | Red "Overdue" | ✅ `is_submitted` is False when incomplete |
| No sections submitted, homework overdue | Red "Overdue" | ✅ |
| All sections submitted, homework not overdue | Green "Submitted" | ✅ |
| Homework has zero sections | No badge (or "Student") | ✅ N/A — no sections to submit |
| Mixed conversation + non-interactive sections, all submitted | Green "Submitted" | ✅ Service handles both types |
| Mixed conversation + non-interactive sections, partially submitted | Red "Overdue" (if overdue) | ✅ |

---

## 6. Summary

The **template logic** in `list.html` already correctly prioritizes `is_submitted` over `is_overdue`. The **data calculation** in `views.py` correctly computes `is_submitted` from per-section status. The issue is that **no test coverage exists** for the submitted+overdue edge case, leaving it vulnerable to regressions.

**Changes required**:
- Add 3 new test methods to `src/homeworks/tests/test_views.py`
- Zero changes to templates, views, or services (they are already correct)

**Files modified**:
- `src/homeworks/tests/test_views.py` — New tests only

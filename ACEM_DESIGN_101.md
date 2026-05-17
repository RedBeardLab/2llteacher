# Implementation Plan: Fix Overdue Label in Course Page

## Problem

On the course detail page (`/courses/<uuid:course_id>/`), students see
"Overdue" badges on homework assignments even after they have submitted
them. The current logic only checks `homework.is_overdue` (whether the
due date has passed), with no awareness of the student's submission
status.

## Desired Behavior

| Condition | Label |
|-----------|-------|
| Student has submitted all sections of the homework | `Submitted` |
| Student has NOT submitted AND due date has passed | `Overdue` |
| Student has NOT submitted AND due date has not passed | (no badge) |
| Teacher/TA viewing the page | Keep existing behavior |

---

## Files to Modify

### 1. `src/courses/views.py` — `HomeworkItem` dataclass + view logic

#### 1a. Add `is_submitted` to `HomeworkItem`

**File:** `src/courses/views.py`, line 276-291

Add a new field:

```python
@dataclass
class HomeworkItem:
    id: UUID
    title: str
    description: str
    due_date: str
    is_draft: bool = False
    is_scheduled: bool = False
    is_overdue: bool = False
    is_submitted: bool = False       # NEW — tracks per-student submission
    is_hidden: bool = False
    is_accessible_to_students: bool = True
    expires_at: Any = None
    publish_at: Any = None
    section_count: int = 0
```

#### 1b. Compute `is_submitted` in `_get_view_data`

**File:** `src/courses/views.py`, lines 432-449

In the homework loop, set `is_submitted` when the user is a student
enrolled in this course. For teachers/TAs, `is_submitted` stays
`False` (the template will ignore it).

**Logic for determining if a homework is fully submitted (per-student):**

A homework has `N` sections. A student has "submitted" the homework
when **every** section has been submitted.

- **Interactive sections** (`section_type = "conversation"`): submitted
  when a `Submission` exists for that section's conversation.
- **Non-interactive sections** (`section_type = "non_interactive"`):
  submitted when a `SectionAnswer` exists for that section.

**Optimal query approach (in bulk):**

```python
from django.db.models import Count, Q
from conversations.models import Submission, SectionAnswer

if is_student_view and student_profile and is_enrolled:
    # Gather all sections for these homeworks in one query
    homework_ids = [hw.id for hw in hw_qs]
    sections = Section.objects.filter(homework_id__in=homework_ids)

    # Count interactive vs non-interactive sections per homework
    interactive_counts = dict(
        sections.filter(section_type="conversation")
        .values("homework_id")
        .annotate(cnt=Count("id"))
        .values_list("homework_id", "cnt")
    )
    non_interactive_counts = dict(
        sections.filter(section_type="non_interactive")
        .values("homework_id")
        .annotate(cnt=Count("id"))
        .values_list("homework_id", "cnt")
    )
    total_counts = dict(
        sections.values("homework_id")
        .annotate(cnt=Count("id"))
        .values_list("homework_id", "cnt")
    )

    # Submitted interactive section IDs
    interactive_ids = list(
        sections.filter(section_type="conversation").values_list("id", flat=True)
    )
    submitted_interactive = set(
        Submission.objects.filter(
            conversation__section_id__in=interactive_ids,
            conversation__user=student_profile.user,
            conversation__is_deleted=False,
        ).values_list("conversation__section_id", flat=True)
    )

    # Submitted non-interactive section IDs
    non_interactive_ids = list(
        sections.filter(section_type="non_interactive").values_list("id", flat=True)
    )
    submitted_non_interactive = set(
        SectionAnswer.objects.filter(
            section_id__in=non_interactive_ids,
            user=student_profile.user,
        ).values_list("section_id", flat=True)
    )

    submitted_section_ids = submitted_interactive | submitted_non_interactive

    # Build a lookup of homework_id -> whether all sections are submitted
    hw_submitted: dict[UUID, bool] = {}
    for hw_id in homework_ids:
        total = total_counts.get(hw_id, 0)
        if total == 0:
            hw_submitted[hw_id] = False
        else:
            # Collect all section IDs for this homework
            hw_section_ids = set(
                sections.filter(homework_id=hw_id).values_list("id", flat=True)
            )
            # A section is "done" if it's in submitted_section_ids
            # or if there are zero required sections of its type
            is_done = hw_section_ids.issubset(submitted_section_ids)
            hw_submitted[hw_id] = is_done
else:
    hw_submitted = {}
```

Then, in the loop that builds `HomeworkItem`:

```python
for hw in hw_qs:
    homeworks.append(
        HomeworkItem(
            ...
            is_overdue=hw.is_overdue,
            is_submitted=hw_submitted.get(hw.id, False),
            ...
        )
    )
```

> **Note:** For teachers/TAs, `hw_submitted` will be empty, so
> `is_submitted` defaults to `False` for all items. The template will
> only show the "Submitted" badge in student-specific scenarios.

---

### 2. `src/courses/templates/courses/detail.html` — Template badge logic

**File:** `src/courses/templates/courses/detail.html`, lines 129-131

**Current code:**
```django
{% if homework.is_overdue and not homework.is_draft %}
<span class="badge bg-danger me-1">Overdue</span>
{% endif %}
```

**Replacement:**
```django
{% if homework.is_submitted and not homework.is_draft %}
<span class="badge bg-success me-1"><i class="bi bi-check-circle"></i> Submitted</span>
{% elif homework.is_overdue and not homework.is_draft %}
<span class="badge bg-danger me-1"><i class="bi bi-exclamation-triangle"></i> Overdue</span>
{% endif %}
```

**Behavior explanation:**

| `is_submitted` | `is_overdue` | Badge shown |
|----------------|--------------|-------------|
| `True` | any | `Submitted` (green) |
| `False` | `True` | `Overdue` (red) |
| `False` | `False` | None |

Only the homework loop (lines 110–144) changes. The rest of the
template is unaffected.

---

### 3. `src/courses/tests/test_views.py` — New test cases

Add to `CourseDetailViewTests` (around line 694).

#### Test 3a: Student sees "Submitted" badge when homework is submitted

```python
def test_student_sees_submitted_badge_when_homework_submitted(self):
    """Test that 'Submitted' badge appears when student submitted all sections."""
    from homeworks.models import Section
    from conversations.models import Conversation, Submission

    # Create a conversation section
    section = Section.objects.create(
        homework=self.homework1,
        title="Section 1",
        content="Content",
        order=1,
        section_type="conversation",
    )
    # Create conversation + submission
    conversation = Conversation.objects.create(
        user=self.student_user,
        section=section,
    )
    Submission.objects.create(conversation=conversation)

    self.client.login(username="teststudent", password="password123")
    response = self.client.get(
        reverse("courses:detail", kwargs={"course_id": self.course.id})
    )

    self.assertContains(response, "Submitted")
    self.assertNotContains(response, "Overdue")
```

#### Test 3b: Student sees "Overdue" when not submitted and past due

```python
def test_student_sees_overdue_badge_when_homework_overdue(self):
    """Test that 'Overdue' badge appears when homework is overdue and not submitted."""
    from django.utils import timezone
    from datetime import timedelta

    # Set homework due_date in the past
    self.homework1.due_date = timezone.now() - timedelta(days=1)
    self.homework1.save()

    self.client.login(username="teststudent", password="password123")
    response = self.client.get(
        reverse("courses:detail", kwargs={"course_id": self.course.id})
    )

    self.assertContains(response, "Overdue")
```

#### Test 3c: Student sees no badge when homework is not past due and not submitted

```python
def test_student_sees_no_badge_when_homework_not_overdue_and_not_submitted(self):
    """Test that no badge appears when not overdue and not submitted."""
    # homework1 is due in 7 days (from setUp), not submitted
    self.client.login(username="teststudent", password="password123")
    response = self.client.get(
        reverse("courses:detail", kwargs={"course_id": self.course.id})
    )

    self.assertNotContains(response, "Overdue")
    self.assertNotContains(response, "Submitted")
```

#### Test 3d: Teacher still sees "Overdue" badge

```python
def test_teacher_sees_overdue_badge_for_overdue_homework(self):
    """Test that teachers still see the 'Overdue' badge (unchanged behavior)."""
    from django.utils import timezone
    from datetime import timedelta

    self.homework1.due_date = timezone.now() - timedelta(days=1)
    self.homework1.save()

    self.client.login(username="testteacher", password="password123")
    response = self.client.get(
        reverse("courses:detail", kwargs={"course_id": self.course.id})
    )

    self.assertContains(response, "Overdue")
```

#### Test 3e: Student sees "Submitted" even when homework is past due

```python
def test_student_sees_submitted_badge_even_when_overdue(self):
    """Test that 'Submitted' takes priority over 'Overdue'."""
    from django.utils import timezone
    from datetime import timedelta
    from homeworks.models import Section
    from conversations.models import Conversation, Submission

    # Set homework due in the past
    self.homework1.due_date = timezone.now() - timedelta(days=1)
    self.homework1.save()

    # Create section + submission
    section = Section.objects.create(
        homework=self.homework1,
        title="Section 1",
        content="Content",
        order=1,
        section_type="conversation",
    )
    conversation = Conversation.objects.create(
        user=self.student_user, section=section,
    )
    Submission.objects.create(conversation=conversation)

    self.client.login(username="teststudent", password="password123")
    response = self.client.get(
        reverse("courses:detail", kwargs={"course_id": self.course.id})
    )

    self.assertContains(response, "Submitted")
    self.assertNotContains(response, "Overdue")
```

---

## Edge Cases

| Case | Behavior |
|------|----------|
| Homework has 0 sections | `is_submitted` = `False` — cannot be "submitted" |
| Homework is a draft (`is_draft=True`) | No badge shown (existing behavior preserved) |
| Homework is hidden | No badge shown (hidden homeworks are filtered from the student query) |
| Homework has mixed section types | Works correctly — both `Submission` (interactive) and `SectionAnswer` (non-interactive) are checked |
| Homework has sections but NONE of them are of type requiring submission | Edge case unlikely in practice; if a non-interactive section has no `SectionAnswer` and is past due, "Overdue" is shown |
| Teacher viewing the course | `is_submitted` stays `False` — template never shows "Submitted" badge for teachers |
| Multiple students, different submission states | Each student sees their own correct badge via `student_profile` |
| Student enrolled in multiple courses with overlapping homeworks | No issue — queries filter by homework IDs scoped to the current course |

## Testing

Run the test suite after implementation:

```bash
uv run coverage run manage.py test --settings=src.llteacher.test_settings src
```

The 5 new test methods above should be added to `CourseDetailViewTests`
in `src/courses/tests/test_views.py`.

## Summary of Changes

| File | Change |
|------|--------|
| `src/courses/views.py` | Add `is_submitted` field to `HomeworkItem` dataclass; compute it per-student in `_get_view_data` |
| `src/courses/templates/courses/detail.html` | Replace single "Overdue" badge logic with "Submitted" / "Overdue" branching |
| `src/courses/tests/test_views.py` | Add 5 new test methods to `CourseDetailViewTests` |

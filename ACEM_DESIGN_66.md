# Design Document: Allow Students to See Course They Are Not Enrolled In

## Issue Summary

**Problem**: When a student tries to view a course they are not enrolled in, they receive a "You do not have access to this course" error (HTTP 403).

**Desired Behavior**: Students should be able to view the course page for any active course, seeing:
- Course name and code
- Course description
- Instructors
- An "Enroll Now" button (if not enrolled)

## Feedback from User

The `user_roles` used in the codebase should not be strings but enums. A new enum for course roles should be created.

## Current Behavior

In `src/courses/views.py`, the `CourseDetailView.get()` method (lines 339-383) checks user roles and returns 403 if the user has no role (teacher, enrolled student, or TA) for the course:

```python
if not user_roles:
    return HttpResponseForbidden("You do not have access to this course.")
```

## Proposed Changes

### 1. Create Course Role Enum

**File**: `src/courses/enums.py` (new file)

```python
from enum import StrEnum


class CourseRole(StrEnum):
    """Enumeration of possible user roles within a course context."""

    TEACHER = "teacher"
    STUDENT = "student"
    TEACHER_ASSISTANT = "teacher_assistant"
```

### 2. Update CourseDetailData Dataclass

**File**: `src/courses/views.py`  
**Location**: Lines 310-323

**Changes**:
- Add `instructors` field
- Add `is_enrolled` flag for template to conditionally show enrollment status
- Update `user_roles` type to use `CourseRole` enum

```python
from .enums import CourseRole  # Add import

@dataclass
class CourseDetailData:
    """Data structure for the course detail view."""

    course_id: UUID
    course_name: str
    course_code: str
    course_description: str
    homeworks: list[HomeworkItem]
    enrolled_students: list[EnrolledStudentItem] | None
    teacher_assistants: list[TAItem] | None
    user_roles: list[CourseRole]  # Changed from list[str]
    instructors: list[InstructorItem]  # NEW: List of instructors
    is_enrolled: bool  # NEW: True if user is enrolled student
```

### 3. Modify CourseDetailView.get() Method

**File**: `src/courses/views.py`  
**Location**: Lines 339-383

**Change**: Instead of returning 403 when a student has no role, allow access with limited data.

```python
def get(self, request: HttpRequest, course_id: UUID) -> HttpResponse:
    """Handle GET requests to display course detail."""
    course = get_object_or_404(Course, id=course_id)

    teacher_profile = getattr(request.user, "teacher_profile", None)
    student_profile = getattr(request.user, "student_profile", None)
    teacher_assistant_profile = getattr(
        request.user, "teacher_assistant_profile", None
    )

    user_roles: list[CourseRole] = []  # Changed type

    if (
        teacher_profile
        and CourseTeacher.objects.filter(
            course=course, teacher=teacher_profile
        ).exists()
    ):
        user_roles.append(CourseRole.TEACHER)

    if student_profile and course.is_student_enrolled(student_profile):
        user_roles.append(CourseRole.STUDENT)

    if teacher_assistant_profile and course.is_teacher_assistant(
        teacher_assistant_profile
    ):
        user_roles.append(CourseRole.TEACHER_ASSISTANT)

    # Get the appropriate data based on user roles
    data = self._get_view_data(
        course,
        user_roles,
        teacher_profile,
        student_profile,
        teacher_assistant_profile,
    )

    return render(request, "courses/detail.html", {"data": data})
```

### 4. Modify _get_view_data() Method

**File**: `src/courses/views.py`  
**Location**: Lines 385-472

**Changes**:
- Update signature to use `CourseRole`
- Add `instructors` and `is_enrolled` to returned data
- Remove the logic that restricts homework visibility based on enrollment

```python
def _get_view_data(
    self,
    course: Course,
    user_roles: list[CourseRole],
    teacher_profile=None,
    student_profile=None,
    teacher_assistant_profile=None,
) -> CourseDetailData:
    # ... existing homework retrieval logic (lines 406-420) ...

    # Get instructors
    instructors = []
    for ct in CourseTeacher.objects.filter(course=course).select_related("teacher__user"):
        instructors.append(
            InstructorItem(
                first_name=ct.teacher.user.first_name,
                last_name=ct.teacher.user.last_name,
            )
        )

    # Determine if user is enrolled as student
    is_enrolled = CourseRole.STUDENT in user_roles

    # Get enrolled students if user is a teacher or TA
    enrolled_students = None
    if CourseRole.TEACHER in user_roles or CourseRole.TEACHER_ASSISTANT in user_roles:
        enrollments = (
            CourseEnrollment.objects.filter(course=course, is_active=True)
            .select_related("student__user")
            .order_by("-enrolled_at")
        )
        enrolled_students = []
        for enrollment in enrollments:
            student = enrollment.student
            enrolled_students.append(
                EnrolledStudentItem(
                    id=student.id,
                    username=student.user.username,
                    email=student.user.email,
                    enrolled_at=enrollment.enrolled_at.strftime("%B %d, %Y"),
                )
            )

    # Get teacher assistants if user is a teacher or TA
    teacher_assistants = None
    if CourseRole.TEACHER in user_roles or CourseRole.TEACHER_ASSISTANT in user_roles:
        tas = (
            CourseTeacherAssistant.objects.filter(course=course)
            .select_related("teacher_assistant__user")
            .order_by("-assigned_at")
        )
        teacher_assistants = []
        for ta in tas:
            teacher_assistants.append(
                TAItem(
                    id=ta.teacher_assistant.id,
                    username=ta.teacher_assistant.user.username,
                    email=ta.teacher_assistant.user.email,
                    assigned_at=ta.assigned_at.strftime("%B %d, %Y"),
                )
            )

    return CourseDetailData(
        course_id=course.id,
        course_name=course.name,
        course_code=course.code,
        course_description=course.description,
        homeworks=homeworks,  # Show homeworks to everyone
        enrolled_students=enrolled_students,
        teacher_assistants=teacher_assistants,
        user_roles=user_roles,
        instructors=instructors,
        is_enrolled=is_enrolled,
    )
```

### 5. Modify CourseEnrollView.post() Method

**File**: `src/courses/views.py`  
**Location**: Line 225

**Change**: After successful enrollment, redirect to the course detail page instead of the course list.

```python
# Redirect back to course detail
return redirect("courses:detail", course_id=course.id)
```

### 6. Update CourseListView to Use CourseRole Enum

**File**: `src/courses/views.py`

Update `CourseItem` and `CourseListData` to use `CourseRole`:

```python
from .enums import CourseRole

@dataclass
class CourseItem:
    id: UUID
    name: str
    code: str
    description: str
    roles: list[CourseRole]  # Changed from list[str]
    is_enrolled: bool
    instructors: list[InstructorItem]
```

Update `CourseListView._get_view_data` (around line 120) to use `CourseRole` instead of strings.

### 7. Modify detail.html Template

**File**: `src/courses/templates/courses/detail.html`

**Changes**:

1. Add enrollment button section (after course description, before homework section):

```html
<!-- Enrollment Section (for unenrolled students) -->
{% if student_profile and not data.is_enrolled and 'teacher' not in data.user_roles and 'teacher_assistant' not in data.user_roles %}
<div class="row mb-4">
    <div class="col">
        <div class="card border-primary">
            <div class="card-body text-center">
                <h5 class="card-title">You are not enrolled in this course</h5>
                <p class="card-text">Enroll now to access homework assignments and participate in conversations.</p>
                <form method="post" action="{% url 'courses:enroll' data.course_id %}">
                    {% csrf_token %}
                    <button type="submit" class="btn btn-primary btn-lg">
                        <i class="bi bi-plus-circle"></i> Enroll Now
                    </button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endif %}
```

2. Add instructors section (after description):

```html
<!-- Instructors Section -->
{% if data.instructors %}
<div class="row mb-4">
    <div class="col">
        <h4><i class="bi bi-person-badge"></i> Instructors</h4>
        <ul class="list-unstyled">
            {% for instructor in data.instructors %}
            <li class="mb-2">
                <i class="bi bi-person"></i> {{ instructor.first_name }} {{ instructor.last_name }}
            </li>
            {% endfor %}
        </ul>
    </div>
</div>
{% endif %}
```

3. Update the "Enrolled" badge to use `is_enrolled`:

```html
{% if data.is_enrolled %}
<span class="badge bg-success ms-2">Enrolled</span>
{% endif %}
```

## Edge Cases

1. **Inactive course**: Students should NOT see an enrollment button for inactive courses. The enrollment form should check `course.is_active` before allowing enrollment.

2. **Teacher viewing other teacher's course**: Teachers who don't teach a course should still see the course if they have the direct URL (they will see course info but no teacher-specific UI).

3. **Unauthenticated users**: Should still be redirected to login (handled by `@login_required` decorator).

4. **TA viewing course they assist**: TAs have full access, no enrollment button needed.

5. **Already enrolled student**: Should see "Enrolled" badge, not enrollment button.

## Testing Considerations

### New Tests to Add

1. **`test_student_can_view_unenrolled_course`**: Verify that a student who is NOT enrolled can access the course detail page (status 200).

2. **`test_student_sees_enrollment_button_for_unenrolled_course`**: Verify that an unenrolled student sees the enrollment button.

3. **`test_student_does_not_see_enrollment_button_for_inactive_course`**: Verify that enrollment button is not shown for inactive courses.

4. **`test_student_sees_instructors_for_unenrolled_course`**: Verify that uninrolled students can see the instructors list.

5. **`test_enrollment_redirects_to_course_detail`**: Verify that after enrolling, user is redirected to course detail page.

### Existing Tests to Modify

1. **`test_student_cannot_view_unenrolled_course`** (line 777-786): Change expected behavior from 403 to 200, and verify limited view with `is_enrolled=False`.

2. **`test_course_detail_shows_correct_user_type`** (line 819-833): Update to use `CourseRole` enum values.

## File Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/courses/enums.py` | Create | New file with `CourseRole` enum |
| `src/courses/views.py` | Modify | Update dataclasses, views to use `CourseRole` enum, add instructor data, modify enrollment redirect |
| `src/courses/templates/courses/detail.html` | Modify | Add enrollment button, instructors section, update badge logic |
| `src/courses/tests/test_views.py` | Modify | Update tests for new behavior and enum usage |

## Implementation Order

1. Create `src/courses/enums.py` with `CourseRole` enum
2. Update `CourseItem` and `CourseListData` to use `CourseRole`
3. Update `CourseDetailData` to include `instructors` and `is_enrolled`
4. Update `CourseDetailView.get()` to remove 403 for empty roles
5. Update `_get_view_data()` to return `instructors` and `is_enrolled`
6. Update `CourseEnrollView.post()` to redirect to course detail
7. Update `detail.html` template with enrollment button and instructors section
8. Update tests
9. Run tests to verify

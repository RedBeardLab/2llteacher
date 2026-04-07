# Design Document: Allow Students to See Course They Are Not Enrolled In

## Issue Summary

**Problem**: When a student tries to view a course they are not enrolled in, they receive a "You do not have access to this course" error (HTTP 403).

**Desired Behavior**: Students should be able to view the course page for any active course, seeing:
- Course name and code
- Course description
- Instructors
- An "Enroll Now" button (if not enrolled)

## Current Behavior

In `src/courses/views.py`, the `CourseDetailView.get()` method (lines 339-383) checks user roles and returns 403 if the user has no role (teacher, enrolled student, or TA) for the course:

```python
if not user_roles:
    return HttpResponseForbidden("You do not have access to this course.")
```

## Proposed Changes

### 1. Modify `CourseDetailView.get()` Method

**File**: `src/courses/views.py`  
**Location**: Lines 339-383

**Change**: Instead of returning 403 when a student has no role, allow access with limited data. The logic should:

1. Check if user is a teacher teaching the course → full access
2. Check if user is an enrolled student → full access
3. Check if user is a TA → full access
4. **NEW**: Check if user is an unauthenticated student → limited access (can see course info, instructors, and enrollment button)

**Modified Logic**:
```python
def get(self, request: HttpRequest, course_id: UUID) -> HttpResponse:
    """Handle GET requests to display course detail."""
    course = get_object_or_404(Course, id=course_id)

    teacher_profile = getattr(request.user, "teacher_profile", None)
    student_profile = getattr(request.user, "student_profile", None)
    teacher_assistant_profile = getattr(
        request.user, "teacher_assistant_profile", None
    )

    user_roles = []

    if (
        teacher_profile
        and CourseTeacher.objects.filter(
            course=course, teacher=teacher_profile
        ).exists()
    ):
        user_roles.append("teacher")

    if student_profile and course.is_student_enrolled(student_profile):
        user_roles.append("student")

    if teacher_assistant_profile and course.is_teacher_assistant(
        teacher_assistant_profile
    ):
        user_roles.append("teacher_assistant")

    # NEW: Check if user is a logged-in student (even if not enrolled)
    is_unenrolled_student = (
        student_profile is not None
        and "student" not in user_roles
        and "teacher" not in user_roles
        and "teacher_assistant" not in user_roles
    )

    # If user has no role at all (not even unenrolled student), deny access
    if not user_roles and not is_unenrolled_student:
        return HttpResponseForbidden("You do not have access to this course.")

    # Get the appropriate data based on user roles
    data = self._get_view_data(
        course,
        user_roles,
        teacher_profile,
        student_profile,
        teacher_assistant_profile,
        is_unenrolled_student=is_unenrolled_student,
    )

    return render(request, "courses/detail.html", {"data": data})
```

### 2. Modify `CourseDetailData` Dataclass

**File**: `src/courses/views.py`  
**Location**: Lines 310-323

**Change**: Add `instructors` field and `is_enrolled_student` flag for the template to conditionally show the enrollment button.

```python
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
    user_roles: list[str]
    instructors: list[InstructorItem]  # NEW: List of instructors
    is_enrolled_student: bool  # NEW: True if user is enrolled student (for template badge)
    can_enroll: bool  # NEW: True if user can enroll (unenrolled student viewing active course)
```

### 3. Modify `_get_view_data()` Method

**File**: `src/courses/views.py`  
**Location**: Lines 385-472

**Change**: 
- Add `is_unenrolled_student` parameter
- When `is_unenrolled_student=True`, return limited data (no homeworks, show instructors, `can_enroll=True`)
- When user has full access, set `can_enroll=False`

**Modified Signature**:
```python
def _get_view_data(
    self,
    course: Course,
    user_roles: list[str],
    teacher_profile=None,
    student_profile=None,
    teacher_assistant_profile=None,
    is_unenrolled_student: bool = False,  # NEW parameter
) -> CourseDetailData:
```

**Modified Return Logic** (before return statement at line 463):
```python
# Get instructors (available to all who can view the course)
instructors = []
for ct in CourseTeacher.objects.filter(course=course).select_related("teacher__user"):
    instructors.append(
        InstructorItem(
            first_name=ct.teacher.user.first_name,
            last_name=ct.teacher.user.last_name,
        )
    )

if is_unenrolled_student:
    # Unenrolled students see course info and instructors, but not homeworks
    return CourseDetailData(
        course_id=course.id,
        course_name=course.name,
        course_code=course.code,
        course_description=course.description,
        homeworks=[],  # No homework access for unenrolled students
        enrolled_students=None,
        teacher_assistants=None,
        user_roles=["student"],  # For template conditionals
        instructors=instructors,
        is_enrolled_student=False,
        can_enroll=course.is_active,  # Can enroll if course is active
    )

# ... existing logic for enrolled users ...
```

### 4. Modify `CourseEnrollView.post()` Method

**File**: `src/courses/views.py`  
**Location**: Line 225

**Change**: After successful enrollment, redirect to the course detail page instead of the course list.

```python
# Redirect back to course detail
return redirect("courses:detail", course_id=course.id)
```

### 5. Modify `detail.html` Template

**File**: `src/courses/templates/courses/detail.html`

**Changes**:
1. Add enrollment button section (after course header, before homework section)
2. Conditionally hide homework list for unenrolled students
3. Add "Enrolled" badge for enrolled students
4. Add instructors section

**New Template Sections**:

Add enrollment button after the course header (after line 45):
```html
<!-- Enrollment Section (for unenrolled students) -->
{% if data.can_enroll and 'teacher' not in data.user_roles %}
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

Add instructors section (after description, before homework section):
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

Conditionally hide homework list for unenrolled students (modify line 48):
```html
<!-- Homework Section -->
{% if data.homeworks|length > 0 %}
{% if 'teacher' in data.user_roles or 'student' in data.user_roles %}
<div class="row mb-4">
    ...
</div>
{% endif %}
{% endif %}
```

## Edge Cases

1. **Inactive course**: Students should NOT see an enrollment button for inactive courses. The `can_enroll` flag should only be `True` if `course.is_active` is `True`.

2. **Teacher viewing other teacher's course**: Teachers who don't teach a course should still see the course if they have the direct URL (consistent with current behavior).

3. **Unauthenticated users**: Should still be redirected to login (handled by `@login_required` decorator).

4. **TA viewing course they assist**: TAs have full access, no enrollment button needed.

5. **Already enrolled student**: Should see "Enrolled" badge (already implemented), not enrollment button.

## Testing Considerations

### New Tests to Add

1. **`test_student_can_view_unenrolled_course`**: Verify that a student who is NOT enrolled can access the course detail page.

2. **`test_student_sees_enrollment_button_for_unenrolled_course`**: Verify that an unenrolled student sees the enrollment button.

3. **`test_student_does_not_see_enrollment_button_for_inactive_course`**: Verify that enrollment button is not shown for inactive courses.

4. **`test_student_cannot_see_homeworks_for_unenrolled_course`**: Verify that unenrolled students cannot see homework assignments.

5. **`test_enrollment_redirects_to_course_detail`**: Verify that after enrolling, user is redirected to course detail page.

### Existing Tests to Modify

1. **`test_student_cannot_view_unenrolled_course`** (line 777-786): Change expected behavior from 403 to 200, and verify limited view.

## File Summary

| File | Change Type | Lines Affected |
|------|-------------|----------------|
| `src/courses/views.py` | Modify | 310-323, 339-383, 385-472 |
| `src/courses/templates/courses/detail.html` | Modify | 45-50, 48-87 (homework section), new sections |
| `src/courses/tests/test_views.py` | Modify | 777-786 (change expected behavior) |
| `src/courses/tests/test_views.py` | Add | New test methods |

## Implementation Order

1. Modify `CourseDetailData` dataclass to add new fields
2. Modify `_get_view_data()` method signature and logic
3. Modify `CourseDetailView.get()` method to pass `is_unenrolled_student`
4. Modify `CourseEnrollView.post()` to redirect to course detail
5. Update `detail.html` template with enrollment button and instructors
6. Update/add tests

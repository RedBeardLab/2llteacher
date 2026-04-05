# Design Document: Course List Description Enhancement

## Issue
**Title**: Course show description
**Description**: The course views show a long description. If one course has a long description the UI looks ugly and unprofessional. Use `details` and `summary` to show an excerpt of the description when available. When not available, do not show description not available. Before the description add also a line with the instructors.

## Summary
Modify the course list view to display descriptions using HTML `details`/`summary` elements, and include instructor names before the description.

## Files to Modify

### 1. `/home/sprite/workspace/repo/src/courses/views.py`

#### Change 1: Add `InstructorItem` dataclass (new)

Add a new dataclass after `CourseItem` to represent an instructor:

```python
@dataclass
class InstructorItem:
    """Data structure for an instructor in the course list."""
    id: UUID
    username: str
    email: str
    role: str  # 'owner' or 'co_teacher'
```

#### Change 2: Modify `CourseItem` dataclass

Update `CourseItem` to include instructors:

```python
@dataclass
class CourseItem:
    """Data structure for a single course item in the list view."""

    id: UUID
    name: str
    code: str
    description: str
    roles: list[str]  # ['teacher', 'student', 'teacher_assistant']
    is_enrolled: bool
    instructors: list[InstructorItem]  # NEW: List of instructors
```

#### Change 3: Modify `CourseListView._get_view_data()` method

In the `_get_view_data()` method, around line 137-152, update the `CourseItem` construction to include instructors:

```python
# Convert to CourseItem list
courses = []
for course_data in sorted(course_dict.values(), key=lambda x: x["course"].name):
    course = course_data["course"]
    
    # Get instructors for this course
    instructors = []
    for course_teacher in CourseTeacher.objects.filter(course=course).select_related("teacher__user"):
        instructors.append(
            InstructorItem(
                id=course_teacher.teacher.id,
                username=course_teacher.teacher.user.username,
                email=course_teacher.teacher.user.email,
                role=course_teacher.role,
            )
        )
    
    courses.append(
        CourseItem(
            id=course.id,
            name=course.name,
            code=course.code,
            description=course.description,
            roles=course_data["roles"],
            is_enrolled=course_data["is_enrolled"],
            instructors=instructors,
        )
    )
```

### 2. `/home/sprite/workspace/repo/src/courses/templates/courses/list.html`

Replace the description display section (lines 69-79) with the new implementation:

**Old code (lines 69-79):**
```html
<div class="card-body">
    <div class="mb-2">
        <strong>Course Code:</strong> <code>{{ course.code }}</code>
    </div>
    <div class="card-text">
        <zero-md src="data:text/markdown;charset=utf-8,{{ course.description|urlencode }}">
        <template data-append>
            <style>.markdown-body { background-color: transparent !important; }</style>
        </template>
    </div>
</div>
```

**New code:**
```html
<div class="card-body">
    <div class="mb-2">
        <strong>Course Code:</strong> <code>{{ course.code }}</code>
    </div>
    {% if course.instructors %}
    <div class="mb-2 text-muted small">
        <i class="bi bi-person-badge"></i>
        {% for instructor in course.instructors %}
            {{ instructor.username }}{% if instructor.role == 'owner' %} (Owner){% endif %}{% if not forloop.last %}, {% endif %}
        {% endfor %}
    </div>
    {% endif %}
    {% if course.description %}
    <div class="card-text">
        <details>
            <summary class="text-primary" style="cursor: pointer;">
                <i class="bi bi-chevron-down"></i> View Description
            </summary>
            <div class="mt-2">
                <zero-md src="data:text/markdown;charset=utf-8,{{ course.description|urlencode }}">
                <template data-append>
                    <style>.markdown-body { background-color: transparent !important; }</style>
                </template>
            </div>
        </details>
    </div>
    {% endif %}
</div>
```

### 3. `/home/sprite/workspace/repo/src/courses/tests/test_views.py`

Add new test methods to `CourseListViewTests` class to test the new functionality.

#### Change: Add tests for instructors in course list

Add the following test methods to `CourseListViewTests`:

```python
def test_get_view_data_includes_instructors(self):
    """Test that course list includes instructor information."""
    # Add teacher to course1 as owner
    CourseTeacher.objects.create(
        course=self.course1, teacher=self.teacher, role="owner"
    )
    
    view = CourseListView()
    data = view._get_view_data(self.teacher_user)
    
    # Find course1
    course1_item = next(c for c in data.courses if c.id == self.course1.id)
    
    # Check instructors
    self.assertEqual(len(course1_item.instructors), 1)
    self.assertEqual(course1_item.instructors[0].username, self.teacher_user.username)
    self.assertEqual(course1_item.instructors[0].role, "owner")

def test_get_view_data_includes_multiple_instructors(self):
    """Test that course list includes multiple instructors."""
    # Create another teacher
    other_teacher_user = User.objects.create_user(
        username="otherteacher", email="other@example.com", password="password123"
    )
    other_teacher = Teacher.objects.create(user=other_teacher_user)
    
    # Add both teachers to course1
    CourseTeacher.objects.create(
        course=self.course1, teacher=self.teacher, role="owner"
    )
    CourseTeacher.objects.create(
        course=self.course1, teacher=other_teacher, role="co_teacher"
    )
    
    view = CourseListView()
    data = view._get_view_data(self.teacher_user)
    
    # Find course1
    course1_item = next(c for c in data.courses if c.id == self.course1.id)
    
    # Check instructors
    self.assertEqual(len(course1_item.instructors), 2)
    roles = [i.role for i in course1_item.instructors]
    self.assertIn("owner", roles)
    self.assertIn("co_teacher", roles)

def test_get_view_data_course_without_instructors_shows_empty_list(self):
    """Test that courses without instructors show empty list."""
    # course1 has no instructors yet
    view = CourseListView()
    data = view._get_view_data(self.teacher_user)
    
    # course1 should have empty instructors list
    course1_item = next(c for c in data.courses if c.id == self.course1.id)
    self.assertEqual(len(course1_item.instructors), 0)
```

## Edge Cases

1. **Course with no description**: The `{% if course.description %}` block ensures nothing is rendered when description is empty
2. **Course with no instructors**: The `{% if course.instructors %}` block ensures no instructor line is shown when course has no teachers
3. **Empty instructor username**: Will still display, but this is an existing data integrity issue not caused by this change
4. **Long description**: The `details`/`summary` elements provide a clean UI regardless of description length

## Testing

Run tests with:
```bash
uv run python run_tests.py --settings=src.llteacher.test_settings courses.tests.test_views
```

Tests to verify:
1. Existing tests still pass
2. New instructor tests pass
3. Template renders correctly (manual verification may be needed)

## Implementation Order

1. Update `views.py` - Add `InstructorItem` dataclass and modify `CourseItem` and `_get_view_data()`
2. Update `list.html` - Modify template to use `details`/`summary` and show instructors
3. Add tests to `test_views.py`
4. Run tests to verify changes

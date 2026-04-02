# Design Document: Matrix View Bug Investigation and Fix

## Issue Summary

**Title**: Matrix view not working anymore

**Description**: The matrix view of grades is not working correctly - it may be showing data for inactive enrollments. Investigation revealed that the `get_all_homework_matrix` function does not filter by `is_active=True` on `CourseEnrollment`, unlike similar queries in other views.

---

## 1. Problem Analysis

### Root Cause

The `HomeworkService.get_all_homework_matrix()` method at `src/homeworks/services.py:504-697` does not filter out inactive course enrollments when fetching students for the matrix view.

**Problematic code** (`src/homeworks/services.py:532-539`):
```python
enrolled_students = (
    Student.objects.filter(
        enrolled_courses__homeworks__in=homeworks,
    )
    .select_related("user")
    .order_by("user__first_name", "user__last_name", "user__username")
    .distinct()
)
```

**Inconsistency**: Other queries in `src/homeworks/views.py` correctly filter by `is_active=True`:
- Line 143: `courseenrollment__is_active=True`
- Line 634: `courseenrollment__is_active=True`
- Line 869: `courseenrollment__is_active=True`

### Impact

Students with inactive enrollments may appear in the matrix view even though they should not be shown. This could cause:
1. Teachers seeing students who are no longer enrolled in their courses
2. Confusion about actual class progress
3. Incorrect grade data being exported via CSV

---

## 2. Files to Modify

### 2.1 Primary Fix

**File**: `src/homeworks/services.py`

**Location**: Lines 532-539 (`get_all_homework_matrix` method)

**Change**: Add `courseenrollment__is_active=True` filter to the enrolled_students query.

### 2.2 New Tests to Add

**File**: `src/homeworks/tests/test_matrix_view.py`

Add test cases for:
1. Inactive enrollment filtering - verify inactive students are NOT shown
2. Reactivated enrollment - verify a student who was inactive then reactivated appears correctly

---

## 3. Implementation Plan

### 3.1 Fix the Service Layer

**File**: `src/homeworks/services.py`

```python
# BEFORE (line 532-539):
enrolled_students = (
    Student.objects.filter(
        enrolled_courses__homeworks__in=homeworks,
    )
    .select_related("user")
    .order_by("user__first_name", "user__last_name", "user__username")
    .distinct()
)

# AFTER:
enrolled_students = (
    Student.objects.filter(
        enrolled_courses__homeworks__in=homeworks,
        enrolled_courses__is_active=True,  # Add this filter
    )
    .select_related("user")
    .order_by("user__first_name", "user__last_name", "user__username")
    .distinct()
)
```

**Note**: The comment on line 531 ("Include students from inactive courses to show historical submissions") should be removed or updated since this behavior is inconsistent with the rest of the codebase and the comment appears to be incorrect/intentional technical debt.

### 3.2 Add Test Cases

**File**: `src/homeworks/tests/test_matrix_view.py`

Add two new test methods to `HomeworkMatrixViewTest` class:

#### Test 1: Inactive Enrollments Not Shown

```python
def test_inactive_enrolled_students_not_shown_in_matrix(self):
    """Test that students with inactive enrollments are not shown in matrix."""
    # Deactivate student1's enrollment
    enrollment = CourseEnrollment.objects.get(course=self.course, student=self.student1)
    enrollment.is_active = False
    enrollment.save()

    matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

    self.assertIsNotNone(matrix_data)
    # Should only show 1 student (student2 with active enrollment)
    self.assertEqual(matrix_data.total_students, 1)
    self.assertEqual(len(matrix_data.student_rows), 1)

    # Verify only student2 is shown
    student_ids = [row.student_id for row in matrix_data.student_rows]
    self.assertNotIn(self.student1.id, student_ids)
    self.assertIn(self.student2.id, student_ids)
```

#### Test 2: Reactivated Enrollment Shown

```python
def test_reactivated_enrollment_shown_in_matrix(self):
    """Test that a student whose enrollment was reactivated appears in matrix."""
    # First deactivate
    enrollment = CourseEnrollment.objects.get(course=self.course, student=self.student1)
    enrollment.is_active = False
    enrollment.save()

    # Get matrix - student1 should not appear
    matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)
    self.assertEqual(matrix_data.total_students, 1)

    # Reactivate
    enrollment.is_active = True
    enrollment.save()

    # Get matrix again - student1 should now appear
    matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)
    self.assertEqual(matrix_data.total_students, 2)

    student_ids = [row.student_id for row in matrix_data.student_rows]
    self.assertIn(self.student1.id, student_ids)
```

#### Test 3: Inactive Enrollment Not in CSV Export

```python
def test_csv_export_excludes_inactive_enrolled_students(self):
    """Test that CSV export excludes students with inactive enrollments."""
    # Deactivate student1's enrollment
    enrollment = CourseEnrollment.objects.get(course=self.course, student=self.student1)
    enrollment.is_active = False
    enrollment.save()

    # Login as teacher and get export
    self.client.login(username="teacher", password="password123")
    response = self.client.get(reverse("homeworks:matrix_export"))

    self.assertEqual(response.status_code, 200)
    content = response.content.decode("utf-8")

    # Should only contain student2's name, not student1
    self.assertIn("Bob Jones", content)
    self.assertNotIn("Alice Smith", content)
```

### 3.3 Update Comment

**File**: `src/homeworks/services.py`

Remove or update the misleading comment on line 531:
```python
# BEFORE:
# Include students from inactive courses to show historical submissions

# AFTER (either remove or correct):
# Only include students with active enrollments
```

---

## 4. Edge Cases to Consider

1. **Student enrolled in multiple courses**: If a student is enrolled in multiple courses (some active, some inactive), they should still appear in the matrix if ANY of their enrollments for the teacher's homework courses is active.

2. **All enrollments inactive**: If all a student's enrollments become inactive, they should not appear in the matrix.

3. **Reactivation after initial matrix load**: The matrix is fetched fresh on each request, so this should work automatically.

4. **CSV export consistency**: The CSV export uses the same service method, so the fix will apply there too.

---

## 5. Verification Plan

### 5.1 Run Existing Tests

```bash
uv run python run_tests.py --settings=src.llteacher.test_settings homeworks.tests.test_matrix_view
uv run python run_tests.py --settings=src.llteacher.test_settings homeworks.tests.test_matrix_export_view
```

### 5.2 Run New Tests

After implementing the fix and new tests:
```bash
uv run python run_tests.py --settings=src.llteacher.test_settings homeworks.tests.test_matrix_view.HomeworkMatrixViewTest.test_inactive_enrolled_students_not_shown_in_matrix
uv run python run_tests.py --settings=src.llteacher.test_settings homeworks.tests.test_matrix_view.HomeworkMatrixViewTest.test_reactivated_enrollment_shown_in_matrix
uv run python run_tests.py --settings=src.llteacher.test_settings homeworks.tests.test_matrix_export_view.TestHomeworkMatrixExportView.test_csv_export_excludes_inactive_enrolled_students
```

### 5.3 Manual Verification

1. Log in as a teacher
2. Create or use an existing course with enrolled students
3. Deactivate one student's enrollment
4. Navigate to the matrix view
5. Verify the deactivated student does not appear
6. Test CSV export to verify same behavior

---

## 6. Implementation Checklist

- [ ] Modify `src/homeworks/services.py` line 534 to add `enrolled_courses__is_active=True` filter
- [ ] Update/remove misleading comment on line 531
- [ ] Add test `test_inactive_enrolled_students_not_shown_in_matrix` to `test_matrix_view.py`
- [ ] Add test `test_reactivated_enrollment_shown_in_matrix` to `test_matrix_view.py`
- [ ] Add test `test_csv_export_excludes_inactive_enrolled_students` to `test_matrix_export_view.py`
- [ ] Run all matrix tests to verify nothing is broken
- [ ] Verify the fix works correctly

---

## 7. Additional Recommendations

### 7.1 Consider Type Safety

The `get_all_homework_matrix` method returns `HomeworkMatrixData | None`. Consider adding a result type that includes error information for better error handling.

### 7.2 Add Missing URL Test

There is no test for the matrix view redirecting when `matrix_data is None`. Consider adding:
```python
def test_matrix_view_redirects_on_error(self):
    """Test that matrix view redirects when service returns None."""
    # This would require mocking the service to return None
    pass
```

### 7.3 Performance Consideration

The current implementation fetches all conversations and submissions for all homeworks. For large datasets, consider:
- Adding pagination
- Using `only()` to fetch specific fields
- Caching frequently accessed data

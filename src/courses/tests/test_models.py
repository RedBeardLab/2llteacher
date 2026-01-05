from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from courses.models import Course, CourseTeacher, CourseEnrollment
from accounts.models import Teacher, Student
from homeworks.models import Homework
import uuid
from datetime import timedelta


class CourseModelTest(TestCase):
    """Test cases for the Course model."""

    def setUp(self):
        self.User = get_user_model()
        self.teacher_user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.course_data = {
            "name": "Introduction to Python",
            "description": "A beginner course on Python programming",
            "code": "PYTHON101",
        }

    def test_course_creation(self):
        """Test basic course creation."""
        course = Course.objects.create(**self.course_data)
        self.assertEqual(course.name, "Introduction to Python")
        self.assertEqual(course.description, "A beginner course on Python programming")
        self.assertEqual(course.code, "PYTHON101")
        self.assertTrue(course.is_active)
        self.assertIsInstance(course.id, uuid.UUID)

    def test_course_uuid_primary_key(self):
        """Test that course has UUID primary key."""
        course = Course.objects.create(**self.course_data)
        self.assertIsInstance(course.id, uuid.UUID)

    def test_course_timestamps(self):
        """Test course timestamp fields."""
        course = Course.objects.create(**self.course_data)
        self.assertIsNotNone(course.created_at)
        self.assertIsNotNone(course.updated_at)
        self.assertIsInstance(course.created_at, timezone.datetime)
        self.assertIsInstance(course.updated_at, timezone.datetime)

    def test_course_str_representation(self):
        """Test course string representation."""
        course = Course.objects.create(**self.course_data)
        self.assertEqual(str(course), "Introduction to Python (PYTHON101)")

    def test_course_table_name(self):
        """Test course table name."""
        course = Course.objects.create(**self.course_data)
        self.assertEqual(course._meta.db_table, "courses_course")

    def test_course_ordering(self):
        """Test course ordering by created_at descending."""
        course1 = Course.objects.create(**self.course_data)
        course2 = Course.objects.create(
            name="Advanced Python",
            description="Advanced Python topics",
            code="PYTHON201",
        )

        courses = list(Course.objects.all())
        self.assertEqual(courses[0], course2)
        self.assertEqual(courses[1], course1)

    def test_course_code_uniqueness(self):
        """Test course code must be unique."""
        Course.objects.create(**self.course_data)

        with self.assertRaises(Exception):
            Course.objects.create(**self.course_data)

    def test_course_without_description(self):
        """Test course creation without description."""
        course_data_no_desc = self.course_data.copy()
        course_data_no_desc["description"] = ""

        course = Course.objects.create(**course_data_no_desc)
        self.assertEqual(course.description, "")

    def test_course_is_active_default(self):
        """Test course is_active defaults to True."""
        course = Course.objects.create(**self.course_data)
        self.assertTrue(course.is_active)

    def test_course_can_be_inactive(self):
        """Test course can be set to inactive."""
        course = Course.objects.create(**self.course_data, is_active=False)
        self.assertFalse(course.is_active)


class CourseTeacherModelTest(TestCase):
    """Test cases for the CourseTeacher model."""

    def setUp(self):
        self.User = get_user_model()
        self.teacher_user = self.User.objects.create_user(
            username="teacher1", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.course = Course.objects.create(
            name="Test Course",
            description="Test Description",
            code="TEST101",
        )

    def test_course_teacher_creation(self):
        """Test basic CourseTeacher creation."""
        course_teacher = CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
            role="owner",
        )
        self.assertEqual(course_teacher.course, self.course)
        self.assertEqual(course_teacher.teacher, self.teacher)
        self.assertEqual(course_teacher.role, "owner")
        self.assertIsInstance(course_teacher.id, uuid.UUID)

    def test_course_teacher_uuid_primary_key(self):
        """Test that CourseTeacher has UUID primary key."""
        course_teacher = CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
        )
        self.assertIsInstance(course_teacher.id, uuid.UUID)

    def test_course_teacher_default_role(self):
        """Test CourseTeacher default role is co_teacher."""
        course_teacher = CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
        )
        self.assertEqual(course_teacher.role, "co_teacher")

    def test_course_teacher_joined_at(self):
        """Test CourseTeacher joined_at timestamp."""
        course_teacher = CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
        )
        self.assertIsNotNone(course_teacher.joined_at)
        self.assertIsInstance(course_teacher.joined_at, timezone.datetime)

    def test_course_teacher_str_representation(self):
        """Test CourseTeacher string representation."""
        course_teacher = CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
            role="owner",
        )
        expected_str = f"{self.teacher.user.email} - {self.course.name} (owner)"
        self.assertEqual(str(course_teacher), expected_str)

    def test_course_teacher_table_name(self):
        """Test CourseTeacher table name."""
        course_teacher = CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
        )
        self.assertEqual(course_teacher._meta.db_table, "courses_course_teacher")

    def test_course_teacher_unique_together(self):
        """Test CourseTeacher unique_together constraint."""
        CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
        )

        with self.assertRaises(Exception):
            CourseTeacher.objects.create(
                course=self.course,
                teacher=self.teacher,
            )

    def test_course_teacher_ordering(self):
        """Test CourseTeacher ordering by joined_at."""
        course_teacher1 = CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
        )

        teacher_user2 = self.User.objects.create_user(
            username="teacher2", password="testpass123"
        )
        teacher2 = Teacher.objects.create(user=teacher_user2)

        course_teacher2 = CourseTeacher.objects.create(
            course=self.course,
            teacher=teacher2,
        )

        course_teachers = list(CourseTeacher.objects.all())
        self.assertEqual(course_teachers[0], course_teacher1)
        self.assertEqual(course_teachers[1], course_teacher2)


class CourseEnrollmentModelTest(TestCase):
    """Test cases for the CourseEnrollment model."""

    def setUp(self):
        self.User = get_user_model()
        self.student_user = self.User.objects.create_user(
            username="student1", password="testpass123"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.course = Course.objects.create(
            name="Test Course",
            description="Test Description",
            code="TEST101",
        )

    def test_course_enrollment_creation(self):
        """Test basic CourseEnrollment creation."""
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )
        self.assertEqual(enrollment.course, self.course)
        self.assertEqual(enrollment.student, self.student)
        self.assertTrue(enrollment.is_active)
        self.assertIsInstance(enrollment.id, uuid.UUID)

    def test_course_enrollment_uuid_primary_key(self):
        """Test that CourseEnrollment has UUID primary key."""
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )
        self.assertIsInstance(enrollment.id, uuid.UUID)

    def test_course_enrollment_default_is_active(self):
        """Test CourseEnrollment default is_active is True."""
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )
        self.assertTrue(enrollment.is_active)

    def test_course_enrollment_can_be_inactive(self):
        """Test CourseEnrollment can be set to inactive."""
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
            is_active=False,
        )
        self.assertFalse(enrollment.is_active)

    def test_course_enrollment_enrolled_at(self):
        """Test CourseEnrollment enrolled_at timestamp."""
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )
        self.assertIsNotNone(enrollment.enrolled_at)
        self.assertIsInstance(enrollment.enrolled_at, timezone.datetime)

    def test_course_enrollment_str_representation(self):
        """Test CourseEnrollment string representation."""
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )
        expected_str = f"{self.student.user.email} - {self.course.name} (Active)"
        self.assertEqual(str(enrollment), expected_str)

    def test_course_enrollment_str_representation_inactive(self):
        """Test CourseEnrollment string representation when inactive."""
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
            is_active=False,
        )
        expected_str = f"{self.student.user.email} - {self.course.name} (Inactive)"
        self.assertEqual(str(enrollment), expected_str)

    def test_course_enrollment_table_name(self):
        """Test CourseEnrollment table name."""
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )
        self.assertEqual(enrollment._meta.db_table, "courses_course_enrollment")

    def test_course_enrollment_unique_together(self):
        """Test CourseEnrollment unique_together constraint."""
        CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )

        with self.assertRaises(Exception):
            CourseEnrollment.objects.create(
                course=self.course,
                student=self.student,
            )

    def test_course_enrollment_ordering(self):
        """Test CourseEnrollment ordering by enrolled_at descending."""
        enrollment1 = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )

        student_user2 = self.User.objects.create_user(
            username="student2", password="testpass123"
        )
        student2 = Student.objects.create(user=student_user2)

        enrollment2 = CourseEnrollment.objects.create(
            course=self.course,
            student=student2,
        )

        enrollments = list(CourseEnrollment.objects.all())
        self.assertEqual(enrollments[0], enrollment2)
        self.assertEqual(enrollments[1], enrollment1)


class CourseMethodsTest(TestCase):
    """Test cases for Course model methods."""

    def setUp(self):
        self.User = get_user_model()

        # Create teachers
        self.teacher_user = self.User.objects.create_user(
            username="teacher1", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.co_teacher_user = self.User.objects.create_user(
            username="teacher2", password="testpass123"
        )
        self.co_teacher = Teacher.objects.create(user=self.co_teacher_user)

        # Create students
        self.student_user = self.User.objects.create_user(
            username="student1", password="testpass123"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.inactive_student_user = self.User.objects.create_user(
            username="student2", password="testpass123"
        )
        self.inactive_student = Student.objects.create(user=self.inactive_student_user)

        # Create course
        self.course = Course.objects.create(
            name="Test Course",
            description="Test Description",
            code="TEST101",
        )

        # Add teachers
        CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
            role="owner",
        )

        CourseTeacher.objects.create(
            course=self.course,
            teacher=self.co_teacher,
            role="co_teacher",
        )

        # Add students
        CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
            is_active=True,
        )

        CourseEnrollment.objects.create(
            course=self.course,
            student=self.inactive_student,
            is_active=False,
        )

    def test_get_active_students(self):
        """Test get_active_students returns only active students."""
        active_students = self.course.get_active_students()
        self.assertEqual(active_students.count(), 1)
        self.assertIn(self.student, active_students)
        self.assertNotIn(self.inactive_student, active_students)

    def test_get_teacher_role_owner(self):
        """Test get_teacher_role returns correct role for owner."""
        role = self.course.get_teacher_role(self.teacher)
        self.assertEqual(role, "owner")

    def test_get_teacher_role_co_teacher(self):
        """Test get_teacher_role returns correct role for co-teacher."""
        role = self.course.get_teacher_role(self.co_teacher)
        self.assertEqual(role, "co_teacher")

    def test_get_teacher_role_not_in_course(self):
        """Test get_teacher_role returns None for teacher not in course."""
        other_teacher_user = self.User.objects.create_user(
            username="teacher3", password="testpass123"
        )
        other_teacher = Teacher.objects.create(user=other_teacher_user)

        role = self.course.get_teacher_role(other_teacher)
        self.assertIsNone(role)

    def test_is_teacher_owner_true(self):
        """Test is_teacher_owner returns True for owner."""
        self.assertTrue(self.course.is_teacher_owner(self.teacher))

    def test_is_teacher_owner_false(self):
        """Test is_teacher_owner returns False for co-teacher."""
        self.assertFalse(self.course.is_teacher_owner(self.co_teacher))

    def test_is_student_enrolled_active(self):
        """Test is_student_enrolled returns True for active student."""
        self.assertTrue(self.course.is_student_enrolled(self.student))

    def test_is_student_enrolled_inactive(self):
        """Test is_student_enrolled returns False for inactive student."""
        self.assertFalse(self.course.is_student_enrolled(self.inactive_student))

    def test_is_student_enrolled_not_enrolled(self):
        """Test is_student_enrolled returns False for not enrolled student."""
        other_student_user = self.User.objects.create_user(
            username="student3", password="testpass123"
        )
        other_student = Student.objects.create(user=other_student_user)

        self.assertFalse(self.course.is_student_enrolled(other_student))


class CourseRelationshipsTest(TestCase):
    """Test cases for course relationships."""

    def setUp(self):
        self.User = get_user_model()

        self.teacher_user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = self.User.objects.create_user(
            username="student1", password="testpass123"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.course = Course.objects.create(
            name="Test Course",
            description="Test Description",
            code="TEST101",
        )

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

    def test_course_can_have_multiple_teachers(self):
        """Test course can have multiple teachers."""
        CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
            role="owner",
        )

        teacher_user2 = self.User.objects.create_user(
            username="teacher2", password="testpass123"
        )
        teacher2 = Teacher.objects.create(user=teacher_user2)

        CourseTeacher.objects.create(
            course=self.course,
            teacher=teacher2,
            role="co_teacher",
        )

        teachers = list(self.course.teachers.all())
        self.assertEqual(len(teachers), 2)
        self.assertIn(self.teacher, teachers)
        self.assertIn(teacher2, teachers)

    def test_course_can_have_multiple_students(self):
        """Test course can have multiple students."""
        CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )

        student_user2 = self.User.objects.create_user(
            username="student2", password="testpass123"
        )
        student2 = Student.objects.create(user=student_user2)

        CourseEnrollment.objects.create(
            course=self.course,
            student=student2,
        )

        students = list(self.course.students.all())
        self.assertEqual(len(students), 2)
        self.assertIn(self.student, students)
        self.assertIn(student2, students)

    def test_course_can_have_multiple_homeworks(self):
        """Test course can have multiple homeworks."""
        # Homework now has direct FK to Course
        homework2 = Homework.objects.create(
            title="Test Homework 2",
            description="Second homework",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=14),
        )

        # Check that both homeworks are associated with the course
        homeworks = list(self.course.homeworks.all())
        self.assertEqual(len(homeworks), 2)
        self.assertIn(self.homework, homeworks)
        self.assertIn(homework2, homeworks)

    def test_student_can_be_in_multiple_courses(self):
        """Test student can be enrolled in multiple courses."""
        CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )

        course2 = Course.objects.create(
            name="Test Course 2",
            description="Test Description 2",
            code="TEST201",
        )

        CourseEnrollment.objects.create(
            course=course2,
            student=self.student,
        )

        courses = list(self.student.enrolled_courses.all())
        self.assertEqual(len(courses), 2)
        self.assertIn(self.course, courses)
        self.assertIn(course2, courses)

    def test_teacher_can_be_in_multiple_courses(self):
        """Test teacher can be in multiple courses."""
        CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
        )

        course2 = Course.objects.create(
            name="Test Course 2",
            description="Test Description 2",
            code="TEST201",
        )

        CourseTeacher.objects.create(
            course=course2,
            teacher=self.teacher,
        )

        courses = list(self.teacher.courses.all())
        self.assertEqual(len(courses), 2)
        self.assertIn(self.course, courses)
        self.assertIn(course2, courses)


class CourseCascadeDeleteTest(TestCase):
    """Test cases for cascade deletes."""

    def setUp(self):
        self.User = get_user_model()

        self.teacher_user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = self.User.objects.create_user(
            username="student1", password="testpass123"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.course = Course.objects.create(
            name="Test Course",
            description="Test Description",
            code="TEST101",
        )

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

    def test_course_delete_removes_course_teacher(self):
        """Test deleting course removes CourseTeacher records."""
        course_teacher = CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
        )
        course_teacher_id = course_teacher.id

        self.course.delete()
        self.assertFalse(CourseTeacher.objects.filter(id=course_teacher_id).exists())

    def test_course_delete_removes_course_enrollment(self):
        """Test deleting course removes CourseEnrollment records."""
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )
        enrollment_id = enrollment.id

        self.course.delete()
        self.assertFalse(CourseEnrollment.objects.filter(id=enrollment_id).exists())

    def test_course_delete_removes_course_homework(self):
        """Test deleting course cascades to homework (via FK)."""
        # Homework now has direct FK to Course with CASCADE
        homework_id = self.homework.id

        self.course.delete()
        # Homework should be deleted when course is deleted
        self.assertFalse(Homework.objects.filter(id=homework_id).exists())

    def test_teacher_delete_removes_course_teacher(self):
        """Test deleting teacher removes CourseTeacher records."""
        course_teacher = CourseTeacher.objects.create(
            course=self.course,
            teacher=self.teacher,
        )
        course_teacher_id = course_teacher.id

        self.teacher.delete()
        self.assertFalse(CourseTeacher.objects.filter(id=course_teacher_id).exists())

    def test_student_delete_removes_course_enrollment(self):
        """Test deleting student removes CourseEnrollment records."""
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
        )
        enrollment_id = enrollment.id

        self.student.delete()
        self.assertFalse(CourseEnrollment.objects.filter(id=enrollment_id).exists())


class CourseEdgeCasesTest(TestCase):
    """Test cases for course model edge cases."""

    def setUp(self):
        self.User = get_user_model()
        self.teacher_user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

    def test_course_with_very_long_name(self):
        """Test course with very long name."""
        long_name = "A" * 200
        course = Course.objects.create(
            name=long_name,
            description="Test description",
            code="LONG01",
        )
        self.assertEqual(course.name, long_name)

    def test_course_with_very_long_description(self):
        """Test course with very long description."""
        long_description = "A" * 10000
        course = Course.objects.create(
            name="Test Course",
            description=long_description,
            code="DESC01",
        )
        self.assertEqual(course.description, long_description)

    def test_course_with_very_long_code(self):
        """Test course with maximum length code."""
        long_code = "A" * 20
        course = Course.objects.create(
            name="Test Course",
            description="Test description",
            code=long_code,
        )
        self.assertEqual(course.code, long_code)

    def test_course_with_special_characters_in_name(self):
        """Test course with special characters in name."""
        special_name = "Test Course @#$%^&*()"
        course = Course.objects.create(
            name=special_name,
            description="Test description",
            code="SPEC01",
        )
        self.assertEqual(course.name, special_name)

    def test_course_with_special_characters_in_code(self):
        """Test course with special characters in code."""
        special_code = "CS101-2025"
        course = Course.objects.create(
            name="Test Course",
            description="Test description",
            code=special_code,
        )
        self.assertEqual(course.code, special_code)

    def test_course_with_empty_description(self):
        """Test course with empty description."""
        course = Course.objects.create(
            name="Test Course",
            description="",
            code="EMPTY01",
        )
        self.assertEqual(course.description, "")

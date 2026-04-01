"""
Tests for the courses app views.

This module tests the views in the courses app, focusing on testing
the behavior of the course list view and course enrollment.
"""

from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model

from courses.models import Course, CourseEnrollment, CourseTeacher, CourseTeacherAssistant
from courses.views import CourseListView, CourseListData
from accounts.models import Teacher, Student, TeacherAssistant

User = get_user_model()


class CourseListViewTests(TestCase):
    """Tests for the CourseListView."""

    def setUp(self):
        """Set up test data."""
        # Create users and profiles
        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.teacher_user = User.objects.create_user(
            username="testteacher", email="teacher@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create some active courses
        self.course1 = Course.objects.create(
            name="Introduction to Python",
            code="PY101",
            description="Learn Python basics",
            is_active=True,
        )

        self.course2 = Course.objects.create(
            name="Advanced Django",
            code="DJ201",
            description="Master Django framework",
            is_active=True,
        )

        # Create an inactive course (should not appear in list)
        self.inactive_course = Course.objects.create(
            name="Old Course",
            code="OLD999",
            description="This course is inactive",
            is_active=False,
        )

        # Create the request factory
        self.factory = RequestFactory()

    def test_get_view_data_for_student_shows_all_active_courses(self):
        """Test that students see all active courses."""
        view = CourseListView()
        data = view._get_view_data(self.student_user)

        # Check if data is of the correct type
        self.assertIsInstance(data, CourseListData)

        # Check if the user type is correctly identified
        self.assertIn("student", data.user_types)

        # Check that all active courses are included
        self.assertEqual(len(data.courses), 2)
        course_ids = [course.id for course in data.courses]
        self.assertIn(self.course1.id, course_ids)
        self.assertIn(self.course2.id, course_ids)

        # Check that inactive course is not included
        self.assertNotIn(self.inactive_course.id, course_ids)

    def test_get_view_data_shows_enrollment_status(self):
        """Test that courses show correct enrollment status."""
        # Enroll student in course1
        CourseEnrollment.objects.create(
            course=self.course1, student=self.student, is_active=True
        )

        view = CourseListView()
        data = view._get_view_data(self.student_user)

        # Find the courses in the returned data
        course1_data = next(c for c in data.courses if c.id == self.course1.id)
        course2_data = next(c for c in data.courses if c.id == self.course2.id)

        # Check enrollment status
        self.assertTrue(course1_data.is_enrolled)
        self.assertFalse(course2_data.is_enrolled)

    def test_get_view_data_inactive_enrollment_shows_as_not_enrolled(self):
        """Test that inactive enrollment shows as not enrolled."""
        # Create inactive enrollment
        CourseEnrollment.objects.create(
            course=self.course1, student=self.student, is_active=False
        )

        view = CourseListView()
        data = view._get_view_data(self.student_user)

        course1_data = next(c for c in data.courses if c.id == self.course1.id)
        self.assertFalse(course1_data.is_enrolled)

    def test_course_list_view_get_renders_correctly(self):
        """Test that the CourseListView GET request renders correctly."""
        request = self.factory.get("/courses/")
        request.user = self.student_user

        view = CourseListView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)

    def test_course_list_view_requires_login(self):
        """Test that the CourseListView requires authentication."""
        # Create an anonymous user request
        self.client.logout()
        response = self.client.get(reverse("courses:list"))

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_get_view_data_for_teacher_shows_only_teaching_courses(self):
        """Test that teachers see only courses they are teaching."""
        # Add teacher to course1 as owner
        CourseTeacher.objects.create(
            course=self.course1, teacher=self.teacher, role="owner"
        )

        view = CourseListView()
        data = view._get_view_data(self.teacher_user)

        # Check if data is of the correct type
        self.assertIsInstance(data, CourseListData)

        # Check if the user type is correctly identified
        self.assertIn("teacher", data.user_types)

        # Check that only course1 is included (teacher is teaching it)
        self.assertEqual(len(data.courses), 1)
        self.assertEqual(data.courses[0].id, self.course1.id)

        # Check that course2 is not included (teacher is not teaching it)
        course_ids = [course.id for course in data.courses]
        self.assertNotIn(self.course2.id, course_ids)

    def test_get_view_data_for_teacher_with_multiple_courses(self):
        """Test that teachers see all courses they teach."""
        # Add teacher to both courses
        CourseTeacher.objects.create(
            course=self.course1, teacher=self.teacher, role="owner"
        )
        CourseTeacher.objects.create(
            course=self.course2, teacher=self.teacher, role="co_teacher"
        )

        view = CourseListView()
        data = view._get_view_data(self.teacher_user)

        # Check that both courses are included
        self.assertEqual(len(data.courses), 2)
        course_ids = [course.id for course in data.courses]
        self.assertIn(self.course1.id, course_ids)
        self.assertIn(self.course2.id, course_ids)

    def test_get_view_data_for_teacher_shows_no_courses_when_not_teaching(self):
        """Test that teachers see no courses when they aren't teaching any."""
        view = CourseListView()
        data = view._get_view_data(self.teacher_user)

        # Check that no courses are shown
        self.assertEqual(len(data.courses), 0)

    def test_course_list_view_for_teacher_renders_correctly(self):
        """Test that the CourseListView GET request renders correctly for teachers."""
        # Add teacher to a course
        CourseTeacher.objects.create(
            course=self.course1, teacher=self.teacher, role="owner"
        )

        self.client.login(username="testteacher", password="password123")
        response = self.client.get(reverse("courses:list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "courses/list.html")

    def test_get_view_data_for_multi_role_user_shows_all_courses(self):
        """Test that users with multiple profiles see courses from all roles."""
        # Create a user with both student and TA profiles
        multi_user = User.objects.create_user(
            username="multirole", email="multi@example.com", password="password123"
        )
        student_profile = Student.objects.create(user=multi_user)
        ta_profile = TeacherAssistant.objects.create(user=multi_user)

        # Create a third course
        course3 = Course.objects.create(
            name="Course 3", code="C3", description="Test", is_active=True
        )

        # Enroll as student in course1
        CourseEnrollment.objects.create(
            course=self.course1, student=student_profile, is_active=True
        )

        # Assign as TA to course2
        CourseTeacherAssistant.objects.create(
            course=self.course2, teacher_assistant=ta_profile
        )

        # Get view data
        view = CourseListView()
        data = view._get_view_data(multi_user)

        # Should have both student and TA in user_types
        self.assertIn('student', data.user_types)
        self.assertIn('teacher_assistant', data.user_types)
        self.assertEqual(len(data.user_types), 2)

        # Should see courses from both roles plus course3 (active, available for enrollment)
        self.assertEqual(len(data.courses), 3)

        # Find courses in list
        course1_item = next(c for c in data.courses if c.id == self.course1.id)
        course2_item = next(c for c in data.courses if c.id == self.course2.id)
        course3_item = next(c for c in data.courses if c.id == course3.id)

        # Verify roles
        self.assertIn('student', course1_item.roles)
        self.assertTrue(course1_item.is_enrolled)

        self.assertIn('teacher_assistant', course2_item.roles)
        self.assertFalse(course2_item.is_enrolled)

        # course3 should have no roles (not enrolled, not TA)
        self.assertEqual(len(course3_item.roles), 0)
        self.assertFalse(course3_item.is_enrolled)


class CourseEnrollViewTests(TestCase):
    """Tests for the CourseEnrollView."""

    def setUp(self):
        """Set up test data."""
        # Create users and profiles
        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.teacher_user = User.objects.create_user(
            username="testteacher", email="teacher@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create a course
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course",
            is_active=True,
        )

        # Create the request factory
        self.factory = RequestFactory()

    def test_enroll_creates_enrollment(self):
        """Test that posting to enroll view creates enrollment."""
        self.client.login(username="teststudent", password="password123")

        response = self.client.post(
            reverse("courses:enroll", kwargs={"course_id": self.course.id})
        )

        # Should redirect to course list
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("courses:list"))

        # Check that enrollment was created
        enrollment = CourseEnrollment.objects.filter(
            course=self.course, student=self.student
        ).first()
        self.assertIsNotNone(enrollment)
        self.assertTrue(enrollment.is_active)

    def test_enroll_does_not_duplicate_enrollment(self):
        """Test that enrolling twice doesn't create duplicate enrollments."""
        # Create an initial enrollment
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )

        self.client.login(username="teststudent", password="password123")

        response = self.client.post(
            reverse("courses:enroll", kwargs={"course_id": self.course.id})
        )

        # Should still succeed
        self.assertEqual(response.status_code, 302)

        # Check that only one enrollment exists
        enrollment_count = CourseEnrollment.objects.filter(
            course=self.course, student=self.student
        ).count()
        self.assertEqual(enrollment_count, 1)

    def test_enroll_reactivates_inactive_enrollment(self):
        """Test that enrolling reactivates an inactive enrollment."""
        # Create an inactive enrollment
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=False
        )

        self.client.login(username="teststudent", password="password123")

        response = self.client.post(
            reverse("courses:enroll", kwargs={"course_id": self.course.id})
        )

        # Should succeed
        self.assertEqual(response.status_code, 302)

        # Check that enrollment is now active
        enrollment = CourseEnrollment.objects.get(
            course=self.course, student=self.student
        )
        self.assertTrue(enrollment.is_active)

    def test_enroll_requires_login(self):
        """Test that enrolling requires authentication."""
        self.client.logout()
        response = self.client.post(
            reverse("courses:enroll", kwargs={"course_id": self.course.id})
        )

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_enroll_requires_student(self):
        """Test that enrolling requires student access."""
        self.client.login(username="testteacher", password="password123")

        response = self.client.post(
            reverse("courses:enroll", kwargs={"course_id": self.course.id})
        )

        # Should return forbidden for non-students
        self.assertEqual(response.status_code, 403)

    def test_enroll_requires_active_course(self):
        """Test that enrolling in inactive course fails."""
        inactive_course = Course.objects.create(
            name="Inactive Course",
            code="INACT999",
            description="This is inactive",
            is_active=False,
        )

        self.client.login(username="teststudent", password="password123")

        response = self.client.post(
            reverse("courses:enroll", kwargs={"course_id": inactive_course.id})
        )

        # Should return forbidden
        self.assertEqual(response.status_code, 403)

        # Check that no enrollment was created
        enrollment_count = CourseEnrollment.objects.filter(
            course=inactive_course, student=self.student
        ).count()
        self.assertEqual(enrollment_count, 0)


class CourseCreateViewTests(TestCase):
    """Tests for the CourseCreateView."""

    def setUp(self):
        """Set up test data."""
        # Create users and profiles
        self.teacher_user = User.objects.create_user(
            username="testteacher", email="teacher@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

    def test_get_create_form_renders(self):
        """Test that the create form renders correctly for teachers."""
        self.client.login(username="testteacher", password="password123")

        response = self.client.get(reverse("courses:create"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "courses/form.html")

    def test_create_course_success(self):
        """Test that teachers can create courses successfully."""
        self.client.login(username="testteacher", password="password123")

        course_data = {
            "name": "New Course",
            "code": "NEW101",
            "description": "A brand new course",
        }

        response = self.client.post(reverse("courses:create"), course_data)

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that course was created
        course = Course.objects.get(code="NEW101")
        self.assertEqual(course.name, "New Course")
        self.assertEqual(course.description, "A brand new course")
        self.assertTrue(course.is_active)

        # Check that teacher is added as owner
        course_teacher = CourseTeacher.objects.get(course=course, teacher=self.teacher)
        self.assertEqual(course_teacher.role, "owner")

    def test_create_course_duplicate_code_fails(self):
        """Test that creating a course with duplicate code fails."""
        # Create initial course
        Course.objects.create(
            name="Existing Course",
            code="EXISTING101",
            description="Already exists",
        )

        self.client.login(username="testteacher", password="password123")

        course_data = {
            "name": "New Course",
            "code": "EXISTING101",  # Duplicate code
            "description": "This should fail",
        }

        response = self.client.post(reverse("courses:create"), course_data)

        # Should not redirect (form has errors)
        self.assertEqual(response.status_code, 200)

        # Check that no new course was created
        course_count = Course.objects.filter(code="EXISTING101").count()
        self.assertEqual(course_count, 1)

    def test_create_course_requires_login(self):
        """Test that creating a course requires authentication."""
        self.client.logout()

        response = self.client.get(reverse("courses:create"))

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_create_course_requires_teacher(self):
        """Test that creating a course requires teacher access."""
        self.client.login(username="teststudent", password="password123")

        response = self.client.get(reverse("courses:create"))

        # Should return forbidden for non-teachers
        self.assertEqual(response.status_code, 403)

    def test_create_course_missing_required_fields(self):
        """Test that creating a course with missing fields fails."""
        self.client.login(username="testteacher", password="password123")

        # Missing name and code
        course_data = {
            "description": "Missing required fields",
        }

        response = self.client.post(reverse("courses:create"), course_data)

        # Should not redirect (form has errors)
        self.assertEqual(response.status_code, 200)

        # Check that no course was created
        self.assertEqual(Course.objects.count(), 0)

    def test_create_course_with_empty_description(self):
        """Test that courses can be created with empty description."""
        self.client.login(username="testteacher", password="password123")

        course_data = {
            "name": "Minimal Course",
            "code": "MIN101",
            "description": "",  # Empty description should be allowed
        }

        response = self.client.post(reverse("courses:create"), course_data)

        # Should succeed
        self.assertEqual(response.status_code, 302)

        # Check that course was created
        course = Course.objects.get(code="MIN101")
        self.assertEqual(course.name, "Minimal Course")
        self.assertEqual(course.description, "")


class CourseDetailViewTests(TestCase):
    """Tests for the CourseDetailView."""

    def setUp(self):
        """Set up test data."""
        # Create users and profiles
        self.teacher_user = User.objects.create_user(
            username="testteacher", email="teacher@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.other_student_user = User.objects.create_user(
            username="otherstudent",
            email="otherstudent@example.com",
            password="password123",
        )
        self.other_student = Student.objects.create(user=self.other_student_user)

        # Create a course
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
            is_active=True,
        )

        # Add teacher as owner
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )

        # Enroll student in course
        CourseEnrollment.objects.create(
            course=self.course, student=self.student, is_active=True
        )

        # Create homeworks
        from homeworks.models import Homework
        from django.utils import timezone
        from datetime import timedelta

        self.homework1 = Homework.objects.create(
            title="Homework 1",
            description="First homework",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.homework2 = Homework.objects.create(
            title="Homework 2",
            description="Second homework",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=14),
        )

    def test_teacher_can_view_course_detail(self):
        """Test that teachers can view their course details."""
        self.client.login(username="testteacher", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "courses/detail.html")

    def test_teacher_sees_homeworks_in_course_detail(self):
        """Test that teachers see homeworks associated with the course."""
        self.client.login(username="testteacher", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        # Check that homeworks are in the context
        self.assertIn("data", response.context)
        data = response.context["data"]

        # Should have 2 homeworks
        self.assertEqual(len(data.homeworks), 2)

        # Check homework IDs
        homework_ids = [hw.id for hw in data.homeworks]
        self.assertIn(self.homework1.id, homework_ids)
        self.assertIn(self.homework2.id, homework_ids)

    def test_teacher_sees_enrolled_students_in_course_detail(self):
        """Test that teachers see enrolled students in the course."""
        self.client.login(username="testteacher", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        data = response.context["data"]

        # Should have 1 enrolled student
        self.assertEqual(len(data.enrolled_students), 1)
        self.assertEqual(data.enrolled_students[0].id, self.student.id)

    def test_student_can_view_enrolled_course_detail(self):
        """Test that students can view courses they're enrolled in."""
        self.client.login(username="teststudent", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "courses/detail.html")

    def test_student_sees_homeworks_in_course_detail(self):
        """Test that students see homeworks associated with the course."""
        self.client.login(username="teststudent", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        data = response.context["data"]

        # Should have 2 homeworks
        self.assertEqual(len(data.homeworks), 2)

        # Check homework IDs
        homework_ids = [hw.id for hw in data.homeworks]
        self.assertIn(self.homework1.id, homework_ids)
        self.assertIn(self.homework2.id, homework_ids)

    def test_student_does_not_see_enrolled_students(self):
        """Test that students don't see the list of enrolled students."""
        self.client.login(username="teststudent", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        data = response.context["data"]

        # Students should not see enrolled_students list
        self.assertIsNone(data.enrolled_students)

    def test_student_cannot_view_unenrolled_course(self):
        """Test that students cannot view courses they're not enrolled in."""
        self.client.login(username="otherstudent", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        # Should return forbidden
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_view_course_they_dont_teach(self):
        """Test that teachers cannot view courses they don't teach."""
        # Create another teacher
        other_teacher_user = User.objects.create_user(
            username="otherteacher",
            email="otherteacher@example.com",
            password="password123",
        )
        Teacher.objects.create(user=other_teacher_user)

        self.client.login(username="otherteacher", password="password123")

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        # Should return forbidden
        self.assertEqual(response.status_code, 403)

    def test_course_detail_requires_login(self):
        """Test that viewing course detail requires authentication."""
        self.client.logout()

        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_course_detail_shows_correct_user_type(self):
        """Test that course detail correctly identifies user type."""
        # Test for teacher
        self.client.login(username="testteacher", password="password123")
        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )
        self.assertIn("teacher", response.context["data"].user_roles)

        # Test for student
        self.client.login(username="teststudent", password="password123")
        response = self.client.get(
            reverse("courses:detail", kwargs={"course_id": self.course.id})
        )
        self.assertIn("student", response.context["data"].user_roles)


class CourseHomeworkCreateViewTests(TestCase):
    """Tests for creating homeworks within a course context."""

    def setUp(self):
        """Set up test data."""
        from llm.models import LLMConfig

        # Create users and profiles
        self.teacher_user = User.objects.create_user(
            username="testteacher", email="teacher@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.other_teacher_user = User.objects.create_user(
            username="otherteacher",
            email="otherteacher@example.com",
            password="password123",
        )
        self.other_teacher = Teacher.objects.create(user=self.other_teacher_user)

        self.student_user = User.objects.create_user(
            username="teststudent", email="student@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create a course
        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course",
            is_active=True,
        )

        # Add teacher as owner
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )

        # Create LLM config for homework
        self.llm_config = LLMConfig.objects.create(
            name="Test LLM",
            model_name="gpt-4",
            api_key="test-api-key",
            base_prompt="You are a helpful AI tutor.",
        )

    def test_get_homework_create_form_renders(self):
        """Test that the homework create form renders for teachers."""
        self.client.login(username="testteacher", password="password123")

        response = self.client.get(
            reverse("courses:homework-create", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "courses/homework_form.html")

    def test_create_homework_for_course_success(self):
        """Test that teachers can create homeworks for their courses."""
        self.client.login(username="testteacher", password="password123")

        from django.utils import timezone
        from datetime import timedelta

        due_date = timezone.now() + timedelta(days=7)

        homework_data = {
            "title": "New Homework",
            "description": "Homework description",
            "due_date": due_date.strftime("%Y-%m-%dT%H:%M"),
            "llm_config": self.llm_config.id,
            # Section data
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "0",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-title": "Section 1",
            "sections-0-content": "Section content",
            "sections-0-order": "1",
            "sections-0-solution": "Section solution",
            "sections-0-section_type": "conversation",
        }

        response = self.client.post(
            reverse("courses:homework-create", kwargs={"course_id": self.course.id}),
            homework_data,
        )

        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check that homework was created
        from homeworks.models import Homework

        homework = Homework.objects.get(title="New Homework")
        self.assertEqual(homework.description, "Homework description")
        self.assertEqual(homework.created_by, self.teacher)

        # Check that homework is linked to course via FK
        self.assertEqual(homework.course, self.course)

        # Check that section was created
        self.assertEqual(homework.sections.count(), 1)
        section = homework.sections.first()
        self.assertEqual(section.title, "Section 1")

    def test_create_homework_requires_teacher(self):
        """Test that creating homework requires teacher access."""
        self.client.login(username="teststudent", password="password123")

        response = self.client.get(
            reverse("courses:homework-create", kwargs={"course_id": self.course.id})
        )

        # Should return forbidden
        self.assertEqual(response.status_code, 403)

    def test_create_homework_requires_teacher_owns_course(self):
        """Test that only teachers who teach the course can create homeworks."""
        self.client.login(username="otherteacher", password="password123")

        response = self.client.get(
            reverse("courses:homework-create", kwargs={"course_id": self.course.id})
        )

        # Should return forbidden
        self.assertEqual(response.status_code, 403)

    def test_create_homework_requires_login(self):
        """Test that creating homework requires authentication."""
        self.client.logout()

        response = self.client.get(
            reverse("courses:homework-create", kwargs={"course_id": self.course.id})
        )

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_create_homework_missing_sections(self):
        """Test that creating homework without sections fails."""
        self.client.login(username="testteacher", password="password123")

        from django.utils import timezone
        from datetime import timedelta

        due_date = timezone.now() + timedelta(days=7)

        homework_data = {
            "title": "Homework Without Sections",
            "description": "This should fail",
            "due_date": due_date.strftime("%Y-%m-%dT%H:%M"),
            "llm_config": self.llm_config.id,
            # No sections
            "sections-TOTAL_FORMS": "0",
            "sections-INITIAL_FORMS": "0",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
        }

        response = self.client.post(
            reverse("courses:homework-create", kwargs={"course_id": self.course.id}),
            homework_data,
        )

        # Should not redirect (form has errors)
        self.assertEqual(response.status_code, 200)

        # Check that no homework was created
        from homeworks.models import Homework

        self.assertFalse(
            Homework.objects.filter(title="Homework Without Sections").exists()
        )

    def test_create_homework_with_past_due_date_fails(self):
        """Test that creating homework with past due date fails."""
        self.client.login(username="testteacher", password="password123")

        from django.utils import timezone
        from datetime import timedelta

        past_date = timezone.now() - timedelta(days=1)

        homework_data = {
            "title": "Past Due Homework",
            "description": "This should fail",
            "due_date": past_date.strftime("%Y-%m-%dT%H:%M"),
            "llm_config": self.llm_config.id,
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "0",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-title": "Section 1",
            "sections-0-content": "Content",
            "sections-0-order": "1",
            "sections-0-solution": "",
            "sections-0-section_type": "conversation",
        }

        response = self.client.post(
            reverse("courses:homework-create", kwargs={"course_id": self.course.id}),
            homework_data,
        )

        # Should not redirect (form has errors)
        self.assertEqual(response.status_code, 200)

        # Check that no homework was created
        from homeworks.models import Homework

        self.assertFalse(Homework.objects.filter(title="Past Due Homework").exists())

    def test_homework_redirects_to_course_detail_on_success(self):
        """Test that successful creation redirects to course detail page."""
        self.client.login(username="testteacher", password="password123")

        from django.utils import timezone
        from datetime import timedelta

        due_date = timezone.now() + timedelta(days=7)

        homework_data = {
            "title": "Redirect Test Homework",
            "description": "Test",
            "due_date": due_date.strftime("%Y-%m-%dT%H:%M"),
            "llm_config": self.llm_config.id,
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "0",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-title": "Section 1",
            "sections-0-content": "Content",
            "sections-0-order": "1",
            "sections-0-solution": "",
            "sections-0-section_type": "conversation",
        }

        response = self.client.post(
            reverse("courses:homework-create", kwargs={"course_id": self.course.id}),
            homework_data,
        )

        # Should redirect to course detail
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("courses:detail", kwargs={"course_id": self.course.id}),
        )


class CourseHomeworkCreateSectionTypeTests(TestCase):
    """Test that section_type is saved correctly when creating homeworks."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone

        self.teacher_user = User.objects.create_user(
            username="teacher_st", email="teacher_st@example.com", password="password"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.course = Course.objects.create(name="Course", code="C101ST", description="")
        CourseTeacher.objects.create(course=self.course, teacher=self.teacher, role="owner")

        from llm.models import LLMConfig
        self.llm_config = LLMConfig.objects.create(
            name="Test LLM",
            model_name="gpt-4",
            api_key="key",
            base_prompt="prompt",
            course=self.course,
        )

        self.due_date = (timezone.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")
        self.url = reverse("courses:homework-create", kwargs={"course_id": self.course.id})

    def _base_post_data(self):
        return {
            "title": "HW",
            "description": "desc",
            "due_date": self.due_date,
            "llm_config": self.llm_config.id,
            "sections-TOTAL_FORMS": "1",
            "sections-INITIAL_FORMS": "0",
            "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-title": "Q1",
            "sections-0-content": "Content",
            "sections-0-order": "1",
            "sections-0-solution": "",
        }

    def test_create_non_interactive_section(self):
        self.client.login(username="teacher_st", password="password")
        data = self._base_post_data()
        data["sections-0-section_type"] = "non_interactive"

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)

        from homeworks.models import Homework
        hw = Homework.objects.get(title="HW", course=self.course)
        self.assertEqual(hw.sections.first().section_type, "non_interactive")

    def test_create_conversation_section(self):
        self.client.login(username="teacher_st", password="password")
        data = self._base_post_data()
        data["sections-0-section_type"] = "conversation"

        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)

        from homeworks.models import Homework
        hw = Homework.objects.get(title="HW", course=self.course)
        self.assertEqual(hw.sections.first().section_type, "conversation")

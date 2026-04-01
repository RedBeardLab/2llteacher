"""
Tests for the homework submissions view.

This module tests the HomeworkSubmissionsView and related functionality,
including the service layer method for getting homework submissions.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4

from accounts.models import Teacher, Student
from homeworks.models import Homework, Section, SectionSolution
from homeworks.services import HomeworkService, ParticipationStatus
from conversations.models import Conversation, Message, Submission
from courses.models import Course, CourseEnrollment

User = get_user_model()


class HomeworkSubmissionsViewTest(TestCase):
    """Test cases for the homework submissions view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create teacher user and profile
        self.teacher_user = User.objects.create_user(
            username="teacher1",
            email="teacher1@example.com",
            password="password123",
            first_name="John",
            last_name="Teacher",
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create another teacher for permission testing
        self.other_teacher_user = User.objects.create_user(
            username="teacher2", email="teacher2@example.com", password="password123"
        )
        self.other_teacher = Teacher.objects.create(user=self.other_teacher_user)

        # Create student users and profiles
        self.student1_user = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="password123",
            first_name="Alice",
            last_name="Student",
        )
        self.student1 = Student.objects.create(user=self.student1_user)

        self.student2_user = User.objects.create_user(
            username="student2",
            email="student2@example.com",
            password="password123",
            first_name="Bob",
            last_name="Student",
        )
        self.student2 = Student.objects.create(user=self.student2_user)

        self.student3_user = User.objects.create_user(
            username="student3",
            email="student3@example.com",
            password="password123",
            first_name="Charlie",
            last_name="Student",
        )
        self.student3 = Student.objects.create(user=self.student3_user)

        # Create course and enroll students
        self.course = Course.objects.create(
            name="Test Course",
            description="Test course description",
            code="TEST101",
        )

        # Enroll students in the course
        CourseEnrollment.objects.create(course=self.course, student=self.student1)
        CourseEnrollment.objects.create(course=self.course, student=self.student2)
        CourseEnrollment.objects.create(course=self.course, student=self.student3)

        # Create homework with course assigned
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        # Create sections
        self.section1 = Section.objects.create(
            homework=self.homework,
            title="Section 1",
            content="Section 1 content",
            order=1,
        )

        self.section2 = Section.objects.create(
            homework=self.homework,
            title="Section 2",
            content="Section 2 content",
            order=2,
        )

        # Create solution for section 1
        self.solution1 = SectionSolution.objects.create(
            content="Solution for section 1"
        )
        self.section1.solution = self.solution1
        self.section1.save()

        # Create conversations and submissions for testing
        self._create_test_conversations()

    def _create_test_conversations(self):
        """Create test conversations and submissions."""
        # Student 1: Has conversations for both sections, submitted section 1
        self.conv1_s1 = Conversation.objects.create(
            user=self.student1_user, section=self.section1
        )
        Message.objects.create(
            conversation=self.conv1_s1,
            content="Student message",
            message_type="student",
        )
        Message.objects.create(
            conversation=self.conv1_s1, content="AI response", message_type="ai"
        )

        # Submit section 1 for student 1
        Submission.objects.create(conversation=self.conv1_s1)

        # Student 1 also has conversation for section 2 (not submitted)
        self.conv1_s2 = Conversation.objects.create(
            user=self.student1_user, section=self.section2
        )
        Message.objects.create(
            conversation=self.conv1_s2,
            content="Student message for section 2",
            message_type="student",
        )

        # Student 2: Has conversation for section 1 only (not submitted)
        self.conv2_s1 = Conversation.objects.create(
            user=self.student2_user, section=self.section1
        )
        Message.objects.create(
            conversation=self.conv2_s1,
            content="Student 2 message",
            message_type="student",
        )

        # Student 2 also has a soft-deleted conversation
        self.conv2_deleted = Conversation.objects.create(
            user=self.student2_user,
            section=self.section1,
            is_deleted=True,
            deleted_at=timezone.now(),
        )
        Message.objects.create(
            conversation=self.conv2_deleted,
            content="Deleted conversation message",
            message_type="student",
        )

        # Student 3: No conversations (should show as no interaction)

    def test_submissions_view_requires_login(self):
        """Test that submissions view requires login."""
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_submissions_view_requires_teacher(self):
        """Test that submissions view requires teacher role."""
        # Login as student
        self.client.login(username="student1", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_submissions_view_requires_homework_ownership(self):
        """Test that teacher can only view submissions for their own homeworks."""
        # Login as different teacher
        self.client.login(username="teacher2", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_submissions_view_nonexistent_homework(self):
        """Test submissions view with nonexistent homework."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect to list

    def test_submissions_view_success(self):
        """Test successful submissions view."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Homework - Submissions")
        self.assertContains(response, "Alice Student")
        self.assertContains(response, "Bob Student")
        self.assertContains(response, "Charlie Student")

    def test_submissions_view_shows_all_students(self):
        """Test that submissions view shows all students including non-participating ones."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        # Check that all students are shown
        self.assertContains(response, "student1@example.com")
        self.assertContains(response, "student2@example.com")
        self.assertContains(response, "student3@example.com")

        # Check statistics
        self.assertContains(response, "3")  # Total students
        self.assertContains(response, "2")  # Active students (student1 and student2)
        self.assertContains(response, "1")  # Inactive students (student3)
        self.assertContains(response, "1")  # Total submissions (student1's submission)

    def test_submissions_view_shows_participation_status(self):
        """Test that submissions view shows correct participation status."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        # Student 1 should be active (has submission)
        self.assertContains(response, "Active")

        # Student 2 should be partial (has conversations but no submissions)
        self.assertContains(response, "Partial Progress")

        # Student 3 should show no interaction
        self.assertContains(response, "No Interaction")

    def test_submissions_view_shows_conversations(self):
        """Test that submissions view shows conversations in reverse chronological order."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        # Check that conversations are shown
        self.assertContains(response, "Section 1: Section 1")
        self.assertContains(response, "Section 2: Section 2")

        # Check that submission status is shown
        self.assertContains(response, "Submitted")

        # Check that soft-deleted conversations are included
        self.assertContains(response, "Deleted")

    def test_submissions_view_shows_warning_for_non_participating_students(self):
        """Test that submissions view shows warning for non-participating students."""
        self.client.login(username="teacher1", password="password123")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        # Check warning message
        self.assertContains(response, "1 Student(s) Not Participating")
        self.assertContains(response, "have not started this homework")


class HomeworkSubmissionsServiceTest(TestCase):
    """Test cases for the homework submissions service method."""

    def setUp(self):
        """Set up test data."""
        # Create teacher
        self.teacher_user = User.objects.create_user(
            username="teacher1", email="teacher1@example.com", password="password123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create students
        self.student1_user = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="password123",
            first_name="Alice",
            last_name="Student",
        )
        self.student1 = Student.objects.create(user=self.student1_user)

        self.student2_user = User.objects.create_user(
            username="student2",
            email="student2@example.com",
            password="password123",
            first_name="Bob",
            last_name="Student",
        )
        self.student2 = Student.objects.create(user=self.student2_user)

        # Create course and enroll students
        self.course = Course.objects.create(
            name="Test Course",
            description="Test course description",
            code="TEST101",
        )

        # Enroll students in the course
        CourseEnrollment.objects.create(course=self.course, student=self.student1)
        CourseEnrollment.objects.create(course=self.course, student=self.student2)

        # Create homework with sections
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.section1 = Section.objects.create(
            homework=self.homework,
            title="Section 1",
            content="Section 1 content",
            order=1,
        )

        self.section2 = Section.objects.create(
            homework=self.homework,
            title="Section 2",
            content="Section 2 content",
            order=2,
        )

    def test_get_homework_submissions_nonexistent_homework(self):
        """Test get_homework_submissions with nonexistent homework."""
        result = HomeworkService.get_homework_submissions(uuid4())
        self.assertIsNone(result)

    def test_get_homework_submissions_no_students(self):
        """Test get_homework_submissions with no students."""
        # Delete all students
        Student.objects.all().delete()
        User.objects.filter(username__startswith="student").delete()

        result = HomeworkService.get_homework_submissions(self.homework.id)

        self.assertIsNotNone(result)
        self.assertEqual(result.homework_id, self.homework.id)
        self.assertEqual(result.homework_title, "Test Homework")
        self.assertEqual(result.total_students, 0)
        self.assertEqual(result.active_students, 0)
        self.assertEqual(result.inactive_students, 0)
        self.assertEqual(result.total_submissions, 0)
        self.assertEqual(len(result.students), 0)

    def test_get_homework_submissions_no_interactions(self):
        """Test get_homework_submissions with students but no interactions."""
        result = HomeworkService.get_homework_submissions(self.homework.id)

        self.assertIsNotNone(result)
        self.assertEqual(result.total_students, 2)
        self.assertEqual(result.active_students, 0)
        self.assertEqual(result.inactive_students, 2)
        self.assertEqual(result.total_submissions, 0)

        # Check that all students have no_interaction status
        for student_summary in result.students:
            self.assertEqual(
                student_summary.participation_status, ParticipationStatus.NO_INTERACTION
            )
            self.assertFalse(student_summary.has_interactions)
            self.assertEqual(student_summary.total_conversations, 0)
            self.assertEqual(
                student_summary.missing_sections, 2
            )  # Both sections are missing

    def test_get_homework_submissions_with_interactions(self):
        """Test get_homework_submissions with student interactions."""
        # Create conversation for student1
        conv1 = Conversation.objects.create(
            user=self.student1_user, section=self.section1
        )
        Message.objects.create(
            conversation=conv1, content="Student message", message_type="student"
        )

        # Create submission for student1
        Submission.objects.create(conversation=conv1)

        # Create conversation for student2 (no submission)
        conv2 = Conversation.objects.create(
            user=self.student2_user, section=self.section1
        )
        Message.objects.create(
            conversation=conv2, content="Student 2 message", message_type="student"
        )

        result = HomeworkService.get_homework_submissions(self.homework.id)

        self.assertIsNotNone(result)
        self.assertEqual(result.total_students, 2)
        self.assertEqual(result.active_students, 2)  # Both have interactions
        self.assertEqual(result.inactive_students, 0)
        self.assertEqual(result.total_submissions, 1)  # Only student1 submitted

        # Find student summaries
        student1_summary = next(
            s for s in result.students if s.student_username == "student1"
        )
        student2_summary = next(
            s for s in result.students if s.student_username == "student2"
        )

        # Check student1 (active - has submission)
        self.assertEqual(
            student1_summary.participation_status, ParticipationStatus.ACTIVE
        )
        self.assertTrue(student1_summary.has_interactions)
        self.assertEqual(student1_summary.submitted_count, 1)
        self.assertEqual(student1_summary.total_conversations, 1)
        self.assertEqual(student1_summary.sections_started, 1)
        self.assertEqual(student1_summary.missing_sections, 1)  # Missing section 2

        # Check student2 (partial - has conversation but no submission)
        self.assertEqual(
            student2_summary.participation_status, ParticipationStatus.PARTIAL
        )
        self.assertTrue(student2_summary.has_interactions)
        self.assertEqual(student2_summary.submitted_count, 0)
        self.assertEqual(student2_summary.total_conversations, 1)
        self.assertEqual(student2_summary.sections_started, 1)
        self.assertEqual(student2_summary.missing_sections, 1)  # Missing section 2

    def test_get_homework_submissions_includes_soft_deleted(self):
        """Test that get_homework_submissions includes soft-deleted conversations."""
        # Create normal conversation
        _conv1 = Conversation.objects.create(
            user=self.student1_user, section=self.section1
        )

        # Create soft-deleted conversation
        _conv2 = Conversation.objects.create(
            user=self.student1_user,
            section=self.section2,
            is_deleted=True,
            deleted_at=timezone.now(),
        )

        result = HomeworkService.get_homework_submissions(self.homework.id)

        student1_summary = next(
            s for s in result.students if s.student_username == "student1"
        )

        # Should include both conversations across sections
        self.assertEqual(student1_summary.total_conversations, 2)
        self.assertEqual(
            student1_summary.sections_started, 2
        )  # Both sections have conversations
        self.assertEqual(student1_summary.missing_sections, 0)  # No missing sections

        # Check that deleted conversation is marked in the appropriate section
        section2_status = next(
            s for s in student1_summary.section_statuses if s.section_order == 2
        )
        self.assertEqual(len(section2_status.conversations), 1)
        deleted_conv = section2_status.conversations[0]
        self.assertTrue(deleted_conv.is_deleted)

    def test_get_homework_submissions_reverse_chronological_order(self):
        """Test that conversations are returned in reverse chronological order."""
        # Create conversations with different timestamps
        conv1 = Conversation.objects.create(
            user=self.student1_user, section=self.section1
        )

        # Update created_at to simulate different creation times
        conv1.created_at = timezone.now() - timedelta(hours=2)
        conv1.save()

        conv2 = Conversation.objects.create(
            user=self.student1_user, section=self.section2
        )
        conv2.created_at = timezone.now() - timedelta(hours=1)
        conv2.save()

        result = HomeworkService.get_homework_submissions(self.homework.id)

        student1_summary = next(
            s for s in result.students if s.student_username == "student1"
        )

        # Should have conversations in both sections
        self.assertEqual(student1_summary.total_conversations, 2)

        # Check that conversations within each section are in reverse chronological order
        # Since we have one conversation per section, we'll check the section ordering
        section1_status = next(
            s for s in student1_summary.section_statuses if s.section_order == 1
        )
        section2_status = next(
            s for s in student1_summary.section_statuses if s.section_order == 2
        )

        self.assertEqual(len(section1_status.conversations), 1)
        self.assertEqual(len(section2_status.conversations), 1)

        # The newer conversation (section2) should have a later created_at time
        self.assertTrue(
            section2_status.conversations[0].created_at
            > section1_status.conversations[0].created_at
        )

    def test_get_homework_submissions_student_sorting(self):
        """Test that students are sorted with no_interaction first, then by last activity."""
        # Student1: No interaction
        # Student2: Has interaction
        _conv2 = Conversation.objects.create(
            user=self.student2_user, section=self.section1
        )

        result = HomeworkService.get_homework_submissions(self.homework.id)

        # Find students by participation status
        no_interaction_students = [
            s
            for s in result.students
            if s.participation_status == ParticipationStatus.NO_INTERACTION
        ]
        partial_students = [
            s
            for s in result.students
            if s.participation_status == ParticipationStatus.PARTIAL
        ]

        # Should have one student with no interaction and one with partial
        self.assertEqual(len(no_interaction_students), 1)
        self.assertEqual(len(partial_students), 1)

        # Student1 should have no interaction
        self.assertEqual(no_interaction_students[0].student_username, "student1")

        # Student2 should have partial interaction
        self.assertEqual(partial_students[0].student_username, "student2")

        # No interaction students should come before partial students in the sorted list
        no_interaction_index = next(
            i
            for i, s in enumerate(result.students)
            if s.participation_status == ParticipationStatus.NO_INTERACTION
        )
        partial_index = next(
            i
            for i, s in enumerate(result.students)
            if s.participation_status == ParticipationStatus.PARTIAL
        )
        self.assertLess(no_interaction_index, partial_index)

    def test_non_enrolled_students_not_shown(self):
        """Test that students not enrolled in any course with the homework are not shown."""
        # Create a student who is NOT enrolled in the course
        non_enrolled_user = User.objects.create_user(
            username="non_enrolled",
            email="non_enrolled@example.com",
            password="password123",
            first_name="Non",
            last_name="Enrolled",
        )
        _non_enrolled_student = Student.objects.create(user=non_enrolled_user)

        # Create a conversation for the non-enrolled student
        # This should still NOT make them appear in the results
        Conversation.objects.create(user=non_enrolled_user, section=self.section1)

        # Get submissions data
        result = HomeworkService.get_homework_submissions(self.homework.id)

        self.assertIsNotNone(result)
        # Should only show the 2 enrolled students, not the non-enrolled one
        self.assertEqual(result.total_students, 2)
        self.assertEqual(len(result.students), 2)

        # Verify the non-enrolled student is NOT in the results
        student_usernames = [s.student_username for s in result.students]
        self.assertNotIn("non_enrolled", student_usernames)

        # Verify only enrolled students are shown
        self.assertIn("student1", student_usernames)
        self.assertIn("student2", student_usernames)


class HomeworkSubmissionsNonInteractiveServiceTest(TestCase):
    """Tests for get_homework_submissions with non-interactive sections."""

    def setUp(self):
        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="pass"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="student", email="student@example.com", password="pass"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.course = Course.objects.create(name="Course", code="C101", description="")
        CourseEnrollment.objects.create(course=self.course, student=self.student)

        self.homework = Homework.objects.create(
            title="HW",
            description="",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.ni_section = Section.objects.create(
            homework=self.homework,
            title="Q1",
            content="What is 2+2?",
            order=1,
            section_type=Section.SECTION_TYPE_NON_INTERACTIVE,
        )

    def test_non_interactive_section_with_answers(self):
        from conversations.models import SectionAnswer

        SectionAnswer.objects.create(user=self.student_user, section=self.ni_section, answer="First answer")
        SectionAnswer.objects.create(user=self.student_user, section=self.ni_section, answer="Second answer")

        result = HomeworkService.get_homework_submissions(self.homework.id)

        self.assertIsNotNone(result)
        student_summary = result.students[0]
        section_status = student_summary.section_statuses[0]

        self.assertEqual(section_status.section_type, "non_interactive")
        self.assertEqual(section_status.answer_count, 2)
        self.assertIsNotNone(section_status.latest_answer)
        self.assertFalse(section_status.is_missing)
        self.assertEqual(len(section_status.conversations), 0)

    def test_non_interactive_section_no_answers(self):
        result = HomeworkService.get_homework_submissions(self.homework.id)

        self.assertIsNotNone(result)
        student_summary = result.students[0]
        section_status = student_summary.section_statuses[0]

        self.assertEqual(section_status.section_type, "non_interactive")
        self.assertEqual(section_status.answer_count, 0)
        self.assertIsNone(section_status.latest_answer)
        self.assertTrue(section_status.is_missing)

    def test_non_interactive_section_counts_toward_participation(self):
        from conversations.models import SectionAnswer

        SectionAnswer.objects.create(user=self.student_user, section=self.ni_section, answer="My answer")

        result = HomeworkService.get_homework_submissions(self.homework.id)

        self.assertIsNotNone(result)
        student_summary = result.students[0]
        self.assertTrue(student_summary.has_interactions)
        self.assertEqual(student_summary.participation_status, ParticipationStatus.ACTIVE)


class HomeworkSubmissionsNonInteractiveViewTest(TestCase):
    """Tests for the submissions view rendering non-interactive sections."""

    def setUp(self):
        self.client = Client()

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="pass"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="student", email="student@example.com", password="pass"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.course = Course.objects.create(name="Course", code="C101", description="")
        CourseEnrollment.objects.create(course=self.course, student=self.student)

        from courses.models import CourseTeacher
        CourseTeacher.objects.create(course=self.course, teacher=self.teacher, role="owner")

        self.homework = Homework.objects.create(
            title="HW",
            description="",
            created_by=self.teacher,
            course=self.course,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.ni_section = Section.objects.create(
            homework=self.homework,
            title="Q1",
            content="What is 2+2?",
            order=1,
            section_type=Section.SECTION_TYPE_NON_INTERACTIVE,
        )

    def test_submissions_view_shows_non_interactive_answer_count(self):
        from conversations.models import SectionAnswer

        SectionAnswer.objects.create(user=self.student_user, section=self.ni_section, answer="Four")
        SectionAnswer.objects.create(user=self.student_user, section=self.ni_section, answer="4")

        self.client.login(username="teacher", password="pass")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 Answers")

    def test_submissions_view_shows_view_all_answers_link(self):
        from conversations.models import SectionAnswer

        SectionAnswer.objects.create(user=self.student_user, section=self.ni_section, answer="Four")

        self.client.login(username="teacher", password="pass")
        url = reverse("homeworks:submissions", kwargs={"homework_id": self.homework.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        expected_url = reverse(
            "conversations:section_answers",
            kwargs={"section_id": self.ni_section.id, "student_id": self.student.id},
        )
        self.assertContains(response, expected_url)

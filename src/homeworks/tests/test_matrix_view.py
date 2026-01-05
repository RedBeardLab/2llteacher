"""
Tests for the homework matrix view.

This module tests the matrix dashboard functionality including:
- Data structure generation
- Teacher-only access
- Matrix display with various data scenarios
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from accounts.models import Teacher, Student
from homeworks.models import Homework, Section
from homeworks.services import HomeworkService
from conversations.models import Conversation, Submission
from llm.models import LLMConfig
from courses.models import Course, CourseEnrollment

User = get_user_model()


class HomeworkMatrixViewTest(TestCase):
    """Test cases for the homework matrix view."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create teacher user
        self.teacher_user = User.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            password="password123",
            first_name="Test",
            last_name="Teacher",
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create student users
        self.student1_user = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="password123",
            first_name="Alice",
            last_name="Smith",
        )
        self.student1 = Student.objects.create(user=self.student1_user)

        self.student2_user = User.objects.create_user(
            username="student2",
            email="student2@example.com",
            password="password123",
            first_name="Bob",
            last_name="Jones",
        )
        self.student2 = Student.objects.create(user=self.student2_user)

        # Create LLM config
        self.llm_config = LLMConfig.objects.create(
            name="Test Config",
            model_name="gpt-4",
            api_key="test-api-key-12345",
            base_prompt="You are a helpful AI tutor.",
        )

        # Create course and enroll students
        self.course = Course.objects.create(
            name="Test Course",
            description="Test course description",
            code="TEST101",
        )

        # Enroll students in the course
        CourseEnrollment.objects.create(course=self.course, student=self.student1)
        CourseEnrollment.objects.create(course=self.course, student=self.student2)

        # Create homeworks with course assigned
        self.homework1 = Homework.objects.create(
            title="Homework 1",
            description="First homework",
            due_date=timezone.now() + timedelta(days=7),
            created_by=self.teacher,
            course=self.course,
            llm_config=self.llm_config,
        )

        self.section1_1 = Section.objects.create(
            homework=self.homework1, title="Section 1.1", content="Content 1.1", order=1
        )

        self.section1_2 = Section.objects.create(
            homework=self.homework1, title="Section 1.2", content="Content 1.2", order=2
        )

        self.homework2 = Homework.objects.create(
            title="Homework 2",
            description="Second homework",
            due_date=timezone.now() + timedelta(days=14),
            created_by=self.teacher,
            course=self.course,
            llm_config=self.llm_config,
        )

        self.section2_1 = Section.objects.create(
            homework=self.homework2, title="Section 2.1", content="Content 2.1", order=1
        )

        # Matrix URL
        self.matrix_url = reverse("homeworks:matrix")

    def test_matrix_view_requires_login(self):
        """Test that matrix view requires authentication."""
        response = self.client.get(self.matrix_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_matrix_view_requires_teacher(self):
        """Test that matrix view is teacher-only."""
        self.client.login(username="student1", password="password123")
        response = self.client.get(self.matrix_url)
        self.assertEqual(response.status_code, 403)

    def test_matrix_view_loads_for_teacher(self):
        """Test that matrix view loads successfully for teacher."""
        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.matrix_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homeworks/matrix.html")

    def test_matrix_data_structure(self):
        """Test that matrix data structure is correct."""
        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        self.assertIsNotNone(matrix_data)
        self.assertEqual(matrix_data.total_students, 2)
        self.assertEqual(matrix_data.total_homeworks, 2)
        self.assertEqual(len(matrix_data.student_rows), 2)
        self.assertEqual(len(matrix_data.homeworks), 2)

    def test_matrix_with_no_submissions(self):
        """Test matrix display when no student has submitted anything."""
        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        # Check that all cells show not started
        for student_row in matrix_data.student_rows:
            for cell in student_row.homework_cells:
                self.assertEqual(cell.submitted_sections, 0)
                self.assertEqual(cell.completion_percentage, 0)
                self.assertEqual(cell.total_conversations, 0)

    def test_matrix_with_partial_submissions(self):
        """Test matrix display with partial submissions."""
        # Student 1 starts conversation for homework 1, section 1
        conv1 = Conversation.objects.create(
            user=self.student1_user, section=self.section1_1
        )

        # Student 1 submits homework 1, section 1
        Submission.objects.create(conversation=conv1, submitted_at=timezone.now())

        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        # Find student1's row
        student1_row = next(
            (
                row
                for row in matrix_data.student_rows
                if row.student_id == self.student1.id
            ),
            None,
        )

        self.assertIsNotNone(student1_row)

        # Check homework 1 cell for student 1
        hw1_cell = next(
            (
                cell
                for cell in student1_row.homework_cells
                if cell.homework_id == self.homework1.id
            ),
            None,
        )

        self.assertIsNotNone(hw1_cell)
        self.assertEqual(hw1_cell.submitted_sections, 1)
        self.assertEqual(hw1_cell.total_sections, 2)
        self.assertEqual(hw1_cell.completion_percentage, 50)
        self.assertEqual(hw1_cell.total_conversations, 1)

    def test_matrix_with_full_submissions(self):
        """Test matrix display when student completes all sections."""
        # Student 1 submits all sections of homework 1
        for section in [self.section1_1, self.section1_2]:
            conv = Conversation.objects.create(user=self.student1_user, section=section)
            Submission.objects.create(conversation=conv, submitted_at=timezone.now())

        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        # Find student1's row
        student1_row = next(
            (
                row
                for row in matrix_data.student_rows
                if row.student_id == self.student1.id
            ),
            None,
        )

        # Check homework 1 cell
        hw1_cell = next(
            (
                cell
                for cell in student1_row.homework_cells
                if cell.homework_id == self.homework1.id
            ),
            None,
        )

        self.assertEqual(hw1_cell.submitted_sections, 2)
        self.assertEqual(hw1_cell.total_sections, 2)
        self.assertEqual(hw1_cell.completion_percentage, 100)

    def test_matrix_multiple_students(self):
        """Test matrix with multiple students at different progress levels."""
        # Student 1: Complete homework 1
        for section in [self.section1_1, self.section1_2]:
            conv = Conversation.objects.create(user=self.student1_user, section=section)
            Submission.objects.create(conversation=conv, submitted_at=timezone.now())

        # Student 2: Partial homework 1, complete homework 2
        conv = Conversation.objects.create(
            user=self.student2_user, section=self.section1_1
        )
        Submission.objects.create(conversation=conv, submitted_at=timezone.now())

        conv2 = Conversation.objects.create(
            user=self.student2_user, section=self.section2_1
        )
        Submission.objects.create(conversation=conv2, submitted_at=timezone.now())

        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        # Verify total submissions
        self.assertEqual(matrix_data.total_submissions, 4)

        # Verify student 1
        student1_row = next(
            (
                row
                for row in matrix_data.student_rows
                if row.student_id == self.student1.id
            ),
            None,
        )
        self.assertEqual(student1_row.total_submissions, 2)

        # Verify student 2
        student2_row = next(
            (
                row
                for row in matrix_data.student_rows
                if row.student_id == self.student2.id
            ),
            None,
        )
        self.assertEqual(student2_row.total_submissions, 2)

    def test_matrix_view_renders_correctly(self):
        """Test that matrix view renders with correct data."""
        # Create some submissions
        conv = Conversation.objects.create(
            user=self.student1_user, section=self.section1_1
        )
        Submission.objects.create(conversation=conv, submitted_at=timezone.now())

        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.matrix_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Homework Matrix Dashboard")
        self.assertContains(response, "Alice Smith")
        self.assertContains(response, "Bob Jones")
        self.assertContains(response, "Homework 1")
        self.assertContains(response, "Homework 2")

    def test_matrix_with_no_students(self):
        """Test matrix display when no students exist."""
        # Delete all students
        Student.objects.all().delete()

        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        self.assertEqual(matrix_data.total_students, 0)
        self.assertEqual(len(matrix_data.student_rows), 0)

    def test_matrix_with_no_homeworks(self):
        """Test matrix display when teacher has no homeworks."""
        # Delete all homeworks
        Homework.objects.all().delete()

        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        self.assertEqual(matrix_data.total_homeworks, 0)
        self.assertEqual(len(matrix_data.homeworks), 0)

    def test_matrix_link_in_homework_list(self):
        """Test that matrix link appears in homework list for teachers."""
        self.client.login(username="teacher", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matrix Dashboard")
        self.assertContains(response, reverse("homeworks:matrix"))

    def test_matrix_link_not_in_homework_list_for_students(self):
        """Test that matrix link does not appear for students."""
        self.client.login(username="student1", password="password123")
        response = self.client.get(reverse("homeworks:list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Matrix Dashboard")

    def test_matrix_with_overdue_homework(self):
        """Test matrix display with overdue homework."""
        # Create overdue homework
        overdue_hw = Homework.objects.create(
            title="Overdue Homework",
            description="This is overdue",
            due_date=timezone.now() - timedelta(days=1),
            created_by=self.teacher,
            course=self.course,
            llm_config=self.llm_config,
        )

        Section.objects.create(
            homework=overdue_hw, title="Section", content="Content", order=1
        )

        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        # Verify overdue homework is included
        self.assertEqual(matrix_data.total_homeworks, 3)

    def test_matrix_overall_completion_percentage(self):
        """Test calculation of overall completion percentage."""
        # Student 1 completes 1 out of 3 total sections
        conv = Conversation.objects.create(
            user=self.student1_user, section=self.section1_1
        )
        Submission.objects.create(conversation=conv, submitted_at=timezone.now())

        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        student1_row = next(
            (
                row
                for row in matrix_data.student_rows
                if row.student_id == self.student1.id
            ),
            None,
        )

        # Should be 33% (1 out of 3 sections)
        expected_percentage = round((1 / 3) * 100)
        self.assertEqual(
            student1_row.overall_completion_percentage, expected_percentage
        )

    def test_matrix_with_deleted_conversations(self):
        """Test that soft-deleted conversations are not counted."""
        # Create and soft-delete a conversation
        conv = Conversation.objects.create(
            user=self.student1_user, section=self.section1_1
        )
        conv.soft_delete()

        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        student1_row = next(
            (
                row
                for row in matrix_data.student_rows
                if row.student_id == self.student1.id
            ),
            None,
        )

        hw1_cell = next(
            (
                cell
                for cell in student1_row.homework_cells
                if cell.homework_id == self.homework1.id
            ),
            None,
        )

        # Soft-deleted conversation should not be counted
        self.assertEqual(hw1_cell.total_conversations, 0)

    def test_non_enrolled_students_not_shown_in_matrix(self):
        """Test that students not enrolled in any course with teacher's homeworks are not shown."""
        # Create a student who is NOT enrolled in the course
        non_enrolled_user = User.objects.create_user(
            username="non_enrolled",
            email="non_enrolled@example.com",
            password="password123",
            first_name="Non",
            last_name="Enrolled",
        )
        non_enrolled_student = Student.objects.create(user=non_enrolled_user)

        # Create conversations for the non-enrolled student
        # This should still NOT make them appear in the matrix
        conv1 = Conversation.objects.create(
            user=non_enrolled_user, section=self.section1_1
        )
        conv2 = Conversation.objects.create(
            user=non_enrolled_user, section=self.section2_1
        )
        Submission.objects.create(conversation=conv1)
        Submission.objects.create(conversation=conv2)

        # Get matrix data
        matrix_data = HomeworkService.get_all_homework_matrix(self.teacher.id)

        self.assertIsNotNone(matrix_data)
        # Should only show the 2 enrolled students, not the non-enrolled one
        self.assertEqual(matrix_data.total_students, 2)
        self.assertEqual(len(matrix_data.student_rows), 2)

        # Verify the non-enrolled student is NOT in the results
        student_ids = [row.student_id for row in matrix_data.student_rows]
        self.assertNotIn(non_enrolled_student.id, student_ids)

        # Verify only enrolled students are shown
        self.assertIn(self.student1.id, student_ids)
        self.assertIn(self.student2.id, student_ids)

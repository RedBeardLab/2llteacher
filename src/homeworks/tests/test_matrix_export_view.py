"""
Tests for the homework matrix CSV export view.

This module tests the CSV export functionality including:
- CSV format and structure
- Teacher-only access
- Data accuracy in exported CSV
- Proper formatting (LastName, FirstName)
"""

import csv
from io import StringIO
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from accounts.models import Teacher, Student
from homeworks.models import Homework, Section
from conversations.models import Conversation, Submission
from llm.models import LLMConfig
from courses.models import Course, CourseEnrollment, CourseHomework

User = get_user_model()


class HomeworkMatrixExportViewTest(TestCase):
    """Test cases for the homework matrix CSV export view."""

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

        # Create student users with different name patterns
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

        # Create student with no last name
        self.student3_user = User.objects.create_user(
            username="student3",
            email="student3@example.com",
            password="password123",
            first_name="Charlie",
            last_name="",
        )
        self.student3 = Student.objects.create(user=self.student3_user)

        # Create LLM config
        self.llm_config = LLMConfig.objects.create(
            name="Test Config",
            model_name="gpt-4",
            api_key="test-api-key-12345",
            base_prompt="You are a helpful AI tutor.",
        )

        # Create homeworks
        self.homework1 = Homework.objects.create(
            title="Homework 1",
            description="First homework",
            due_date=timezone.now() + timedelta(days=7),
            created_by=self.teacher,
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
            llm_config=self.llm_config,
        )

        self.section2_1 = Section.objects.create(
            homework=self.homework2, title="Section 2.1", content="Content 2.1", order=1
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
        CourseEnrollment.objects.create(course=self.course, student=self.student3)

        # Assign homeworks to course
        CourseHomework.objects.create(course=self.course, homework=self.homework1)
        CourseHomework.objects.create(course=self.course, homework=self.homework2)

        # Export URL
        self.export_url = reverse("homeworks:matrix_export")

    def test_export_view_requires_login(self):
        """Test that export view requires authentication."""
        response = self.client.get(self.export_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_export_view_requires_teacher(self):
        """Test that export view is teacher-only."""
        self.client.login(username="student1", password="password123")
        response = self.client.get(self.export_url)
        self.assertEqual(response.status_code, 403)

    def test_export_view_returns_csv(self):
        """Test that export view returns CSV file."""
        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("homework_grades.csv", response["Content-Disposition"])

    def test_csv_header_format(self):
        """Test that CSV has correct header format."""
        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        # Parse CSV
        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        header = next(csv_reader)

        # Check header structure
        self.assertEqual(header[0], "Student Name")
        self.assertEqual(header[1], "Student ID")
        self.assertEqual(header[2], "Student Email")
        self.assertEqual(header[3], "Homework 1")
        self.assertEqual(header[4], "Homework 2")

    def test_csv_student_name_format(self):
        """Test that student names are in 'LastName, FirstName' format."""
        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        next(csv_reader)  # Skip header

        # Collect student names
        student_names = []
        for row in csv_reader:
            student_names.append(row[0])

        # Check that names are in correct format
        self.assertIn("Smith, Alice", student_names)
        self.assertIn("Jones, Bob", student_names)
        # Student with no last name should just show first name
        self.assertIn("Charlie", student_names)

    def test_csv_student_id_is_empty(self):
        """Test that Student ID column is empty string."""
        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        next(csv_reader)  # Skip header

        # Check all student ID fields are empty
        for row in csv_reader:
            self.assertEqual(row[1], "")

    def test_csv_completion_format_no_percentage_symbols(self):
        """Test that completion data has no percentage symbols (just numbers)."""
        # Create some submissions
        conv = Conversation.objects.create(user=self.student1_user, section=self.section1_1)
        Submission.objects.create(conversation=conv, submitted_at=timezone.now())

        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        next(csv_reader)  # Skip header

        # Check that no percentage symbols or other formatting exists in data
        for row in csv_reader:
            # Homework completions (should be just numbers 0-100)
            for homework_col in row[3:]:
                self.assertNotIn("%", homework_col)
                self.assertNotIn("(", homework_col)
                self.assertNotIn(")", homework_col)
                self.assertNotIn("/", homework_col)
                # Should be a valid number
                try:
                    float(homework_col)
                except ValueError:
                    self.fail(f"Homework column '{homework_col}' is not a valid number")

    def test_csv_homework_completion_format(self):
        """Test that homework completion is in percentage format (0-100)."""
        # Student 1 completes 1 of 2 sections in homework 1
        conv = Conversation.objects.create(user=self.student1_user, section=self.section1_1)
        Submission.objects.create(conversation=conv, submitted_at=timezone.now())

        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        next(csv_reader)  # Skip header

        # Find student1's row
        for row in csv_reader:
            if "Smith, Alice" in row[0]:
                # Check homework 1 completion (column 3) - 1/2 = 50%
                self.assertEqual(row[3], "50")
                # Check homework 2 completion (column 4) - 0/1 = 0%
                self.assertEqual(row[4], "0")
                break

    def test_csv_with_no_submissions(self):
        """Test CSV export when no submissions exist."""
        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        next(csv_reader)  # Skip header

        # Check that all students have 0% completion
        for row in csv_reader:
            self.assertEqual(row[3], "0")  # Homework 1 - 0%
            self.assertEqual(row[4], "0")  # Homework 2 - 0%

    def test_csv_with_full_completion(self):
        """Test CSV export with full homework completion."""
        # Student 1 completes all sections of homework 1
        for section in [self.section1_1, self.section1_2]:
            conv = Conversation.objects.create(user=self.student1_user, section=section)
            Submission.objects.create(conversation=conv, submitted_at=timezone.now())

        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        next(csv_reader)  # Skip header

        # Find student1's row
        for row in csv_reader:
            if "Smith, Alice" in row[0]:
                # Homework 1 should be complete (2/2 = 100%)
                self.assertEqual(row[3], "100")
                # Homework 2 should be 0%
                self.assertEqual(row[4], "0")
                break

    def test_csv_row_count(self):
        """Test that CSV has correct number of rows (header + students)."""
        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        rows = list(csv_reader)

        # Should have 1 header + 3 students
        self.assertEqual(len(rows), 4)

    def test_csv_with_multiple_homeworks(self):
        """Test CSV with multiple homeworks displays all columns."""
        # Create a third homework
        homework3 = Homework.objects.create(
            title="Homework 3",
            description="Third homework",
            due_date=timezone.now() + timedelta(days=21),
            created_by=self.teacher,
            llm_config=self.llm_config,
        )
        Section.objects.create(
            homework=homework3, title="Section 3.1", content="Content 3.1", order=1
        )

        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        header = next(csv_reader)

        # Should have 3 fixed columns + 3 homework columns
        self.assertEqual(len(header), 6)
        self.assertEqual(header[5], "Homework 3")

    def test_csv_email_field(self):
        """Test that email addresses are correctly included."""
        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        next(csv_reader)  # Skip header

        # Collect emails
        emails = []
        for row in csv_reader:
            emails.append(row[2])

        self.assertIn("student1@example.com", emails)
        self.assertIn("student2@example.com", emails)
        self.assertIn("student3@example.com", emails)

    def test_non_enrolled_students_not_in_csv_export(self):
        """Test that students not enrolled in any course are not included in CSV export."""
        # Create a student who is NOT enrolled in the course
        non_enrolled_user = User.objects.create_user(
            username="non_enrolled",
            email="non_enrolled@example.com",
            password="password123",
            first_name="Non",
            last_name="Enrolled",
        )
        non_enrolled_student = Student.objects.create(user=non_enrolled_user)

        # Create conversations and submissions for the non-enrolled student
        # This should still NOT make them appear in the CSV
        conv1 = Conversation.objects.create(user=non_enrolled_user, section=self.section1_1)
        conv2 = Conversation.objects.create(user=non_enrolled_user, section=self.section2_1)
        Submission.objects.create(conversation=conv1)
        Submission.objects.create(conversation=conv2)

        # Get CSV export
        self.client.login(username="teacher", password="password123")
        response = self.client.get(self.export_url)

        content = response.content.decode("utf-8")
        csv_reader = csv.reader(StringIO(content))
        rows = list(csv_reader)

        # Should have header + 3 enrolled students (not the non-enrolled one)
        self.assertEqual(len(rows), 4)

        # Collect student names and emails
        student_names = [row[0] for row in rows[1:]]  # Skip header
        student_emails = [row[2] for row in rows[1:]]  # Skip header

        # Verify the non-enrolled student is NOT in the CSV
        self.assertNotIn("Enrolled, Non", student_names)
        self.assertNotIn("non_enrolled@example.com", student_emails)

        # Verify only enrolled students are in the CSV
        self.assertIn("Smith, Alice", student_names)
        self.assertIn("Jones, Bob", student_names)
        self.assertIn("student1@example.com", student_emails)
        self.assertIn("student2@example.com", student_emails)

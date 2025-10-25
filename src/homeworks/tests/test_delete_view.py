"""
Tests for homework deletion functionality.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from uuid import uuid4

from accounts.models import Teacher, Student
from homeworks.models import Homework, Section
from llm.models import LLMConfig

User = get_user_model()


class HomeworkDeleteViewTest(TestCase):
    """Test cases for homework deletion via POST to detail view."""

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

        # Create student user and profile
        self.student_user = User.objects.create_user(
            username="student1", email="student1@example.com", password="password123"
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create LLM config
        self.llm_config = LLMConfig.objects.create(
            name="Test Config",
            model_name="gpt-4",
            api_key="test-key",
            base_prompt="You are a helpful AI tutor.",
            max_completion_tokens=1000,
            temperature=0.7,
        )

        # Create homework
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test description",
            due_date="2024-12-31 23:59:59",
            created_by=self.teacher,
            llm_config=self.llm_config,
        )

        # Create sections
        self.section1 = Section.objects.create(
            homework=self.homework, title="Section 1", content="Content 1", order=1
        )
        self.section2 = Section.objects.create(
            homework=self.homework, title="Section 2", content="Content 2", order=2
        )

    def test_delete_homework_success(self):
        """Test successful homework deletion by owner."""
        # Login as the teacher who owns the homework
        self.client.login(username="teacher1", password="password123")

        # Get the homework detail URL
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework.id})

        # Verify homework exists before deletion
        self.assertTrue(Homework.objects.filter(id=self.homework.id).exists())

        # Send POST request with delete action
        response = self.client.post(url, {"action": "delete"})

        # Should redirect to homework list
        self.assertRedirects(response, reverse("homeworks:list"))

        # Verify homework is deleted
        self.assertFalse(Homework.objects.filter(id=self.homework.id).exists())

        # Verify sections are also deleted (cascade)
        self.assertFalse(Section.objects.filter(homework_id=self.homework.id).exists())

        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("deleted successfully", str(messages[0]))
        self.assertIn("Test Homework", str(messages[0]))

    def test_delete_homework_permission_denied_other_teacher(self):
        """Test that teachers cannot delete homeworks they don't own."""
        # Login as different teacher
        self.client.login(username="teacher2", password="password123")

        # Get the homework detail URL
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework.id})

        # Send POST request with delete action
        response = self.client.post(url, {"action": "delete"})

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # Verify homework still exists
        self.assertTrue(Homework.objects.filter(id=self.homework.id).exists())

    def test_delete_homework_permission_denied_student(self):
        """Test that students cannot delete homeworks."""
        # Login as student
        self.client.login(username="student1", password="password123")

        # Get the homework detail URL
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework.id})

        # Send POST request with delete action
        response = self.client.post(url, {"action": "delete"})

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

        # Verify homework still exists
        self.assertTrue(Homework.objects.filter(id=self.homework.id).exists())

    def test_delete_homework_not_found(self):
        """Test deletion of non-existent homework."""
        # Login as teacher
        self.client.login(username="teacher1", password="password123")

        # Use a random UUID that doesn't exist
        fake_id = uuid4()
        url = reverse("homeworks:detail", kwargs={"homework_id": fake_id})

        # Send POST request with delete action
        response = self.client.post(url, {"action": "delete"})

        # Should redirect to homework list
        self.assertRedirects(response, reverse("homeworks:list"))

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("not found", str(messages[0]))

    def test_delete_homework_unauthenticated(self):
        """Test that unauthenticated users cannot delete homeworks."""
        # Don't login
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework.id})

        # Send POST request with delete action
        response = self.client.post(url, {"action": "delete"})

        # Should redirect to login (302 status code)
        self.assertEqual(response.status_code, 302)
        # Check that it redirects to login page
        self.assertTrue(response["Location"].startswith("/accounts/login/"))

        # Verify homework still exists
        self.assertTrue(Homework.objects.filter(id=self.homework.id).exists())

    def test_post_without_delete_action(self):
        """Test POST request without delete action."""
        # Login as teacher
        self.client.login(username="teacher1", password="password123")

        # Get the homework detail URL
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework.id})

        # Send POST request without action or with different action
        response = self.client.post(url, {"action": "something_else"})

        # Should redirect back to detail view
        self.assertRedirects(
            response,
            reverse("homeworks:detail", kwargs={"homework_id": self.homework.id}),
        )

        # Verify homework still exists
        self.assertTrue(Homework.objects.filter(id=self.homework.id).exists())

    def test_post_without_action_parameter(self):
        """Test POST request without any action parameter."""
        # Login as teacher
        self.client.login(username="teacher1", password="password123")

        # Get the homework detail URL
        url = reverse("homeworks:detail", kwargs={"homework_id": self.homework.id})

        # Send POST request without action parameter
        response = self.client.post(url, {})

        # Should redirect back to detail view
        self.assertRedirects(
            response,
            reverse("homeworks:detail", kwargs={"homework_id": self.homework.id}),
        )

        # Verify homework still exists
        self.assertTrue(Homework.objects.filter(id=self.homework.id).exists())

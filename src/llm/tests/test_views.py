"""
Tests for the LLM views.

This module contains tests for the LLM views following
the testing-first architecture approach.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch
import json

from llm.models import LLMConfig
from llm.services import LLMResponseWithTools
from accounts.models import Teacher, Student

User = get_user_model()


class LLMViewsTestCase(TestCase):
    """Base test case for LLM views with common setup."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test users
        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="student", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(user=self.student_user)

        # Create test LLM config
        self.llm_config = LLMConfig.objects.create(
            name="Test Config",
            model_name="gpt-3.5-turbo",
            api_key="test-api-key-12345",
            base_prompt="You are a helpful AI tutor.",
            temperature=0.7,
            max_completion_tokens=1000,
            is_default=True,
            is_active=True,
        )


class TestLLMConfigListView(LLMViewsTestCase):
    """Test cases for LLMConfigListView."""

    def test_teacher_can_access_config_list(self):
        """Test that teachers can access the config list."""
        self.client.login(username="teacher", password="testpass123")

        response = self.client.get(reverse("llm:config-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Config")
        self.assertContains(response, "gpt-3.5-turbo")

    def test_student_cannot_access_config_list(self):
        """Test that students cannot access the config list."""
        self.client.login(username="student", password="testpass123")

        response = self.client.get(reverse("llm:config-list"))

        # Should redirect to login or show permission denied
        self.assertIn(response.status_code, [302, 403])

    def test_anonymous_user_redirected(self):
        """Test that anonymous users are redirected to login."""
        response = self.client.get(reverse("llm:config-list"))

        self.assertEqual(response.status_code, 302)


class TestLLMConfigCreateView(LLMViewsTestCase):
    """Test cases for LLMConfigCreateView."""

    def test_teacher_can_access_create_form(self):
        """Test that teachers can access the create form."""
        self.client.login(username="teacher", password="testpass123")

        response = self.client.get(reverse("llm:config-create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create LLM Configuration")

    def test_teacher_can_create_config(self):
        """Test that teachers can create a new config."""
        self.client.login(username="teacher", password="testpass123")

        form_data = {
            "name": "New Test Config",
            "model_name": "gpt-4",
            "api_key": "new-test-api-key",
            "base_prompt": "You are a new AI tutor.",
            "temperature": 0.8,
            "max_completion_tokens": 2000,
            "is_default": False,
            "is_active": True,
        }

        response = self.client.post(reverse("llm:config-create"), form_data)

        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)

        # Check config was created
        new_config = LLMConfig.objects.get(name="New Test Config")
        self.assertEqual(new_config.model_name, "gpt-4")
        self.assertEqual(new_config.temperature, 0.8)

    def test_student_cannot_create_config(self):
        """Test that students cannot create configs."""
        self.client.login(username="student", password="testpass123")

        response = self.client.get(reverse("llm:config-create"))

        self.assertIn(response.status_code, [302, 403])


class TestLLMConfigDetailView(LLMViewsTestCase):
    """Test cases for LLMConfigDetailView."""

    def test_teacher_can_view_config_detail(self):
        """Test that teachers can view config details."""
        self.client.login(username="teacher", password="testpass123")

        response = self.client.get(
            reverse("llm:config-detail", kwargs={"config_id": self.llm_config.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Config")
        self.assertContains(response, "gpt-3.5-turbo")

    def test_student_can_view_config_detail(self):
        """Test that students can view config details (read-only)."""
        self.client.login(username="student", password="testpass123")

        response = self.client.get(
            reverse("llm:config-detail", kwargs={"config_id": self.llm_config.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Config")
        # Should not contain edit/delete buttons for students
        self.assertNotContains(response, "Edit Configuration")


class TestLLMConfigUpdateView(LLMViewsTestCase):
    """Test cases for LLMConfigUpdateView."""

    def test_teacher_can_update_config(self):
        """Test that teachers can update configs."""
        self.client.login(username="teacher", password="testpass123")

        form_data = {
            "name": "Updated Test Config",
            "model_name": "gpt-4",
            "api_key": "updated-api-key",
            "base_prompt": "You are an updated AI tutor.",
            "temperature": 0.9,
            "max_completion_tokens": 1500,
            "is_default": True,
            "is_active": True,
        }

        response = self.client.post(
            reverse("llm:config-edit", kwargs={"config_id": self.llm_config.id}),
            form_data,
        )

        # Should redirect after successful update
        self.assertEqual(response.status_code, 302)

        # Check config was updated
        updated_config = LLMConfig.objects.get(id=self.llm_config.id)
        self.assertEqual(updated_config.name, "Updated Test Config")
        self.assertEqual(updated_config.model_name, "gpt-4")
        self.assertEqual(updated_config.temperature, 0.9)

    def test_student_cannot_update_config(self):
        """Test that students cannot update configs."""
        self.client.login(username="student", password="testpass123")

        response = self.client.get(
            reverse("llm:config-edit", kwargs={"config_id": self.llm_config.id})
        )

        self.assertIn(response.status_code, [302, 403])


class TestLLMConfigDeleteView(LLMViewsTestCase):
    """Test cases for LLMConfigDeleteView."""

    def test_teacher_can_delete_config(self):
        """Test that teachers can delete (deactivate) configs."""
        # Create a non-default config for deletion
        delete_config = LLMConfig.objects.create(
            name="Delete Me",
            model_name="gpt-3.5-turbo",
            api_key="delete-api-key",
            base_prompt="Delete me.",
            temperature=0.7,
            max_completion_tokens=1000,
            is_default=False,
            is_active=True,
        )

        self.client.login(username="teacher", password="testpass123")

        response = self.client.post(
            reverse("llm:config-delete", kwargs={"config_id": delete_config.id})
        )

        # Should redirect after successful deletion
        self.assertEqual(response.status_code, 302)

        # Check config was deactivated
        deleted_config = LLMConfig.objects.get(id=delete_config.id)
        self.assertFalse(deleted_config.is_active)

    def test_cannot_delete_default_config(self):
        """Test that default configs cannot be deleted."""
        self.client.login(username="teacher", password="testpass123")

        response = self.client.post(
            reverse("llm:config-delete", kwargs={"config_id": self.llm_config.id})
        )

        # Should redirect with error message
        self.assertEqual(response.status_code, 302)

        # Check config is still active
        config = LLMConfig.objects.get(id=self.llm_config.id)
        self.assertTrue(config.is_active)

    def test_student_cannot_delete_config(self):
        """Test that students cannot delete configs."""
        self.client.login(username="student", password="testpass123")

        response = self.client.post(
            reverse("llm:config-delete", kwargs={"config_id": self.llm_config.id})
        )

        self.assertIn(response.status_code, [302, 403])


class TestLLMConfigTestView(LLMViewsTestCase):
    """Test cases for LLMConfigTestView."""

    @patch("llm.services.LLMService.test_config")
    def test_teacher_can_test_config(self, mock_test_config):
        """Test that teachers can test configs."""
        # Mock successful test response
        mock_test_config.return_value = LLMResponseWithTools(
            response_text="Test response from AI", tokens_used=15, success=True
        )

        self.client.login(username="teacher", password="testpass123")

        response = self.client.post(
            reverse("llm:config-test", kwargs={"config_id": self.llm_config.id}),
            {"test_message": "Hello, this is a test."},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)

        # Parse JSON response
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["response_text"], "Test response from AI")
        self.assertEqual(data["tokens_used"], 15)

    @patch("llm.services.LLMService.test_config")
    def test_config_test_failure(self, mock_test_config):
        """Test handling of config test failures."""
        # Mock failed test response
        mock_test_config.return_value = LLMResponseWithTools(
            response_text="", tokens_used=0, success=False, error="Invalid API key"
        )

        self.client.login(username="teacher", password="testpass123")

        response = self.client.post(
            reverse("llm:config-test", kwargs={"config_id": self.llm_config.id}),
            {"test_message": "Hello, this is a test."},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)

        # Parse JSON response
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Invalid API key")


class TestLLMGenerateAPIView(LLMViewsTestCase):
    """Test cases for LLMGenerateAPIView."""

    @patch("llm.services.LLMService.get_response")
    def test_api_generate_response(self, mock_get_response):
        """Test the API endpoint for generating responses."""
        # Login as student for API access
        self.client.login(username="student", password="testpass123")

        # Mock successful response with tools format
        from llm.services import LLMResponseWithTools

        mock_get_response.return_value = LLMResponseWithTools(
            response_text="This is an AI response.",
            function_calls=None,
            tokens_used=20,
            success=True,
        )

        # Create necessary database objects for the test
        from homeworks.models import Homework, Section
        from conversations.models import Conversation
        from courses.models import Course

        # Create a course first
        course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )

        # Create homework with course (direct FK relationship)
        homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=course,
            due_date="2024-12-31 23:59:59",
            llm_config=self.llm_config,
        )

        section = Section.objects.create(
            homework=homework,
            title="Test Section",
            content="Test section content",
            order=1,
        )

        # Create conversation
        conversation = Conversation.objects.create(
            user=self.student_user, section=section
        )

        # Create API data with real conversation ID
        api_data = {
            "conversation_id": str(conversation.id),
            "content": "I need help with this problem.",
            "message_type": "student",
        }

        response = self.client.post(
            reverse("llm:api-generate"),
            json.dumps(api_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        # Parse JSON response
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["response_text"], "This is an AI response.")

    def test_api_generate_invalid_data(self):
        """Test API endpoint with invalid data."""
        # Login as student for API access
        self.client.login(username="student", password="testpass123")

        # Missing required fields
        api_data = {
            "content": "I need help with this problem."
            # Missing conversation_id and message_type
        }

        response = self.client.post(
            reverse("llm:api-generate"),
            json.dumps(api_data),
            content_type="application/json",
        )

        self.assertEqual(
            response.status_code, 200
        )  # API returns 200 with error in JSON

        # Parse JSON response to check for error
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertIn("error", data)


class TestLLMConfigsAPIView(LLMViewsTestCase):
    """Test cases for LLMConfigsAPIView."""

    def test_api_get_configs(self):
        """Test the API endpoint for getting all configs."""
        # Login as student for API access
        self.client.login(username="student", password="testpass123")

        response = self.client.get(reverse("llm:api-configs"))

        self.assertEqual(response.status_code, 200)

        # Parse JSON response
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["configs"]), 1)

        config = data["configs"][0]
        self.assertEqual(config["name"], "Test Config")
        self.assertEqual(config["model_name"], "gpt-3.5-turbo")
        self.assertTrue(config["is_default"])

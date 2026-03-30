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

from llm.models import LLMConfig, GlobalLLMDefault
from llm.services import LLMResponseWithTools, LLMService
from accounts.models import Teacher, Student
from courses.models import Course, CourseTeacher

User = get_user_model()


class LLMViewsTestCase(TestCase):
    """Base test case for LLM views with common setup."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@test.com", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.student_user = User.objects.create_user(
            username="student", email="student@test.com", password="testpass123"
        )
        self.student = Student.objects.create(user=self.student_user)

        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )
        CourseTeacher.objects.create(
            course=self.course, teacher=self.teacher, role="owner"
        )

        self.llm_config = LLMConfig.objects.create(
            course=self.course,
            name="Test Config",
            model_name="gpt-3.5-turbo",
            api_key="test-api-key-12345",
            base_prompt="You are a helpful AI tutor.",
            temperature=0.7,
            max_completion_tokens=1000,
            is_default=True,
            is_active=True,
        )

        self.global_default = GlobalLLMDefault.objects.create(
            name="Global Default",
            model_name="gpt-4",
            api_key="global-api-key",
            base_prompt="You are a global AI tutor.",
            temperature=0.7,
            max_completion_tokens=1000,
            is_active=True,
        )


class TestLLMConfigListView(LLMViewsTestCase):
    """Test cases for LLMConfigListView."""

    def test_teacher_can_access_config_list(self):
        """Test that teachers can access the config list."""
        self.client.login(username="teacher", password="testpass123")

        response = self.client.get(
            reverse("llm:config-list", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Config")
        self.assertContains(response, "gpt-3.5-turbo")

    def test_student_cannot_access_config_list(self):
        """Test that students cannot access the config list."""
        self.client.login(username="student", password="testpass123")

        response = self.client.get(
            reverse("llm:config-list", kwargs={"course_id": self.course.id})
        )

        self.assertIn(response.status_code, [302, 403])

    def test_anonymous_user_redirected(self):
        """Test that anonymous users are redirected to login."""
        response = self.client.get(
            reverse("llm:config-list", kwargs={"course_id": self.course.id})
        )

        self.assertEqual(response.status_code, 302)


class TestLLMConfigCreateView(LLMViewsTestCase):
    """Test cases for LLMConfigCreateView."""

    def test_teacher_can_access_create_form(self):
        """Test that teachers can access the create form."""
        self.client.login(username="teacher", password="testpass123")

        response = self.client.get(
            reverse("llm:config-create", kwargs={"course_id": self.course.id})
        )

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

        response = self.client.post(
            reverse("llm:config-create", kwargs={"course_id": self.course.id}),
            form_data,
        )

        self.assertEqual(response.status_code, 302)

        new_config = LLMConfig.objects.get(name="New Test Config", course=self.course)
        self.assertEqual(new_config.model_name, "gpt-4")
        self.assertEqual(new_config.temperature, 0.8)

    def test_student_cannot_create_config(self):
        """Test that students cannot create configs."""
        self.client.login(username="student", password="testpass123")

        response = self.client.get(
            reverse("llm:config-create", kwargs={"course_id": self.course.id})
        )

        self.assertIn(response.status_code, [302, 403])


class TestLLMConfigDetailView(LLMViewsTestCase):
    """Test cases for LLMConfigDetailView."""

    def test_teacher_can_view_config_detail(self):
        """Test that teachers can view config details."""
        self.client.login(username="teacher", password="testpass123")

        response = self.client.get(
            reverse(
                "llm:config-detail",
                kwargs={"course_id": self.course.id, "config_id": self.llm_config.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Config")
        self.assertContains(response, "gpt-3.5-turbo")

    def test_student_cannot_view_config_detail(self):
        """Test that students cannot view config details."""
        self.client.login(username="student", password="testpass123")

        response = self.client.get(
            reverse(
                "llm:config-detail",
                kwargs={"course_id": self.course.id, "config_id": self.llm_config.id},
            )
        )

        self.assertIn(response.status_code, [302, 403])


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
            reverse(
                "llm:config-edit",
                kwargs={"course_id": self.course.id, "config_id": self.llm_config.id},
            ),
            form_data,
        )

        self.assertEqual(response.status_code, 302)

        updated_config = LLMConfig.objects.get(id=self.llm_config.id)
        self.assertEqual(updated_config.name, "Updated Test Config")
        self.assertEqual(updated_config.model_name, "gpt-4")
        self.assertEqual(updated_config.temperature, 0.9)

    def test_student_cannot_update_config(self):
        """Test that students cannot update configs."""
        self.client.login(username="student", password="testpass123")

        response = self.client.get(
            reverse(
                "llm:config-edit",
                kwargs={"course_id": self.course.id, "config_id": self.llm_config.id},
            )
        )

        self.assertIn(response.status_code, [302, 403])


class TestLLMConfigDeleteView(LLMViewsTestCase):
    """Test cases for LLMConfigDeleteView."""

    def test_teacher_can_delete_config(self):
        """Test that teachers can delete (deactivate) configs."""
        delete_config = LLMConfig.objects.create(
            course=self.course,
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
            reverse(
                "llm:config-delete",
                kwargs={"course_id": self.course.id, "config_id": delete_config.id},
            )
        )

        self.assertEqual(response.status_code, 302)

        deleted_config = LLMConfig.objects.get(id=delete_config.id)
        self.assertFalse(deleted_config.is_active)

    def test_cannot_delete_default_config(self):
        """Test that default configs cannot be deleted."""
        self.client.login(username="teacher", password="testpass123")

        response = self.client.post(
            reverse(
                "llm:config-delete",
                kwargs={"course_id": self.course.id, "config_id": self.llm_config.id},
            )
        )

        self.assertEqual(response.status_code, 302)

        config = LLMConfig.objects.get(id=self.llm_config.id)
        self.assertTrue(config.is_active)

    def test_student_cannot_delete_config(self):
        """Test that students cannot delete configs."""
        self.client.login(username="student", password="testpass123")

        response = self.client.post(
            reverse(
                "llm:config-delete",
                kwargs={"course_id": self.course.id, "config_id": self.llm_config.id},
            )
        )

        self.assertIn(response.status_code, [302, 403])


class TestLLMConfigCloneView(LLMViewsTestCase):
    """Test cases for LLMConfigCloneView."""

    def setUp(self):
        super().setUp()
        self.target_course = Course.objects.create(
            name="Target Course",
            code="TARGET101",
            description="Target course for cloning",
        )
        CourseTeacher.objects.create(
            course=self.target_course, teacher=self.teacher, role="owner"
        )

    def test_teacher_can_access_clone_form(self):
        """Test that teachers can access the clone form."""
        self.client.login(username="teacher", password="testpass123")

        response = self.client.get(
            reverse(
                "llm:config-clone",
                kwargs={"course_id": self.course.id, "config_id": self.llm_config.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clone")
        self.assertContains(response, "Target Course")

    def test_teacher_can_clone_config(self):
        """Test that teachers can clone a config to another course."""
        self.client.login(username="teacher", password="testpass123")

        form_data = {
            "target_course_id": str(self.target_course.id),
        }

        response = self.client.post(
            reverse(
                "llm:config-clone",
                kwargs={"course_id": self.course.id, "config_id": self.llm_config.id},
            ),
            form_data,
        )

        self.assertEqual(response.status_code, 302)

        cloned_config = LLMConfig.objects.filter(
            course=self.target_course, name=self.llm_config.name
        ).first()
        self.assertIsNotNone(cloned_config)
        self.assertEqual(cloned_config.model_name, self.llm_config.model_name)
        self.assertEqual(cloned_config.api_key, self.llm_config.api_key)
        self.assertFalse(cloned_config.is_default)

    def test_student_cannot_clone_config(self):
        """Test that students cannot clone configs."""
        self.client.login(username="student", password="testpass123")

        response = self.client.get(
            reverse(
                "llm:config-clone",
                kwargs={"course_id": self.course.id, "config_id": self.llm_config.id},
            )
        )

        self.assertIn(response.status_code, [302, 403])


class TestLLMServiceCourseScoped(LLMViewsTestCase):
    """Test cases for LLM service course-scoped methods."""

    def test_get_configs_for_course(self):
        """Test getting configs for a specific course."""
        configs = LLMService.get_configs_for_course(self.course.id)

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].name, "Test Config")

    def test_get_configs_for_course_empty(self):
        """Test getting configs for a course with no configs."""
        empty_course = Course.objects.create(
            name="Empty Course", code="EMPTY101", description="No configs here"
        )

        configs = LLMService.get_configs_for_course(empty_course.id)

        self.assertEqual(len(configs), 0)

    def test_get_default_config_for_course(self):
        """Test getting default config for a specific course."""
        default_config = LLMService.get_default_config_for_course(self.course.id)

        self.assertIsNotNone(default_config)
        self.assertEqual(default_config.name, "Test Config")
        self.assertTrue(default_config.is_default)

    def test_clone_config_to_course(self):
        """Test cloning a config to another course."""
        target_course = Course.objects.create(
            name="Target Course", code="TARGET101", description="Cloning target"
        )

        result = LLMService.clone_config_to_course(self.llm_config.id, target_course.id)

        self.assertTrue(result.success)

        cloned = LLMConfig.objects.get(course=target_course, name=self.llm_config.name)
        self.assertEqual(cloned.model_name, self.llm_config.model_name)
        self.assertFalse(cloned.is_default)

    def test_get_or_create_default_for_course(self):
        """Test getting or creating default config for a course."""
        new_course = Course.objects.create(
            name="New Course", code="NEW101", description="New course"
        )

        result = LLMService.get_or_create_default_for_course(new_course.id)

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Global Default")

        configs = LLMConfig.objects.filter(course=new_course)
        self.assertTrue(configs.exists())


class TestLLMGenerateAPIView(LLMViewsTestCase):
    """Test cases for LLMGenerateAPIView."""

    @patch("llm.services.LLMService.get_response")
    def test_api_generate_response(self, mock_get_response):
        """Test the API endpoint for generating responses."""
        self.client.login(username="student", password="testpass123")

        mock_get_response.return_value = LLMResponseWithTools(
            response_text="This is an AI response.",
            function_calls=None,
            tokens_used=20,
            success=True,
        )

        from homeworks.models import Homework, Section
        from conversations.models import Conversation

        homework = Homework.objects.create(
            title="Test Homework",
            description="Test homework description",
            created_by=self.teacher,
            course=self.course,
            due_date="2024-12-31 23:59:59",
            llm_config=self.llm_config,
        )

        section = Section.objects.create(
            homework=homework,
            title="Test Section",
            content="Test section content",
            order=1,
        )

        conversation = Conversation.objects.create(
            user=self.student_user, section=section
        )

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

        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(data["response_text"], "This is an AI response.")


class TestLLMConfigsAPIView(LLMViewsTestCase):
    """Test cases for LLMConfigsAPIView."""

    def test_api_get_configs(self):
        """Test the API endpoint for getting all configs."""
        self.client.login(username="student", password="testpass123")

        response = self.client.get(reverse("llm:api-configs"))

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["configs"]), 1)

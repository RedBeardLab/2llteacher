from django.test import TestCase

from accounts.models import Teacher, User
from courses.models import Course
from llm.models import GlobalLLMDefault
from rag.huey import huey
from rag.tasks import _resolve_embedding_api_key


class ResolveApiKeyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", password="password123")
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(
            name="Test", code="TST", description="Test", is_active=True
        )

    def test_returns_empty_string_when_no_config_exists(self):
        key = _resolve_embedding_api_key(str(self.course.id))
        self.assertEqual(key, "")

    def test_returns_key_from_global_default(self):
        GlobalLLMDefault.objects.create(
            name="Default",
            model_name="gpt-4o",
            api_key="global-key",
            is_active=True,
        )
        key = _resolve_embedding_api_key(str(self.course.id))
        self.assertEqual(key, "global-key")

    def test_returns_key_from_course_config(self):
        GlobalLLMDefault.objects.create(
            name="Default",
            model_name="gpt-4o",
            api_key="global-key",
            is_active=True,
        )
        from llm.models import LLMConfig

        LLMConfig.objects.create(
            name="Course Config",
            model_name="gpt-4o",
            api_key="course-key",
            is_active=True,
            course=self.course,
        )
        key = _resolve_embedding_api_key(str(self.course.id))
        self.assertEqual(key, "course-key")


class HueyInstanceTests(TestCase):
    def test_huey_is_immediate_in_test_mode(self):
        self.assertTrue(huey.immediate)

    def test_huey_uses_base_class_when_immediate(self):
        from django.test.utils import override_settings
        with override_settings(HUEY={"name": "t", "filename": ":memory:", "immediate": True}):
            from rag.huey import _get_huey
            instance = _get_huey()
            self.assertEqual(type(instance).__name__, "Huey")

    def test_huey_uses_sqlite_when_not_immediate(self):
        from django.test.utils import override_settings
        with override_settings(HUEY={"name": "t", "filename": ":memory:", "immediate": False}):
            from rag.huey import _get_huey
            instance = _get_huey()
            self.assertEqual(type(instance).__name__, "SqliteHuey")

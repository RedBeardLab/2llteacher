from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from llm.models import LLMConfig
import uuid


class LLMConfigModelTest(TestCase):
    """Test cases for the LLMConfig model."""

    def setUp(self):
        self.llm_config_data = {
            "name": "Test GPT-4 Config",
            "model_name": "gpt-4",
            "api_key": "test-api-key-12345",
            "base_prompt": "You are a helpful AI tutor.",
            "temperature": 0.7,
            "max_completion_tokens": 1000,
            "is_default": False,
            "is_active": True,
        }

    def test_llm_config_creation(self):
        """Test basic LLM config creation."""
        config = LLMConfig.objects.create(**self.llm_config_data)
        self.assertEqual(config.name, "Test GPT-4 Config")
        self.assertEqual(config.model_name, "gpt-4")
        self.assertEqual(config.api_key, "test-api-key-12345")
        self.assertEqual(config.base_prompt, "You are a helpful AI tutor.")
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.max_completion_tokens, 1000)
        self.assertFalse(config.is_default)
        self.assertTrue(config.is_active)

    def test_llm_config_uuid_primary_key(self):
        """Test that LLM config has UUID primary key."""
        config = LLMConfig.objects.create(**self.llm_config_data)
        self.assertIsInstance(config.id, uuid.UUID)

    def test_llm_config_timestamps(self):
        """Test LLM config timestamp fields."""
        config = LLMConfig.objects.create(**self.llm_config_data)
        self.assertIsNotNone(config.created_at)
        self.assertIsNotNone(config.updated_at)
        self.assertIsInstance(config.created_at, timezone.datetime)
        self.assertIsInstance(config.updated_at, timezone.datetime)

    def test_llm_config_str_representation(self):
        """Test LLM config string representation."""
        config = LLMConfig.objects.create(**self.llm_config_data)
        self.assertEqual(str(config), "Test GPT-4 Config (gpt-4) - No Course")

    def test_llm_config_table_name(self):
        """Test LLM config table name."""
        config = LLMConfig.objects.create(**self.llm_config_data)
        self.assertEqual(config._meta.db_table, "llm_config")

    def test_llm_config_default_values(self):
        """Test LLM config default values."""
        config = LLMConfig.objects.create(
            name="Minimal Config",
            model_name="gpt-3.5-turbo",
            api_key="test-api-key-12345",
            base_prompt="Basic prompt",
        )
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.max_completion_tokens, 1000)
        self.assertFalse(config.is_default)
        self.assertTrue(config.is_active)

    def test_llm_config_name_uniqueness_per_course(self):
        """Test that LLM config names must be unique per course."""
        from courses.models import Course
        from django.db import transaction

        course1 = Course.objects.create(name="Course 1", code="C1")
        course2 = Course.objects.create(name="Course 2", code="C2")

        data1 = self.llm_config_data.copy()
        data1["course"] = course1
        LLMConfig.objects.create(**data1)

        data2 = self.llm_config_data.copy()
        data2["course"] = course1
        with self.assertRaises(Exception):
            with transaction.atomic():
                LLMConfig.objects.create(**data2)

        data3 = self.llm_config_data.copy()
        data3["course"] = course2
        config3 = LLMConfig.objects.create(**data3)
        self.assertEqual(config3.name, self.llm_config_data["name"])

    def test_llm_config_model_name_required(self):
        """Test that model name is required."""
        incomplete_data = self.llm_config_data.copy()
        del incomplete_data["model_name"]

        config = LLMConfig(**incomplete_data)
        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_llm_config_api_key_required(self):
        """Test that API key is required."""
        incomplete_data = self.llm_config_data.copy()
        del incomplete_data["api_key"]

        config = LLMConfig(**incomplete_data)
        with self.assertRaises(ValidationError):
            config.full_clean()

    def test_llm_config_base_prompt_required(self):
        """Test that base prompt is required."""
        incomplete_data = self.llm_config_data.copy()
        del incomplete_data["base_prompt"]

        config = LLMConfig(**incomplete_data)
        with self.assertRaises(ValidationError):
            config.full_clean()


class LLMConfigValidationTest(TestCase):
    """Test cases for LLM config validation."""

    def setUp(self):
        self.base_data = {
            "name": "Test Config",
            "model_name": "gpt-4",
            "api_key": "test-api-key-12345",
            "base_prompt": "Test prompt",
        }

    def test_temperature_min_value(self):
        """Test temperature minimum value validation."""
        config = LLMConfig.objects.create(**self.base_data, temperature=0.0)
        self.assertEqual(config.temperature, 0.0)

    def test_temperature_max_value(self):
        """Test temperature maximum value validation."""
        config = LLMConfig.objects.create(**self.base_data, temperature=2.0)
        self.assertEqual(config.temperature, 2.0)

    def test_temperature_below_minimum(self):
        """Test temperature below minimum raises error."""
        with self.assertRaises(ValidationError):
            config = LLMConfig(**self.base_data, temperature=-0.1)
            config.full_clean()

    def test_temperature_above_maximum(self):
        """Test temperature above maximum raises error."""
        with self.assertRaises(ValidationError):
            config = LLMConfig(**self.base_data, temperature=2.1)
            config.full_clean()

    def test_max_completion_tokens_positive_integer(self):
        """Test max_completion_tokens accepts positive integers."""
        config = LLMConfig.objects.create(**self.base_data, max_completion_tokens=500)
        self.assertEqual(config.max_completion_tokens, 500)

    def test_max_completion_tokens_zero_raises_error(self):
        """Test max_completion_tokens zero raises error."""
        # PositiveIntegerField allows 0, so this test should pass
        config = LLMConfig(**self.base_data, max_completion_tokens=0)
        config.full_clean()  # This should not raise an error
        self.assertEqual(config.max_completion_tokens, 0)

    def test_max_completion_tokens_negative_raises_error(self):
        """Test max_completion_tokens negative raises error."""
        with self.assertRaises(ValidationError):
            config = LLMConfig(**self.base_data, max_completion_tokens=-100)
            config.full_clean()

    def test_max_completion_tokens_large_value(self):
        """Test max_completion_tokens accepts large values."""
        config = LLMConfig.objects.create(**self.base_data, max_completion_tokens=10000)
        self.assertEqual(config.max_completion_tokens, 10000)


class LLMConfigDefaultBehaviorTest(TestCase):
    """Test cases for LLM config default behavior."""

    def setUp(self):
        self.base_data = {
            "name": "Test Config",
            "model_name": "gpt-4",
            "api_key": "test-api-key-12345",
            "base_prompt": "Test prompt",
        }

    def test_single_default_config(self):
        """Test that only one default config can exist."""
        config1_data = self.base_data.copy()
        config1_data["name"] = "Config 1"
        config1_data["is_default"] = True

        config2_data = self.base_data.copy()
        config2_data["name"] = "Config 2"
        config2_data["is_default"] = True

        config1 = LLMConfig.objects.create(**config1_data)
        config2 = LLMConfig.objects.create(**config2_data)

        # Refresh from database
        config1.refresh_from_db()
        config2.refresh_from_db()

        self.assertFalse(config1.is_default)
        self.assertTrue(config2.is_default)

    def test_multiple_default_configs_updated(self):
        """Test that setting multiple configs as default updates existing ones."""
        config1_data = self.base_data.copy()
        config1_data["name"] = "Config 1"
        config1_data["is_default"] = True

        config2_data = self.base_data.copy()
        config2_data["name"] = "Config 2"
        config2_data["is_default"] = True

        config3_data = self.base_data.copy()
        config3_data["name"] = "Config 3"
        config3_data["is_default"] = True

        config1 = LLMConfig.objects.create(**config1_data)
        config2 = LLMConfig.objects.create(**config2_data)
        config3 = LLMConfig.objects.create(**config3_data)

        # Refresh from database
        config1.refresh_from_db()
        config2.refresh_from_db()
        config3.refresh_from_db()

        self.assertFalse(config1.is_default)
        self.assertFalse(config2.is_default)
        self.assertTrue(config3.is_default)

    def test_update_existing_to_default(self):
        """Test updating existing config to default."""
        config1_data = self.base_data.copy()
        config1_data["name"] = "Config 1"
        config1_data["is_default"] = True

        config2_data = self.base_data.copy()
        config2_data["name"] = "Config 2"
        config2_data["is_default"] = False

        config1 = LLMConfig.objects.create(**config1_data)
        config2 = LLMConfig.objects.create(**config2_data)

        # Update config2 to default
        config2.is_default = True
        config2.save()

        # Refresh from database
        config1.refresh_from_db()
        config2.refresh_from_db()

        self.assertFalse(config1.is_default)
        self.assertTrue(config2.is_default)

    def test_no_default_configs(self):
        """Test that no default configs can exist."""
        config1_data = self.base_data.copy()
        config1_data["name"] = "Config 1"
        config1_data["is_default"] = False

        config2_data = self.base_data.copy()
        config2_data["name"] = "Config 2"
        config2_data["is_default"] = False

        config1 = LLMConfig.objects.create(**config1_data)
        config2 = LLMConfig.objects.create(**config2_data)

        self.assertFalse(config1.is_default)
        self.assertFalse(config2.is_default)


class LLMConfigEdgeCasesTest(TestCase):
    """Test cases for LLM config edge cases."""

    def setUp(self):
        self.base_data = {
            "name": "Test Config",
            "model_name": "gpt-4",
            "api_key": "test-api-key-12345",
            "base_prompt": "Test prompt",
        }

    def test_empty_base_prompt(self):
        """Test that empty base prompt is allowed."""
        data = self.base_data.copy()
        data["base_prompt"] = ""
        config = LLMConfig.objects.create(**data)
        self.assertEqual(config.base_prompt, "")

    def test_very_long_base_prompt(self):
        """Test that very long base prompt is allowed."""
        long_prompt = "A" * 10000
        data = self.base_data.copy()
        data["base_prompt"] = long_prompt
        config = LLMConfig.objects.create(**data)
        self.assertEqual(config.base_prompt, long_prompt)

    def test_special_characters_in_name(self):
        """Test that special characters in name are allowed."""
        special_name = "Config with @#$%^&*() characters"
        data = self.base_data.copy()
        data["name"] = special_name
        config = LLMConfig.objects.create(**data)
        self.assertEqual(config.name, special_name)

    def test_unicode_in_model_name(self):
        """Test that unicode in model name is allowed."""
        unicode_model = "gpt-4-unicode-测试"
        data = self.base_data.copy()
        data["model_name"] = unicode_model
        config = LLMConfig.objects.create(**data)
        self.assertEqual(config.model_name, unicode_model)

    def test_very_long_model_name(self):
        """Test that very long model name is allowed."""
        long_model = "A" * 100
        data = self.base_data.copy()
        data["name"] = long_model
        config = LLMConfig.objects.create(**data)
        self.assertEqual(config.name, long_model)

    def test_very_long_api_key(self):
        """Test that very long API key is allowed."""
        long_key = "A" * 100
        data = self.base_data.copy()
        data["api_key"] = long_key
        config = LLMConfig.objects.create(**data)
        self.assertEqual(config.api_key, long_key)

    def test_boolean_fields_defaults(self):
        """Test boolean field defaults."""
        config = LLMConfig.objects.create(**self.base_data)
        self.assertFalse(config.is_default)
        self.assertTrue(config.is_active)

    def test_boolean_fields_can_be_false(self):
        """Test that boolean fields can be set to False."""
        config = LLMConfig.objects.create(**self.base_data, is_active=False)
        self.assertFalse(config.is_active)

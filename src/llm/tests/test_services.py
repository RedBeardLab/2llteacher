"""
Tests for the LLMService class.

This module contains tests for the LLMService following
the testing-first architecture approach.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
import uuid

from llm.models import LLMConfig
from llm.services import (
    LLMService,
    LLMConfigData,
    LLMConfigCreateData,
    LLMConfigCreateResult,
    LLMConfigUpdateResult,
)

User = get_user_model()


class LLMServiceTestCase(TestCase):
    """Base test case for LLMService with common setup."""

    def setUp(self):
        """Set up test data."""
        # Create a test LLM config
        self.llm_config = LLMConfig.objects.create(
            name="Test Config",
            model_name="test-model",
            api_key="test-api-key-12345",
            base_prompt="You are a helpful AI tutor.",
            temperature=0.7,
            max_completion_tokens=1000,
            is_default=True,
            is_active=True,
        )


class TestLLMServiceConfig(LLMServiceTestCase):
    """Test cases for LLMService configuration methods."""

    def test_get_default_config(self):
        """Test retrieving the default LLM configuration."""
        config = LLMService.get_default_config()

        # Check result
        self.assertIsNotNone(config)
        assert config
        self.assertIsInstance(config, LLMConfigData)
        self.assertEqual(config.id, self.llm_config.id)
        self.assertEqual(config.name, self.llm_config.name)
        self.assertEqual(config.model_name, self.llm_config.model_name)
        self.assertTrue(config.is_default)

    def test_create_config(self):
        """Test creating a new LLM configuration."""
        # Create new config data using typed dataclass
        config_data = LLMConfigCreateData(
            name="New Config",
            model_name="new-model",
            api_key="new-test-api-key-67890",
            base_prompt="You are a new AI tutor.",
            temperature=0.5,
            max_completion_tokens=2000,
            is_default=False,
            is_active=True,
        )

        # Create config
        result = LLMService.create_config(config_data)

        # Check result
        self.assertIsInstance(result, LLMConfigCreateResult)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.config_id)

        # Check config was created
        new_config = LLMConfig.objects.get(id=result.config_id)
        self.assertEqual(new_config.name, config_data.name)
        self.assertEqual(new_config.model_name, config_data.model_name)
        self.assertEqual(new_config.temperature, config_data.temperature)

    def test_update_config(self):
        """Test updating an existing LLM configuration."""
        # Update data
        update_data = {"name": "Updated Config", "temperature": 0.8}

        # Update config
        result = LLMService.update_config(self.llm_config.id, update_data)

        # Check result
        self.assertIsInstance(result, LLMConfigUpdateResult)
        self.assertTrue(result.success)

        # Check config was updated
        updated_config = LLMConfig.objects.get(id=self.llm_config.id)
        self.assertEqual(updated_config.name, update_data["name"])
        self.assertEqual(updated_config.temperature, update_data["temperature"])

        # Check other fields remain unchanged
        self.assertEqual(updated_config.model_name, self.llm_config.model_name)
        self.assertEqual(updated_config.is_default, self.llm_config.is_default)


class TestLLMServiceResponses(LLMServiceTestCase):
    """Test cases for LLMService response generation methods."""

    def setUp(self):
        """Set up test data including conversation."""
        super().setUp()

        # Mock conversation and message data
        self.conversation = MagicMock()
        self.conversation.id = uuid.uuid4()
        self.conversation.section.title = "Test Section"
        self.conversation.section.content = "Test content for section."

        # Mock messages in conversation
        message1 = MagicMock()
        message1.content = "Hello, I need help with this section."
        message1.message_type = "student"
        message1.is_from_student = True
        message1.is_from_ai = False

        message2 = MagicMock()
        message2.content = "I'm here to help! What specific part are you stuck on?"
        message2.message_type = "ai"
        message2.is_from_student = False
        message2.is_from_ai = True

        # Mock the all() and order_by() methods
        messages_qs = MagicMock()
        messages_qs.order_by.return_value = [message1, message2]
        self.conversation.messages.all.return_value = messages_qs
        self.conversation.section.homework.llm_config = self.llm_config

    @patch("llm.services.OpenAI")
    def test_get_response(self, mock_openai_class):
        """Test generating an AI response."""

        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock the completion response
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "This is a test AI response."
        mock_completion.usage.total_tokens = 20

        mock_client.chat.completions.create.return_value = mock_completion

        # Get response
        response = LLMService.get_response(
            self.conversation,
            "I'm struggling with the concept of inheritance.",
            "student",
        )

        # Check result
        self.assertEqual(response, "This is a test AI response.")

        # Check OpenAI client was initialized with OpenRouter endpoint and API key
        mock_openai_class.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.llm_config.api_key
        )

        # Check API was called
        mock_client.chat.completions.create.assert_called_once()



    def test_is_meaningful_chunk_validation(self):
        """Test chunk validation logic."""
        # Test meaningful chunks
        self.assertTrue(LLMService._is_meaningful_chunk("Hello"))
        self.assertTrue(LLMService._is_meaningful_chunk("a"))
        self.assertTrue(LLMService._is_meaningful_chunk("  text  "))
        
        # Test non-meaningful chunks
        self.assertFalse(LLMService._is_meaningful_chunk(""))
        self.assertFalse(LLMService._is_meaningful_chunk("   "))
        self.assertFalse(LLMService._is_meaningful_chunk("\n\t  "))
        self.assertFalse(LLMService._is_meaningful_chunk("  \n  \t  "))

    # We no longer need to test _get_api_key as we now get the API key directly from config

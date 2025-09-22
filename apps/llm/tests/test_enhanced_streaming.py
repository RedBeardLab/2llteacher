"""
Tests for enhanced streaming with intelligent retry logic.

Testing the new streaming functionality with finish reason detection and retry logic.
"""

import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

from homeworks.models import Homework, Section
from conversations.models import Conversation
from accounts.models import Student, Teacher
from llm.services import LLMService, StreamTokenType, FinishReason, StreamingError, StreamToken

User = get_user_model()


class EnhancedStreamingTest(TestCase):
    """Test the enhanced streaming functionality with intelligent retry."""

    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        # Create student profile
        self.student_profile = Student.objects.create(user=self.user)

        # Create teacher for homework
        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="teacherpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create homework and section
        from datetime import datetime

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test description",
            created_by=self.teacher,
            due_date=datetime(2024, 12, 31),
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test section content",
            order=1,
        )

        # Create conversation
        self.conversation = Conversation.objects.create(
            user=self.user, section=self.section
        )

    @patch('llm.models.LLMConfig.objects.get')
    @patch('llm.services.LLMService.get_default_config')
    @patch('llm.services.LLMService._stream_with_finish_reason_detection')
    def test_successful_streaming_with_stop_finish_reason(self, mock_stream, mock_get_config, mock_llm_get):
        """Test successful streaming that ends with STOP finish reason."""
        # Mock LLM config
        from llm.services import LLMConfigData
        config_id = uuid.uuid4()
        mock_get_config.return_value = LLMConfigData(
            id=config_id, name="test", model_name="gpt-3.5-turbo",
            api_key="test-key", base_prompt="test", temperature=0.7,
            max_completion_tokens=1000, is_default=True, is_active=True
        )
        
        # Mock LLMConfig model get
        mock_llm_config = MagicMock()
        mock_llm_config.api_key = "test-key"
        mock_llm_get.return_value = mock_llm_config
        
        # Mock successful streaming response
        mock_stream.return_value = [
            ("Hello", None),
            (" there", None),
            ("! How", None),
            (" can I", None),
            (" help?", None),
            ("", FinishReason.STOP),  # Final chunk with finish reason
        ]

        # Test streaming
        tokens = list(LLMService.stream_response_with_completion(
            self.conversation, "Hello, I need help", "student"
        ))

        # Verify we got tokens and completion
        token_contents = [token.content for token in tokens if token.type == StreamTokenType.TOKEN]
        self.assertEqual(token_contents, ["Hello", " there", "! How", " can I", " help?"])

        # Verify completion signal
        completion_tokens = [token for token in tokens if token.type == StreamTokenType.COMPLETE]
        self.assertEqual(len(completion_tokens), 1)
        self.assertEqual(completion_tokens[0].content, "Hello there! How can I help?")
        self.assertEqual(completion_tokens[0].finish_reason, FinishReason.STOP)

    @patch('llm.models.LLMConfig.objects.get')
    @patch('llm.services.LLMService.get_default_config')
    @patch('llm.services.LLMService._stream_with_finish_reason_detection')
    def test_streaming_with_length_finish_reason_raises_error(self, mock_stream, mock_get_config, mock_llm_get):
        """Test that LENGTH finish reason raises StreamingError."""
        # Mock LLM config
        from llm.services import LLMConfigData
        config_id = uuid.uuid4()
        mock_get_config.return_value = LLMConfigData(
            id=config_id, name="test", model_name="gpt-3.5-turbo",
            api_key="test-key", base_prompt="test", temperature=0.7,
            max_completion_tokens=1000, is_default=True, is_active=True
        )
        
        # Mock LLMConfig model get
        mock_llm_config = MagicMock()
        mock_llm_config.api_key = "test-key"
        mock_llm_get.return_value = mock_llm_config
        
        # Mock response that hits length limit
        mock_stream.return_value = [
            ("This is a very long response", None),
            ("", FinishReason.LENGTH),  # Hit token limit
        ]

        # Test that StreamingError is raised
        with self.assertRaises(StreamingError) as context:
            list(LLMService.stream_response_with_completion(
                self.conversation, "Tell me everything", "student"
            ))

        self.assertIn("exceeded maximum length limit", str(context.exception))

    @patch('llm.models.LLMConfig.objects.get')
    @patch('llm.services.LLMService.get_default_config')
    @patch('llm.services.LLMService._stream_with_finish_reason_detection')
    def test_streaming_with_content_filter_raises_error(self, mock_stream, mock_get_config, mock_llm_get):
        """Test that CONTENT_FILTER finish reason raises StreamingError."""
        # Mock LLM config
        from llm.services import LLMConfigData
        config_id = uuid.uuid4()
        mock_get_config.return_value = LLMConfigData(
            id=config_id, name="test", model_name="gpt-3.5-turbo",
            api_key="test-key", base_prompt="test", temperature=0.7,
            max_completion_tokens=1000, is_default=True, is_active=True
        )
        
        # Mock LLMConfig model get
        mock_llm_config = MagicMock()
        mock_llm_config.api_key = "test-key"
        mock_llm_get.return_value = mock_llm_config
        
        # Mock response blocked by content filter
        mock_stream.return_value = [
            ("I cannot", None),
            ("", FinishReason.CONTENT_FILTER),  # Blocked by content filter
        ]

        # Test that StreamingError is raised
        with self.assertRaises(StreamingError) as context:
            list(LLMService.stream_response_with_completion(
                self.conversation, "Inappropriate request", "student"
            ))

        self.assertIn("blocked by content filter", str(context.exception))

    @patch('llm.models.LLMConfig.objects.get')
    @patch('llm.services.LLMService.get_default_config')
    @patch('llm.services.LLMService._stream_with_finish_reason_detection')
    def test_streaming_retry_on_interrupted_stream(self, mock_stream, mock_get_config, mock_llm_get):
        """Test retry logic when stream is interrupted (finish_reason=None)."""
        # Mock LLM config
        from llm.services import LLMConfigData
        config_id = uuid.uuid4()
        mock_get_config.return_value = LLMConfigData(
            id=config_id, name="test", model_name="gpt-3.5-turbo",
            api_key="test-key", base_prompt="test", temperature=0.7,
            max_completion_tokens=1000, is_default=True, is_active=True
        )
        
        # Mock LLMConfig model get
        mock_llm_config = MagicMock()
        mock_llm_config.api_key = "test-key"
        mock_llm_get.return_value = mock_llm_config
        
        # Mock interrupted stream on first attempt, success on second
        mock_stream.side_effect = [
            # First attempt - interrupted
            [
                ("Hello", None),
                ("", None),  # Interrupted stream
            ],
            # Second attempt - success
            [
                ("Hello", None),
                (" there", None),
                ("! How", None),
                (" can I", None),
                (" help?", None),
                ("", FinishReason.STOP),
            ]
        ]

        # Test streaming
        tokens = list(LLMService.stream_response_with_completion(
            self.conversation, "Hello, I need help", "student"
        ))

        # Verify we got tokens from both attempts (duplicates are expected during retries)
        token_contents = [token.content for token in tokens if token.type == StreamTokenType.TOKEN]
        self.assertEqual(token_contents, ["Hello", "Hello", " there", "! How", " can I", " help?"])

        # Verify completion signal has the correct final content (without duplicates)
        completion_tokens = [token for token in tokens if token.type == StreamTokenType.COMPLETE]
        self.assertEqual(len(completion_tokens), 1)
        self.assertEqual(completion_tokens[0].content, "Hello there! How can I help?")

        # Verify retry was attempted
        self.assertEqual(mock_stream.call_count, 2)

    @patch('llm.models.LLMConfig.objects.get')
    @patch('llm.services.LLMService.get_default_config')
    @patch('llm.services.LLMService._stream_with_finish_reason_detection')
    def test_streaming_retry_on_insufficient_content(self, mock_stream, mock_get_config, mock_llm_get):
        """Test retry logic when response has insufficient meaningful content."""
        # Mock LLM config
        from llm.services import LLMConfigData
        config_id = uuid.uuid4()
        mock_get_config.return_value = LLMConfigData(
            id=config_id, name="test", model_name="gpt-3.5-turbo",
            api_key="test-key", base_prompt="test", temperature=0.7,
            max_completion_tokens=1000, is_default=True, is_active=True
        )
        
        # Mock LLMConfig model get
        mock_llm_config = MagicMock()
        mock_llm_config.api_key = "test-key"
        mock_llm_get.return_value = mock_llm_config
        
        # Mock insufficient content on first attempt, success on second
        mock_stream.side_effect = [
            # First attempt - insufficient content
            [
                ("  ", None),  # Just whitespace
                ("", FinishReason.STOP),
            ],
            # Second attempt - success
            [
                ("Hello", None),
                (" there", None),
                ("!", None),
                ("", FinishReason.STOP),
            ]
        ]

        # Test streaming
        tokens = list(LLMService.stream_response_with_completion(
            self.conversation, "Hello", "student"
        ))

        # Verify we got the successful response from second attempt
        token_contents = [token.content for token in tokens if token.type == StreamTokenType.TOKEN]
        self.assertEqual(token_contents, ["Hello", " there", "!"])

        # Verify completion signal
        completion_tokens = [token for token in tokens if token.type == StreamTokenType.COMPLETE]
        self.assertEqual(len(completion_tokens), 1)
        self.assertEqual(completion_tokens[0].content, "Hello there!")

        # Verify retry was attempted
        self.assertEqual(mock_stream.call_count, 2)

    @patch('llm.models.LLMConfig.objects.get')
    @patch('llm.services.LLMService.get_default_config')
    @patch('llm.services.LLMService._stream_with_finish_reason_detection')
    def test_streaming_fails_after_max_retries(self, mock_stream, mock_get_config, mock_llm_get):
        """Test that streaming fails after maximum retry attempts."""
        # Mock LLM config
        from llm.services import LLMConfigData
        config_id = uuid.uuid4()
        mock_get_config.return_value = LLMConfigData(
            id=config_id, name="test", model_name="gpt-3.5-turbo",
            api_key="test-key", base_prompt="test", temperature=0.7,
            max_completion_tokens=1000, is_default=True, is_active=True
        )
        
        # Mock LLMConfig model get
        mock_llm_config = MagicMock()
        mock_llm_config.api_key = "test-key"
        mock_llm_get.return_value = mock_llm_config
        
        # Mock all attempts failing with interrupted streams
        mock_stream.return_value = [
            ("Hello", None),
            ("", None),  # Always interrupted
        ]

        # Test that StreamingError is raised after max retries
        with self.assertRaises(StreamingError) as context:
            list(LLMService.stream_response_with_completion(
                self.conversation, "Hello", "student"
            ))

        self.assertIn("Failed to generate response after 3 attempts", str(context.exception))
        
        # Verify all retry attempts were made
        self.assertEqual(mock_stream.call_count, 3)

    @patch('llm.models.LLMConfig.objects.get')
    @patch('llm.services.LLMService.get_default_config')
    @patch('llm.services.LLMService._stream_with_finish_reason_detection')
    def test_meaningful_chunk_filtering(self, mock_stream, mock_get_config, mock_llm_get):
        """Test that only meaningful chunks are yielded as tokens."""
        # Mock LLM config
        from llm.services import LLMConfigData
        config_id = uuid.uuid4()
        mock_get_config.return_value = LLMConfigData(
            id=config_id, name="test", model_name="gpt-3.5-turbo",
            api_key="test-key", base_prompt="test", temperature=0.7,
            max_completion_tokens=1000, is_default=True, is_active=True
        )
        
        # Mock LLMConfig model get
        mock_llm_config = MagicMock()
        mock_llm_config.api_key = "test-key"
        mock_llm_get.return_value = mock_llm_config
        
        # Mock response with meaningful and non-meaningful chunks
        mock_stream.return_value = [
            ("Hello", None),
            ("   ", None),  # Whitespace only - should be filtered
            (" there", None),
            ("", None),  # Empty - should be filtered
            ("!", None),
            ("", FinishReason.STOP),
        ]

        # Test streaming
        tokens = list(LLMService.stream_response_with_completion(
            self.conversation, "Hello", "student"
        ))

        # Verify only meaningful chunks were yielded as tokens
        token_contents = [token.content for token in tokens if token.type == StreamTokenType.TOKEN]
        self.assertEqual(token_contents, ["Hello", " there", "!"])

        # Verify complete response includes all content
        completion_tokens = [token for token in tokens if token.type == StreamTokenType.COMPLETE]
        self.assertEqual(len(completion_tokens), 1)
        self.assertEqual(completion_tokens[0].content, "Hello    there!")

    @patch('llm.services.OpenAI')
    def test_finish_reason_detection_integration(self, mock_openai_class):
        """Test finish reason detection with mocked OpenAI response."""
        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock streaming response chunks
        mock_chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"), finish_reason=None)]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" there"), finish_reason=None)]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="!"), finish_reason="stop")]),
        ]
        mock_client.chat.completions.create.return_value = iter(mock_chunks)

        # Test finish reason detection
        tokens_and_reasons = list(LLMService._stream_with_finish_reason_detection(
            MagicMock(api_key="test-key"),
            MagicMock(
                messages=[],
                homework_title="Test",
                section_title="Test",
                section_content="Test",
                current_message="Hello",
                message_type="student"
            )
        ))

        # Verify tokens and finish reason
        expected = [
            ("Hello", None),
            (" there", None),
            ("!", None),
            ("", FinishReason.STOP),
        ]
        self.assertEqual(tokens_and_reasons, expected)

    def test_stream_token_dataclass(self):
        """Test StreamToken dataclass functionality."""
        # Test token creation
        token = StreamToken(
            type=StreamTokenType.TOKEN,
            content="Hello",
        )
        self.assertEqual(token.type, StreamTokenType.TOKEN)
        self.assertEqual(token.content, "Hello")
        self.assertIsNone(token.finish_reason)

        # Test completion token
        completion = StreamToken(
            type=StreamTokenType.COMPLETE,
            content="Hello there!",
            finish_reason=FinishReason.STOP
        )
        self.assertEqual(completion.type, StreamTokenType.COMPLETE)
        self.assertEqual(completion.content, "Hello there!")
        self.assertEqual(completion.finish_reason, FinishReason.STOP)

    def test_finish_reason_enum_values(self):
        """Test FinishReason enum values match OpenAI API."""
        # Verify enum values match OpenAI API
        self.assertEqual(FinishReason.STOP, "stop")
        self.assertEqual(FinishReason.LENGTH, "length")
        self.assertEqual(FinishReason.CONTENT_FILTER, "content_filter")
        self.assertEqual(FinishReason.FUNCTION_CALL, "function_call")

    def test_stream_token_type_enum_values(self):
        """Test StreamTokenType enum values."""
        self.assertEqual(StreamTokenType.TOKEN, "token")
        self.assertEqual(StreamTokenType.COMPLETE, "complete")

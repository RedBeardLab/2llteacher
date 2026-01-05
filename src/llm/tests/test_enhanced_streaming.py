"""
Tests for enhanced streaming with intelligent retry logic.

Simplified version focusing on core functionality with minimal mocking.
"""

import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

from homeworks.models import Homework, Section
from conversations.models import Conversation
from accounts.models import Student, Teacher
from llm.models import LLMConfig
from llm.services import (
    LLMService,
    StreamTokenType,
    FinishReason,
    StreamingError,
    StreamToken,
)

User = get_user_model()


@patch("llm.services.OpenAI")
class EnhancedStreamingTest(TestCase):
    """Test the enhanced streaming functionality with intelligent retry."""

    def setUp(self):
        """Set up test data with minimal setup."""
        # Create test user and profiles
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.student_profile = Student.objects.create(user=self.user)

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@example.com", password="teacherpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create LLM config
        self.llm_config = LLMConfig.objects.create(
            name="Test Config",
            model_name="gpt-3.5-turbo",
            api_key="test-key",
            base_prompt="You are a helpful AI tutor.",
            temperature=0.7,
            max_completion_tokens=1000,
            is_default=True,
            is_active=True,
        )

        # Create course first
        from courses.models import Course
        from datetime import datetime

        self.course = Course.objects.create(
            name="Test Course",
            code="TEST101",
            description="Test course description",
        )

        # Create homework with course (direct FK relationship)
        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test description",
            created_by=self.teacher,
            course=self.course,
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

    def _create_mock_chunks(self, tokens, finish_reason=FinishReason.STOP):
        """Helper to create mock OpenAI streaming chunks."""
        chunks = []
        for token in tokens:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = token
            chunk.choices[0].finish_reason = None
            chunks.append(chunk)

        # Final chunk with finish reason
        final_chunk = MagicMock()
        final_chunk.choices = [MagicMock()]
        final_chunk.choices[0].delta = MagicMock()
        final_chunk.choices[0].delta.content = None
        final_chunk.choices[0].finish_reason = finish_reason
        chunks.append(final_chunk)

        return chunks

    def test_successful_streaming_with_stop_finish_reason(self, mock_openai_class):
        """Test successful streaming that ends with STOP finish reason."""
        # Setup mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        tokens = ["Hello", " there", "! How", " can I", " help?"]
        mock_chunks = self._create_mock_chunks(tokens, FinishReason.STOP)
        mock_client.chat.completions.create.return_value = iter(mock_chunks)

        # Test streaming
        stream_tokens = list(
            LLMService.stream_response_with_completion(
                self.conversation, "Hello, I need help", "student"
            )
        )

        # Verify tokens
        token_contents = [
            token.content
            for token in stream_tokens
            if token.type == StreamTokenType.TOKEN
        ]
        self.assertEqual(token_contents, tokens)

        # Verify completion signal
        completion_tokens = [
            token for token in stream_tokens if token.type == StreamTokenType.COMPLETE
        ]
        self.assertEqual(len(completion_tokens), 1)
        self.assertEqual(completion_tokens[0].content, "Hello there! How can I help?")
        self.assertEqual(completion_tokens[0].finish_reason, FinishReason.STOP)

    def test_streaming_error_conditions(self, mock_openai_class):
        """Test that LENGTH and CONTENT_FILTER finish reasons raise StreamingError."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Test LENGTH error
        length_chunks = self._create_mock_chunks(["Long response"], FinishReason.LENGTH)
        mock_client.chat.completions.create.return_value = iter(length_chunks)

        with self.assertRaises(StreamingError) as context:
            list(
                LLMService.stream_response_with_completion(
                    self.conversation, "Tell me everything", "student"
                )
            )
        self.assertIn("exceeded maximum length limit", str(context.exception))

        # Test CONTENT_FILTER error
        filter_chunks = self._create_mock_chunks(
            ["Blocked"], FinishReason.CONTENT_FILTER
        )
        mock_client.chat.completions.create.return_value = iter(filter_chunks)

        with self.assertRaises(StreamingError) as context:
            list(
                LLMService.stream_response_with_completion(
                    self.conversation, "Inappropriate request", "student"
                )
            )
        self.assertIn("blocked by content filter", str(context.exception))

    def test_streaming_retry_on_interruption(self, mock_openai_class):
        """Test retry logic when stream is interrupted."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # First attempt - interrupted (no finish_reason)
        interrupted_chunks = self._create_mock_chunks(["Hello"], None)

        # Second attempt - success
        success_chunks = self._create_mock_chunks(
            ["Hello", " there", "!"], FinishReason.STOP
        )

        mock_client.chat.completions.create.side_effect = [
            iter(interrupted_chunks),
            iter(success_chunks),
        ]

        # Test streaming
        stream_tokens = list(
            LLMService.stream_response_with_completion(
                self.conversation, "Hello", "student"
            )
        )

        # Verify retry was attempted
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)

        # Verify final success (tokens from both attempts)
        token_contents = [
            token.content
            for token in stream_tokens
            if token.type == StreamTokenType.TOKEN
        ]
        self.assertEqual(token_contents, ["Hello", "Hello", " there", "!"])

        completion_tokens = [
            token for token in stream_tokens if token.type == StreamTokenType.COMPLETE
        ]
        self.assertEqual(completion_tokens[0].content, "Hello there!")

    def test_streaming_retry_on_insufficient_content(self, mock_openai_class):
        """Test retry logic when response has insufficient content."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # First attempt - only whitespace
        insufficient_chunks = self._create_mock_chunks(["  "], FinishReason.STOP)

        # Second attempt - success
        success_chunks = self._create_mock_chunks(["Hello", "!"], FinishReason.STOP)

        mock_client.chat.completions.create.side_effect = [
            iter(insufficient_chunks),
            iter(success_chunks),
        ]

        # Test streaming
        stream_tokens = list(
            LLMService.stream_response_with_completion(
                self.conversation, "Hello", "student"
            )
        )

        # Verify retry was attempted
        self.assertEqual(mock_client.chat.completions.create.call_count, 2)

        # Verify we got the successful response
        token_contents = [
            token.content
            for token in stream_tokens
            if token.type == StreamTokenType.TOKEN
        ]
        self.assertEqual(token_contents, ["Hello", "!"])

    def test_streaming_fails_after_max_retries(self, mock_openai_class):
        """Test that streaming fails after maximum retry attempts."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # All attempts return interrupted streams
        interrupted_chunks = self._create_mock_chunks(["Hello"], None)
        mock_client.chat.completions.create.return_value = iter(interrupted_chunks)

        # Test that StreamingError is raised after max retries
        with self.assertRaises(StreamingError) as context:
            list(
                LLMService.stream_response_with_completion(
                    self.conversation, "Hello", "student"
                )
            )

        self.assertIn(
            "Failed to generate response after 3 attempts", str(context.exception)
        )
        self.assertEqual(mock_client.chat.completions.create.call_count, 3)

    def test_meaningful_chunk_filtering(self, mock_openai_class):
        """Test that only meaningful chunks are yielded as tokens."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mix of meaningful and non-meaningful chunks
        all_chunks = []
        contents = ["Hello", "   ", " there", "", "!"]  # Include whitespace and empty

        for content in contents:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta = MagicMock()
            chunk.choices[0].delta.content = content
            chunk.choices[0].finish_reason = None
            all_chunks.append(chunk)

        # Final chunk
        final_chunk = MagicMock()
        final_chunk.choices = [MagicMock()]
        final_chunk.choices[0].delta = MagicMock()
        final_chunk.choices[0].delta.content = None
        final_chunk.choices[0].finish_reason = FinishReason.STOP
        all_chunks.append(final_chunk)

        mock_client.chat.completions.create.return_value = iter(all_chunks)

        # Test streaming
        stream_tokens = list(
            LLMService.stream_response_with_completion(
                self.conversation, "Hello", "student"
            )
        )

        # Verify only meaningful chunks were yielded as tokens
        token_contents = [
            token.content
            for token in stream_tokens
            if token.type == StreamTokenType.TOKEN
        ]
        self.assertEqual(token_contents, ["Hello", " there", "!"])

        # Verify complete response includes all content
        completion_tokens = [
            token for token in stream_tokens if token.type == StreamTokenType.COMPLETE
        ]
        self.assertEqual(completion_tokens[0].content, "Hello    there!")

    def test_stream_token_dataclass(self, mock_openai_class):
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
            finish_reason=FinishReason.STOP,
        )
        self.assertEqual(completion.type, StreamTokenType.COMPLETE)
        self.assertEqual(completion.content, "Hello there!")
        self.assertEqual(completion.finish_reason, FinishReason.STOP)

    def test_enum_values(self, mock_openai_class):
        """Test enum values match expected API values."""
        # FinishReason enum values
        self.assertEqual(FinishReason.STOP, "stop")
        self.assertEqual(FinishReason.LENGTH, "length")
        self.assertEqual(FinishReason.CONTENT_FILTER, "content_filter")
        self.assertEqual(FinishReason.FUNCTION_CALL, "function_call")

        # StreamTokenType enum values
        self.assertEqual(StreamTokenType.TOKEN, "token")
        self.assertEqual(StreamTokenType.COMPLETE, "complete")

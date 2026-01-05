"""
Tests for LLM message structure and context management.

This module tests that conversation context (section content, homework info)
is not redundantly repeated in every message to the LLM.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock, call
import uuid

from llm.models import LLMConfig
from llm.services import LLMService
from homeworks.models import Homework, Section
from conversations.models import Conversation, Message
from accounts.models import Student, Teacher

User = get_user_model()


class TestMessageStructureWithoutContextRepetition(TestCase):
    """Test that section context is not repeated in every message."""

    def setUp(self):
        """Set up test data with a multi-turn conversation."""
        # Create users and profiles
        self.student_user = User.objects.create_user(
            username="teststudent", email="student@test.com", password="testpass123"
        )
        self.student_profile = Student.objects.create(user=self.student_user)

        self.teacher_user = User.objects.create_user(
            username="teacher", email="teacher@test.com", password="teacherpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        # Create LLM config
        self.llm_config = LLMConfig.objects.create(
            name="Test Config",
            model_name="gpt-3.5-turbo",
            api_key="test-api-key",
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
            title="Python Basics Homework",
            description="Learn Python fundamentals",
            created_by=self.teacher,
            course=self.course,
            due_date=datetime(2024, 12, 31),
            llm_config=self.llm_config,
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Understanding Variables",
            content="Variables in Python are used to store data. They can hold different types like integers, strings, and lists. You declare a variable by assigning a value to it using the = operator.",
            order=1,
        )

        # Create conversation using the service (includes initial AI greeting)
        from conversations.services import ConversationService

        result = ConversationService.start_conversation(self.student_user, self.section)
        self.conversation = Conversation.objects.get(id=result.conversation_id)

        # Add conversation history (2 back-and-forth exchanges after initial greeting)
        Message.objects.create(
            conversation=self.conversation,
            content="What is a variable in Python?",
            message_type=Message.MESSAGE_TYPE_STUDENT,
        )
        Message.objects.create(
            conversation=self.conversation,
            content="A variable is a container that stores data. What would you like to know specifically?",
            message_type=Message.MESSAGE_TYPE_AI,
        )
        Message.objects.create(
            conversation=self.conversation,
            content="How do I create a variable?",
            message_type=Message.MESSAGE_TYPE_STUDENT,
        )
        Message.objects.create(
            conversation=self.conversation,
            content="You create a variable by using the assignment operator =. For example: x = 5",
            message_type=Message.MESSAGE_TYPE_AI,
        )

    @patch("llm.services.OpenAI")
    def test_section_context_not_repeated_in_messages(self, mock_openai_class):
        """
        Test that section context (homework title, section title, section content)
        appears only ONCE in the conversation, not repeated in every user message.
        """
        # Setup mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock API response
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "Great question! Let me explain..."
        mock_completion.choices[0].message.tool_calls = None
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.total_tokens = 50
        mock_client.chat.completions.create.return_value = mock_completion

        # Make a new request (5th message in conversation)
        current_message = "Can variables change their type?"
        response = LLMService.get_response(
            self.conversation,
            current_message,
            "student",
            available_functions=[LLMService.get_stopping_rule_function()],
        )

        # Verify API was called
        self.assertTrue(mock_client.chat.completions.create.called)

        # Get the messages array that was sent to the API
        call_args = mock_client.chat.completions.create.call_args
        messages_sent = call_args.kwargs["messages"]

        # Expected structure:
        # 1. System message with base prompt AND section context
        # 2. Initial AI greeting (created by start_conversation)
        # 3. User message 1 - plain text
        # 4. AI response 1
        # 5. User message 2 - plain text
        # 6. AI response 2
        # 7. Current user message - plain text

        # Verify we have the right number of messages
        # System + initial AI + 4 history + 1 current = 7 messages
        self.assertEqual(
            len(messages_sent),
            7,
            f"Expected 7 messages (1 system + 1 initial AI + 4 history + 1 current), got {len(messages_sent)}",
        )

        # Check system message - should contain base prompt AND section context
        self.assertEqual(messages_sent[0]["role"], "system")
        system_message = messages_sent[0]["content"]

        # System message should contain base prompt
        self.assertIn(
            self.llm_config.base_prompt,
            system_message,
            "System message should contain base prompt",
        )

        # System message should contain section context
        self.assertIn(
            "Python Basics Homework",
            system_message,
            "System message should contain homework title",
        )
        self.assertIn(
            "Understanding Variables",
            system_message,
            "System message should contain section title",
        )
        self.assertIn(
            "Variables in Python are used to store data",
            system_message,
            "System message should contain section content",
        )

        # Check initial AI greeting
        self.assertEqual(messages_sent[1]["role"], "assistant")
        self.assertIn(
            "Hello! I'm here to help you with Section", messages_sent[1]["content"]
        )

        # Check FIRST user message - should be PLAIN TEXT only
        self.assertEqual(messages_sent[2]["role"], "user")
        first_user_message = messages_sent[2]["content"]
        self.assertEqual(
            first_user_message,
            "What is a variable in Python?",
            "First user message should be just the question",
        )

        # Check first AI response
        self.assertEqual(messages_sent[3]["role"], "assistant")
        self.assertIn("A variable is a container", messages_sent[3]["content"])

        # Check SECOND user message - should be PLAIN TEXT only
        self.assertEqual(messages_sent[4]["role"], "user")
        second_user_message = messages_sent[4]["content"]
        self.assertEqual(
            second_user_message,
            "How do I create a variable?",
            "Second user message should be just the question",
        )

        # Check second AI response
        self.assertEqual(messages_sent[5]["role"], "assistant")
        self.assertIn("assignment operator", messages_sent[5]["content"])

        # Check CURRENT user message - should be PLAIN TEXT only
        self.assertEqual(messages_sent[6]["role"], "user")
        current_user_message = messages_sent[6]["content"]
        self.assertEqual(
            current_user_message,
            current_message,
            "Current user message should be just the question",
        )

    @patch("llm.services.OpenAI")
    def test_system_message_includes_full_context(self, mock_openai_class):
        """
        Test that the system message includes full section context.
        This is a separate test to clearly document expected behavior.
        """
        # Create a fresh conversation with no messages
        new_conversation = Conversation.objects.create(
            user=self.student_user, section=self.section
        )

        # Setup mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = "I'm here to help!"
        mock_completion.choices[0].message.tool_calls = None
        mock_completion.choices[0].finish_reason = "stop"
        mock_completion.usage.total_tokens = 30
        mock_client.chat.completions.create.return_value = mock_completion

        # Send first message
        first_message = "What is a variable?"
        response = LLMService.get_response(
            new_conversation,
            first_message,
            "student",
            available_functions=[LLMService.get_stopping_rule_function()],
        )

        # Get the messages array
        call_args = mock_client.chat.completions.create.call_args
        messages_sent = call_args.kwargs["messages"]

        # Should have: system message + first user message
        self.assertEqual(len(messages_sent), 2)

        # System message should contain full context
        system_message = messages_sent[0]["content"]
        self.assertIn(self.llm_config.base_prompt, system_message)
        self.assertIn("Python Basics Homework", system_message)
        self.assertIn("Understanding Variables", system_message)
        self.assertIn("Variables in Python are used to store data", system_message)

        # User message should be plain text
        first_user_content = messages_sent[1]["content"]
        self.assertEqual(first_user_content, first_message)

    @patch("llm.services.OpenAI")
    def test_streaming_also_avoids_context_repetition(self, mock_openai_class):
        """
        Test that streaming API calls also avoid repeating context.
        """
        # Setup mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Create mock streaming chunks
        chunks = []
        for token in ["Hello", " there", "!"]:
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
        final_chunk.choices[0].finish_reason = "stop"
        chunks.append(final_chunk)

        mock_client.chat.completions.create.return_value = iter(chunks)

        # Stream a response (this is the 5th message)
        list(
            LLMService.stream_response_with_completion(
                self.conversation,
                "Can you explain more?",
                "student",
                available_functions=[LLMService.get_stopping_rule_function()],
            )
        )

        # Get the messages array
        call_args = mock_client.chat.completions.create.call_args
        messages_sent = call_args.kwargs["messages"]

        # Should have 7 messages (system + initial AI + 4 history + 1 current)
        self.assertEqual(len(messages_sent), 7)

        # Verify user messages (indices 2, 4, 6) don't repeat context
        for i in [2, 4, 6]:  # Indices of user messages 1, 2, and 3
            user_message = messages_sent[i]["content"]
            self.assertNotIn(
                "Python Basics Homework",
                user_message,
                f"User message at index {i} should not repeat homework title",
            )
            self.assertNotIn(
                "Variables in Python are used to store data",
                user_message,
                f"User message at index {i} should not repeat section content",
            )

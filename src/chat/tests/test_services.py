import json
from unittest.mock import patch, MagicMock

from django.test import TestCase

from accounts.models import User, Teacher
from courses.models import Course, CourseTeacher
from chat.models import Chat, ChatMessage
from chat.services import ChatService


class ChatServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="teacher1")
        self.teacher = Teacher.objects.create(user=self.user)
        self.course = Course.objects.create(name="Test Course", code="TC101")

    def test_start_chat_creates_new(self):
        chat = ChatService.start_chat(self.user, self.course)
        self.assertEqual(chat.user, self.user)
        self.assertEqual(chat.course, self.course)
        self.assertFalse(chat.is_deleted)
        self.assertEqual(chat.messages.count(), 1)
        self.assertEqual(
            chat.messages.first().message_type, ChatMessage.MESSAGE_TYPE_AI
        )

    def test_start_chat_reuses_existing(self):
        chat1 = ChatService.start_chat(self.user, self.course)
        chat2 = ChatService.start_chat(self.user, self.course)
        self.assertEqual(chat1.id, chat2.id)
        self.assertEqual(chat1.messages.count(), 1)

    def test_start_chat_starts_new_after_delete(self):
        chat1 = ChatService.start_chat(self.user, self.course)
        chat1.is_deleted = True
        chat1.save()
        chat2 = ChatService.start_chat(self.user, self.course)
        self.assertNotEqual(chat1.id, chat2.id)
        self.assertFalse(chat2.is_deleted)

    def test_create_chat_always_creates_new(self):
        chat1 = ChatService.create_chat(self.user, self.course)
        chat2 = ChatService.create_chat(self.user, self.course)
        self.assertNotEqual(chat1.id, chat2.id)
        self.assertEqual(chat1.messages.count(), 1)
        self.assertEqual(chat2.messages.count(), 1)
        self.assertEqual(chat1.course, self.course)
        self.assertEqual(chat1.user, self.user)

    def test_build_chat_messages_empty(self):
        chat = ChatService.start_chat(self.user, self.course)
        messages = ChatService._build_chat_messages(chat)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Course: Test Course", messages[0]["content"])
        self.assertEqual(messages[1]["role"], "assistant")

    def test_build_chat_messages_with_history(self):
        chat = ChatService.start_chat(self.user, self.course)
        ChatMessage.objects.create(
            chat=chat, content="Hello", message_type=ChatMessage.MESSAGE_TYPE_STUDENT
        )
        messages = ChatService._build_chat_messages(chat)
        user_msgs = [
            m for m in messages if m["role"] == "user" and m.get("content")
        ]
        self.assertEqual(len(user_msgs), 1)

    def test_build_chat_messages_with_tool_call(self):
        chat = ChatService.start_chat(self.user, self.course)
        ai_msg = ChatMessage.objects.create(
            chat=chat,
            content="P-value is...",
            message_type=ChatMessage.MESSAGE_TYPE_AI,
            tool_call_id="call_xyz",
            tool_call_arguments='{"query": "p-value definition"}',
        )
        ChatMessageContext = __import__("chat.models", fromlist=["ChatMessageContext"]).ChatMessageContext
        ChatMessageContext.objects.create(
            message=ai_msg,
            material_title="Chapter 5.pdf",
            page_start=42,
            page_end=42,
            content="A p-value is the probability...",
            score=0.15,
            query="p-value definition",
        )
        messages = ChatService._build_chat_messages(chat)
        tool_calls = [m for m in messages if m.get("tool_calls")]
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(
            tool_calls[0]["tool_calls"][0]["function"]["name"],
            "retrieve_knowledge",
        )
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        self.assertEqual(len(tool_msgs), 1)
        self.assertIn("Chapter 5.pdf", tool_msgs[0]["content"])

from django.test import TestCase
from django.core.exceptions import ValidationError

from accounts.models import User
from courses.models import Course
from chat.models import Chat, ChatMessage, ChatMessageContext


class ChatModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="testuser")
        self.course = Course.objects.create(name="Test Course", code="TC101")

    def test_chat_str(self):
        chat = Chat.objects.create(
            user=self.user, course=self.course, title="Test Chat"
        )
        self.assertIn("Test Course", str(chat))

    def test_chat_defaults(self):
        chat = Chat.objects.create(user=self.user, course=self.course)
        self.assertFalse(chat.is_deleted)
        self.assertEqual(chat.title, "")

    def test_chat_message_creation(self):
        chat = Chat.objects.create(user=self.user, course=self.course)
        msg = ChatMessage.objects.create(
            chat=chat,
            content="Hello",
            message_type=ChatMessage.MESSAGE_TYPE_STUDENT,
        )
        self.assertEqual(msg.message_type, "student")
        self.assertIn("student", str(msg))

    def test_chat_message_context_str(self):
        chat = Chat.objects.create(user=self.user, course=self.course)
        msg = ChatMessage.objects.create(
            chat=chat, content="test", message_type=ChatMessage.MESSAGE_TYPE_AI
        )
        ctx = ChatMessageContext.objects.create(
            message=msg,
            material_title="Chapter 1.pdf",
            page_start=5,
            page_end=7,
            content="Some chunk text",
            score=0.15,
            query="test query",
        )
        self.assertIn("Chapter 1.pdf", str(ctx))
        self.assertIn("0.150", str(ctx))

    def test_chat_meta_ordering(self):
        c1 = Chat.objects.create(user=self.user, course=self.course)
        c2 = Chat.objects.create(user=self.user, course=self.course)
        self.assertQuerySetEqual(Chat.objects.all(), [c2, c1], transform=lambda c: c)

    def test_message_meta_ordering(self):
        chat = Chat.objects.create(user=self.user, course=self.course)
        m1 = ChatMessage.objects.create(chat=chat, content="A", message_type="student")
        m2 = ChatMessage.objects.create(chat=chat, content="B", message_type="ai")
        self.assertQuerySetEqual(
            ChatMessage.objects.all(), [m1, m2], transform=lambda m: m
        )

    def test_context_meta_ordering_by_score(self):
        chat = Chat.objects.create(user=self.user, course=self.course)
        msg = ChatMessage.objects.create(chat=chat, content="test", message_type="ai")
        c1 = ChatMessageContext.objects.create(
            message=msg,
            material_title="A",
            page_start=1,
            page_end=1,
            content="x",
            score=0.5,
            query="q",
        )
        c2 = ChatMessageContext.objects.create(
            message=msg,
            material_title="B",
            page_start=2,
            page_end=2,
            content="y",
            score=0.1,
            query="q",
        )
        self.assertQuerySetEqual(
            ChatMessageContext.objects.all(), [c2, c1], transform=lambda c: c
        )

    def test_message_content_min_length(self):
        chat = Chat.objects.create(user=self.user, course=self.course)
        msg = ChatMessage(chat=chat, content="", message_type="student")
        with self.assertRaises(ValidationError):
            msg.full_clean()

    def test_message_type_constants(self):
        self.assertEqual(ChatMessage.MESSAGE_TYPE_STUDENT, "student")
        self.assertEqual(ChatMessage.MESSAGE_TYPE_AI, "ai")
        self.assertEqual(ChatMessage.MESSAGE_TYPE_SYSTEM, "system")

    def test_tool_call_fields(self):
        chat = Chat.objects.create(user=self.user, course=self.course)
        msg = ChatMessage.objects.create(
            chat=chat,
            content="AI response",
            message_type=ChatMessage.MESSAGE_TYPE_AI,
            tool_call_id="call_abc123",
            tool_call_arguments='{"query": "p-value"}',
        )
        self.assertEqual(msg.tool_call_id, "call_abc123")
        self.assertEqual(msg.tool_call_arguments, '{"query": "p-value"}')

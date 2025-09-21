from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from conversations.models import Conversation, Message, Submission
from accounts.models import Teacher, Student
from homeworks.models import Homework, Section
import uuid
from datetime import timedelta


class ConversationModelTest(TestCase):
    """Test cases for the Conversation model."""

    def setUp(self):
        self.User = get_user_model()
        self.teacher_user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.student_user = self.User.objects.create_user(
            username="teststudent", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)
        self.student = Student.objects.create(user=self.student_user)

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )

        self.conversation_data = {"user": self.student_user, "section": self.section}

    def test_conversation_creation(self):
        """Test basic conversation creation."""
        conversation = Conversation.objects.create(**self.conversation_data)
        self.assertEqual(conversation.user, self.student_user)
        self.assertEqual(conversation.section, self.section)
        self.assertFalse(conversation.is_deleted)
        self.assertIsNone(conversation.deleted_at)
        self.assertIsInstance(conversation.id, uuid.UUID)

    def test_conversation_uuid_primary_key(self):
        """Test that conversation has UUID primary key."""
        conversation = Conversation.objects.create(**self.conversation_data)
        self.assertIsInstance(conversation.id, uuid.UUID)

    def test_conversation_timestamps(self):
        """Test conversation timestamp fields."""
        conversation = Conversation.objects.create(**self.conversation_data)
        self.assertIsNotNone(conversation.created_at)
        self.assertIsNotNone(conversation.updated_at)
        self.assertIsInstance(conversation.created_at, timezone.datetime)
        self.assertIsInstance(conversation.updated_at, timezone.datetime)

    def test_conversation_str_representation(self):
        """Test conversation string representation."""
        conversation = Conversation.objects.create(**self.conversation_data)
        expected_str = f"Student conversation {conversation.id} - {conversation.user.username} on {conversation.section}"
        self.assertEqual(str(conversation), expected_str)

    def test_conversation_table_name(self):
        """Test conversation table name."""
        conversation = Conversation.objects.create(**self.conversation_data)
        self.assertEqual(conversation._meta.db_table, "conversations_conversation")

    def test_conversation_ordering(self):
        """Test conversation ordering by created_at descending."""
        conversation1 = Conversation.objects.create(**self.conversation_data)
        conversation2 = Conversation.objects.create(
            user=self.teacher_user, section=self.section
        )

        conversations = list(Conversation.objects.all())
        self.assertEqual(conversations[0], conversation2)
        self.assertEqual(conversations[1], conversation1)

    def test_conversation_soft_delete(self):
        """Test conversation soft delete functionality."""
        conversation = Conversation.objects.create(**self.conversation_data)
        original_deleted_at = conversation.deleted_at

        conversation.soft_delete()

        self.assertTrue(conversation.is_deleted)
        self.assertIsNotNone(conversation.deleted_at)
        self.assertNotEqual(conversation.deleted_at, original_deleted_at)

    def test_conversation_message_count_property(self):
        """Test conversation message_count property."""
        conversation = Conversation.objects.create(**self.conversation_data)
        self.assertEqual(conversation.message_count, 0)

        # Create a message
        Message.objects.create(
            conversation=conversation, content="Test message", message_type="student"
        )
        self.assertEqual(conversation.message_count, 1)

    def test_conversation_is_teacher_test_property(self):
        """Test conversation is_teacher_test property."""
        # Student conversation
        student_conversation = Conversation.objects.create(**self.conversation_data)
        self.assertFalse(student_conversation.is_teacher_test)

        # Teacher conversation
        teacher_conversation = Conversation.objects.create(
            user=self.teacher_user, section=self.section
        )
        self.assertTrue(teacher_conversation.is_teacher_test)

    def test_conversation_is_student_conversation_property(self):
        """Test conversation is_student_conversation property."""
        # Student conversation
        student_conversation = Conversation.objects.create(**self.conversation_data)
        self.assertTrue(student_conversation.is_student_conversation)

        # Teacher conversation
        teacher_conversation = Conversation.objects.create(
            user=self.teacher_user, section=self.section
        )
        self.assertFalse(teacher_conversation.is_student_conversation)


class MessageModelTest(TestCase):
    """Test cases for the Message model."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.user)

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )

        self.conversation = Conversation.objects.create(
            user=self.user, section=self.section
        )

        self.message_data = {
            "conversation": self.conversation,
            "content": "This is a test message",
            "message_type": "student",
        }

    def test_message_creation(self):
        """Test basic message creation."""
        message = Message.objects.create(**self.message_data)
        self.assertEqual(message.conversation, self.conversation)
        self.assertEqual(message.content, "This is a test message")
        self.assertEqual(message.message_type, "student")
        self.assertIsInstance(message.id, uuid.UUID)

    def test_message_uuid_primary_key(self):
        """Test that message has UUID primary key."""
        message = Message.objects.create(**self.message_data)
        self.assertIsInstance(message.id, uuid.UUID)

    def test_message_timestamp(self):
        """Test message timestamp field."""
        message = Message.objects.create(**self.message_data)
        self.assertIsNotNone(message.timestamp)
        self.assertIsInstance(message.timestamp, timezone.datetime)

    def test_message_str_representation(self):
        """Test message string representation."""
        message = Message.objects.create(**self.message_data)
        expected_str = f"{message.message_type} message at {message.timestamp}"
        self.assertEqual(str(message), expected_str)

    def test_message_table_name(self):
        """Test message table name."""
        message = Message.objects.create(**self.message_data)
        self.assertEqual(message._meta.db_table, "conversations_message")

    def test_message_ordering(self):
        """Test message ordering by timestamp."""
        message1 = Message.objects.create(**self.message_data)
        message2 = Message.objects.create(
            conversation=self.conversation, content="Second message", message_type="ai"
        )

        messages = list(Message.objects.all())
        self.assertEqual(messages[0], message1)
        self.assertEqual(messages[1], message2)

    def test_message_content_min_length_validation(self):
        """Test message content minimum length validation."""
        with self.assertRaises(ValidationError):
            message = Message(
                conversation=self.conversation,
                content="",  # Empty content
                message_type="student",
            )
            message.full_clean()

    def test_message_content_with_minimum_length(self):
        """Test message content with minimum length."""
        message = Message.objects.create(
            conversation=self.conversation,
            content="A",  # Single character
            message_type="student",
        )
        self.assertEqual(message.content, "A")

    def test_message_type_constants(self):
        """Test message type constants."""
        self.assertEqual(Message.MESSAGE_TYPE_STUDENT, "student")
        self.assertEqual(Message.MESSAGE_TYPE_AI, "ai")
        self.assertEqual(Message.MESSAGE_TYPE_R_CODE, "code")
        self.assertEqual(Message.MESSAGE_TYPE_FILE_UPLOAD, "file_upload")
        self.assertEqual(Message.MESSAGE_TYPE_CODE_EXECUTION, "code_execution")
        self.assertEqual(Message.MESSAGE_TYPE_SYSTEM, "system")

    def test_message_is_from_student_property(self):
        """Test message is_from_student property."""
        # Student message
        student_message = Message.objects.create(**self.message_data)
        self.assertTrue(student_message.is_from_student)

        # AI message
        ai_message = Message.objects.create(
            conversation=self.conversation, content="AI response", message_type="ai"
        )
        self.assertFalse(ai_message.is_from_student)

        # R code message
        r_code_message = Message.objects.create(
            conversation=self.conversation,
            content='print("Hello")',
            message_type="code",
        )
        self.assertTrue(r_code_message.is_from_student)

        # File upload message
        file_message = Message.objects.create(
            conversation=self.conversation,
            content="file.pdf",
            message_type="file_upload",
        )
        self.assertTrue(file_message.is_from_student)

        # Code execution message
        code_exec_message = Message.objects.create(
            conversation=self.conversation,
            content="Output: Hello",
            message_type="code_execution",
        )
        self.assertTrue(code_exec_message.is_from_student)

    def test_message_is_from_ai_property(self):
        """Test message is_from_ai property."""
        # AI message
        ai_message = Message.objects.create(
            conversation=self.conversation, content="AI response", message_type="ai"
        )
        self.assertTrue(ai_message.is_from_ai)

        # Student message
        student_message = Message.objects.create(**self.message_data)
        self.assertFalse(student_message.is_from_ai)

    def test_message_is_system_message_property(self):
        """Test message is_system_message property."""
        # System message
        system_message = Message.objects.create(
            conversation=self.conversation,
            content="System notification",
            message_type="system",
        )
        self.assertTrue(system_message.is_system_message)

        # Student message
        student_message = Message.objects.create(**self.message_data)
        self.assertFalse(student_message.is_system_message)


class SubmissionModelTest(TestCase):
    """Test cases for the Submission model."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="teststudent", password="testpass123"
        )
        self.student = Student.objects.create(user=self.user)

        self.teacher_user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )

        self.conversation = Conversation.objects.create(
            user=self.user, section=self.section
        )

        self.submission_data = {"conversation": self.conversation}

    def test_submission_creation(self):
        """Test basic submission creation."""
        submission = Submission.objects.create(**self.submission_data)
        self.assertEqual(submission.conversation, self.conversation)
        self.assertIsInstance(submission.id, uuid.UUID)

    def test_submission_uuid_primary_key(self):
        """Test that submission has UUID primary key."""
        submission = Submission.objects.create(**self.submission_data)
        self.assertIsInstance(submission.id, uuid.UUID)

    def test_submission_submitted_at(self):
        """Test submission submitted_at field."""
        submission = Submission.objects.create(**self.submission_data)
        self.assertIsNotNone(submission.submitted_at)
        self.assertIsInstance(submission.submitted_at, timezone.datetime)

    def test_submission_str_representation(self):
        """Test submission string representation."""
        submission = Submission.objects.create(**self.submission_data)
        expected_str = f"Submission by {self.conversation.user.username} for {self.conversation.section}"
        self.assertEqual(str(submission), expected_str)

    def test_submission_table_name(self):
        """Test submission table name."""
        submission = Submission.objects.create(**self.submission_data)
        self.assertEqual(submission._meta.db_table, "conversations_submission")

    def test_submission_ordering(self):
        """Test submission ordering by submitted_at descending."""
        submission1 = Submission.objects.create(**self.submission_data)
        submission2 = Submission.objects.create(
            conversation=Conversation.objects.create(
                user=self.teacher_user, section=self.section
            )
        )

        submissions = list(Submission.objects.all())
        self.assertEqual(submissions[0], submission2)
        self.assertEqual(submissions[1], submission1)

    def test_submission_section_property(self):
        """Test submission section property."""
        submission = Submission.objects.create(**self.submission_data)
        self.assertEqual(submission.section, self.section)

    def test_submission_student_property(self):
        """Test submission student property."""
        submission = Submission.objects.create(**self.submission_data)
        self.assertEqual(submission.student, self.student)

    def test_submission_clean_method_validation(self):
        """Test submission clean method validation."""
        # Create first submission
        _submission1 = Submission.objects.create(**self.submission_data)

        # Try to create another submission for same student and section
        conversation2 = Conversation.objects.create(
            user=self.user, section=self.section
        )

        submission2 = Submission(conversation=conversation2)

        with self.assertRaises(ValidationError):
            submission2.clean()

    def test_submission_clean_method_same_submission(self):
        """Test submission clean method with same submission."""
        submission = Submission.objects.create(**self.submission_data)

        # Should not raise error when cleaning the same submission
        try:
            submission.clean()
        except ValidationError:
            self.fail("clean() raised ValidationError unexpectedly!")

    def test_submission_clean_method_different_sections(self):
        """Test submission clean method with different sections."""
        # Create another section
        section2 = Section.objects.create(
            homework=self.homework, title="Section 2", content="Content 2", order=2
        )

        # Create submission for first section
        _submission1 = Submission.objects.create(**self.submission_data)

        # Create submission for second section
        conversation2 = Conversation.objects.create(user=self.user, section=section2)
        submission2 = Submission(conversation=conversation2)

        # Should not raise error for different sections
        try:
            submission2.clean()
        except ValidationError:
            self.fail("clean() raised ValidationError unexpectedly!")

    def test_submission_clean_method_different_students(self):
        """Test submission clean method with different students."""
        # Create another student
        student2_user = self.User.objects.create_user(
            username="teststudent2", password="testpass123"
        )
        _student2 = Student.objects.create(user=student2_user)

        # Create submission for first student
        _submission1 = Submission.objects.create(**self.submission_data)

        # Create submission for second student
        conversation2 = Conversation.objects.create(
            user=student2_user, section=self.section
        )
        submission2 = Submission(conversation=conversation2)

        # Should not raise error for different students
        try:
            submission2.clean()
        except ValidationError:
            self.fail("clean() raised ValidationError unexpectedly!")


class ConversationMessageRelationshipTest(TestCase):
    """Test cases for conversation-message relationships."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.user)

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )

        self.conversation = Conversation.objects.create(
            user=self.user, section=self.section
        )

    def test_conversation_has_messages(self):
        """Test that conversation can have multiple messages."""
        message1 = Message.objects.create(
            conversation=self.conversation,
            content="First message",
            message_type="student",
        )
        message2 = Message.objects.create(
            conversation=self.conversation, content="Second message", message_type="ai"
        )

        messages = list(self.conversation.messages.all())
        self.assertEqual(len(messages), 2)
        self.assertIn(message1, messages)
        self.assertIn(message2, messages)

    def test_message_belongs_to_conversation(self):
        """Test that message belongs to conversation."""
        message = Message.objects.create(
            conversation=self.conversation,
            content="Test message",
            message_type="student",
        )
        self.assertEqual(message.conversation, self.conversation)

    def test_conversation_cascade_delete_messages(self):
        """Test that messages are deleted when conversation is deleted."""
        message = Message.objects.create(
            conversation=self.conversation,
            content="Test message",
            message_type="student",
        )
        message_id = message.id

        self.conversation.delete()
        self.assertFalse(Message.objects.filter(id=message_id).exists())


class ConversationSubmissionRelationshipTest(TestCase):
    """Test cases for conversation-submission relationships."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="teststudent", password="testpass123"
        )
        self.student = Student.objects.create(user=self.user)

        self.teacher_user = self.User.objects.create_user(
            username="testteacher", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.teacher_user)

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )

        self.conversation = Conversation.objects.create(
            user=self.user, section=self.section
        )

    def test_conversation_has_submission(self):
        """Test that conversation can have a submission."""
        submission = Submission.objects.create(conversation=self.conversation)
        self.assertEqual(self.conversation.submission, submission)

    def test_submission_belongs_to_conversation(self):
        """Test that submission belongs to conversation."""
        submission = Submission.objects.create(conversation=self.conversation)
        self.assertEqual(submission.conversation, self.conversation)

    def test_conversation_cascade_delete_submission(self):
        """Test that submission is deleted when conversation is deleted."""
        submission = Submission.objects.create(conversation=self.conversation)
        submission_id = submission.id

        self.conversation.delete()
        self.assertFalse(Submission.objects.filter(id=submission_id).exists())


class ModelEdgeCasesTest(TestCase):
    """Test cases for model edge cases."""

    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.teacher = Teacher.objects.create(user=self.user)

        self.homework = Homework.objects.create(
            title="Test Homework",
            description="Test Description",
            created_by=self.teacher,
            due_date=timezone.now() + timedelta(days=7),
        )

        self.section = Section.objects.create(
            homework=self.homework,
            title="Test Section",
            content="Test content",
            order=1,
        )

        self.conversation = Conversation.objects.create(
            user=self.user, section=self.section
        )

    def test_message_with_very_long_content(self):
        """Test message with very long content."""
        long_content = "A" * 10000
        message = Message.objects.create(
            conversation=self.conversation, content=long_content, message_type="student"
        )
        self.assertEqual(message.content, long_content)

    def test_message_with_very_long_message_type(self):
        """Test message with very long message type."""
        long_type = "A" * 50
        message = Message.objects.create(
            conversation=self.conversation,
            content="Test content",
            message_type=long_type,
        )
        self.assertEqual(message.message_type, long_type)

    def test_conversation_with_special_characters_in_str(self):
        """Test conversation string representation with special characters."""
        conversation = Conversation.objects.create(user=self.user, section=self.section)
        # Should not raise error
        str(conversation)

    def test_message_with_special_characters_in_content(self):
        """Test message with special characters in content."""
        special_content = "Message with @#$%^&*() characters and emojis 🚀🎉"
        message = Message.objects.create(
            conversation=self.conversation,
            content=special_content,
            message_type="student",
        )
        self.assertEqual(message.content, special_content)

    def test_submission_with_special_characters_in_str(self):
        """Test submission string representation with special characters."""
        submission = Submission.objects.create(conversation=self.conversation)
        # Should not raise error
        str(submission)

    def test_conversation_soft_delete_twice(self):
        """Test conversation soft delete called twice."""
        conversation = Conversation.objects.create(user=self.user, section=self.section)

        conversation.soft_delete()
        _first_deleted_at = conversation.deleted_at

        conversation.soft_delete()
        _second_deleted_at = conversation.deleted_at

        self.assertTrue(conversation.is_deleted)
        # The conversation should remain deleted after second call
        self.assertTrue(conversation.is_deleted)
        # The deleted_at should be set (not None)
        self.assertIsNotNone(conversation.deleted_at)

    def test_message_timestamp_accuracy(self):
        """Test message timestamp accuracy."""
        before_create = timezone.now()
        message = Message.objects.create(
            conversation=self.conversation,
            content="Test message",
            message_type="student",
        )
        after_create = timezone.now()

        self.assertGreaterEqual(message.timestamp, before_create)
        self.assertLessEqual(message.timestamp, after_create)

    def test_submission_submitted_at_accuracy(self):
        """Test submission submitted_at accuracy."""
        before_create = timezone.now()
        submission = Submission.objects.create(conversation=self.conversation)
        after_create = timezone.now()

        self.assertGreaterEqual(submission.submitted_at, before_create)
        self.assertLessEqual(submission.submitted_at, after_create)

"""
Conversation Service

This module provides services for managing conversations between users and AI tutors.
Following a testable-first approach with typed data contracts.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Iterator, TypedDict
from datetime import datetime
from uuid import UUID
from django.db import transaction

from accounts.models import User
from homeworks.models import Section

from .models import Conversation

# Import for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from accounts.models import Teacher, Student


# Data Contracts
@dataclass
class MessageProcessingRequest:
    """Unified request structure for message processing."""

    conversation_id: UUID
    user: User
    content: str
    message_type: str = "student"


@dataclass
class StreamEvent:
    """Base class for streaming events."""

    type: str
    timestamp: datetime
    data: dict[str, Any]


@dataclass
class MessageProcessingResult:
    """Unified result structure for message processing."""

    user_message_id: UUID
    ai_message_id: UUID
    success: bool = True
    error: Optional[str] = None


@dataclass
class MessageData:
    id: UUID
    content: str
    message_type: str
    timestamp: datetime
    is_from_student: bool
    is_from_ai: bool
    is_system_message: bool


@dataclass
class ConversationData:
    id: UUID
    user_id: UUID
    section_id: UUID
    section_title: str
    homework_id: UUID
    homework_title: str
    created_at: datetime
    updated_at: datetime
    is_teacher_test: bool
    is_student_conversation: bool
    can_submit: bool
    messages: Optional[List[MessageData]] = None


@dataclass
class ConversationStartResult:
    conversation_id: Optional[UUID]
    initial_message_id: Optional[UUID]
    section_id: UUID
    success: bool = True
    error: Optional[str] = None


@dataclass
class MessageSendResult:
    user_message_id: Optional[UUID] = None
    ai_message_id: Optional[UUID] = None
    ai_response: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class CodeExecutionResult:
    code_message_id: Optional[UUID] = None
    result_message_id: Optional[UUID] = None
    has_error: bool = False
    success: bool = True
    error: Optional[str] = None


class ConversationService:
    """
    Service class for conversation-related business logic.

    This service follows a testable-first approach with clear data contracts
    and properly typed methods for easier testing and maintenance.
    """

    @staticmethod
    def start_conversation(user: User, section: "Section") -> ConversationStartResult:
        """
        Start a new conversation for a user on a section.

        Args:
            user: User object who is starting the conversation
            section: Section object for the conversation

        Returns:
            ConversationStartResult object with operation results
        """
        from .models import Conversation, Message

        try:
            # Create new conversation
            conversation = Conversation.objects.create(user=user, section=section)

            # Create initial AI message
            initial_message_content = ConversationService._create_initial_message(
                section
            )
            message = Message.objects.create(
                conversation=conversation,
                content=initial_message_content,
                message_type=Message.MESSAGE_TYPE_AI,
            )

            # Return success result
            return ConversationStartResult(
                conversation_id=conversation.id,
                initial_message_id=message.id,
                section_id=section.id,
            )
        except Exception as e:
            # Return failure result
            return ConversationStartResult(
                conversation_id=None,
                initial_message_id=None,
                section_id=section.id,
                success=False,
                error=str(e),
            )

    @staticmethod
    def get_conversation_data(
        conversation_id: UUID, user: User
    ) -> Optional[ConversationData]:
        """
        Get conversation data including messages.

        Args:
            conversation_id: UUID of the conversation to retrieve
            user: User to determine can_submit status

        Returns:
            ConversationData if found, None otherwise
        """
        from .models import Conversation

        try:
            # Get conversation with optimized query including homework
            conversation = Conversation.objects.select_related(
                "user", "section", "section__homework"
            ).get(id=conversation_id)

            # Get all messages in conversation
            messages = conversation.messages.all().order_by("timestamp")

            # Create MessageData objects for each message
            message_data_list: List[MessageData] = []
            for msg in messages:
                message_data = MessageData(
                    id=msg.id,
                    content=msg.content,
                    message_type=msg.message_type,
                    timestamp=msg.timestamp,
                    is_from_student=msg.is_from_student,
                    is_from_ai=msg.is_from_ai,
                    is_system_message=msg.is_system_message,
                )
                message_data_list.append(message_data)

            # Determine if user can submit this conversation
            can_submit = (
                hasattr(user, "student_profile")
                and user.id == conversation.user.id
                and not conversation.is_deleted
                and not conversation.is_teacher_test
            )

            # Create and return conversation data
            return ConversationData(
                id=conversation.id,
                user_id=conversation.user.id,
                section_id=conversation.section.id,
                section_title=conversation.section.title,
                homework_id=conversation.section.homework.id,
                homework_title=conversation.section.homework.title,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
                is_teacher_test=conversation.is_teacher_test,
                is_student_conversation=conversation.is_student_conversation,
                can_submit=can_submit,
                messages=message_data_list,
            )
        except Conversation.DoesNotExist:
            return None
        except Exception:
            return None

    @staticmethod
    def add_system_message(
        conversation: "Conversation", content: str
    ) -> Optional[UUID]:
        """
        Add a system message to the conversation.

        Args:
            conversation: Conversation object
            content: System message content

        Returns:
            UUID of the created message if successful, None otherwise
        """
        from .models import Message

        try:
            message = Message.objects.create(
                conversation=conversation,
                content=content,
                message_type=Message.MESSAGE_TYPE_SYSTEM,
            )
            return message.id
        except Exception:
            return None

    @staticmethod
    def delete_teacher_test_conversation(conversation: "Conversation") -> bool:
        """
        Delete a teacher test conversation.

        Args:
            conversation: Conversation object to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Verify this is a teacher test conversation
            if not conversation.is_teacher_test:
                raise ValueError("Can only delete teacher test conversations.")

            # Soft delete the conversation
            conversation.soft_delete()
            return True
        except Exception:
            return False

    @staticmethod
    def get_teacher_test_conversations(
        teacher: "Teacher", section: Optional["Section"] = None
    ) -> List[ConversationData]:
        """
        Get teacher test conversations for a teacher.

        Args:
            teacher: Teacher object
            section: Optional Section object to filter by

        Returns:
            List of ConversationData for teacher test conversations
        """
        try:
            # Query for teacher's conversations that aren't deleted
            queryset = teacher.user.conversations.filter(is_deleted=False)

            # Filter by section if provided
            if section:
                queryset = queryset.filter(section=section)

            # Get conversations ordered by recency
            conversations = queryset.order_by("-created_at")

            # Create ConversationData objects for each conversation
            conversation_data_list: List[ConversationData] = []
            for conv in conversations:
                # Skip conversations that aren't teacher test conversations
                if not conv.is_teacher_test:
                    continue

                conversation_data = ConversationData(
                    id=conv.id,
                    user_id=conv.user.id,
                    section_id=conv.section.id,
                    section_title=conv.section.title,
                    homework_id=conv.section.homework.id,
                    homework_title=conv.section.homework.title,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    is_teacher_test=conv.is_teacher_test,
                    is_student_conversation=conv.is_student_conversation,
                    can_submit=False,  # Teacher test conversations can't be submitted
                )
                conversation_data_list.append(conversation_data)

            return conversation_data_list
        except Exception:
            return []

    @staticmethod
    def handle_r_code_execution(
        conversation: "Conversation",
        code: str,
        output: str,
        error: Optional[str] = None,
    ) -> CodeExecutionResult:
        """
        Handle R code execution and add results to conversation.

        Args:
            conversation: Conversation object
            code: R code that was executed
            output: Output from code execution
            error: Optional error message if execution failed

        Returns:
            CodeExecutionResult with message IDs and status
        """
        from .models import Message

        try:
            # Create message for R code
            code_message = Message.objects.create(
                conversation=conversation,
                content=code,
                message_type=Message.MESSAGE_TYPE_R_CODE,
            )

            # Create message for execution result based on whether there was an error
            if error:
                result_content = f"Error: {error}"
                result_type = Message.MESSAGE_TYPE_SYSTEM
                has_error = True
            else:
                result_content = f"Output:\n{output}"
                result_type = Message.MESSAGE_TYPE_CODE_EXECUTION
                has_error = False

            result_message = Message.objects.create(
                conversation=conversation,
                content=result_content,
                message_type=result_type,
            )

            # Return success result
            return CodeExecutionResult(
                code_message_id=code_message.id,
                result_message_id=result_message.id,
                has_error=has_error,
            )
        except Exception as e:
            # Return failure result
            return CodeExecutionResult(success=False, error=str(e))

    @staticmethod
    def process_message(
        request: MessageProcessingRequest, streaming: bool = False
    ) -> MessageProcessingResult | Iterator[StreamEvent]:
        """
        Unified message processing that supports both streaming and non-streaming modes.

        Args:
            request: MessageProcessingRequest with all necessary data
            streaming: If True, returns Iterator[StreamEvent], else MessageProcessingResult

        Returns:
            MessageProcessingResult for non-streaming, Iterator[StreamEvent] for streaming
        """
        from .models import Conversation, Message
        from llm.services import LLMService

        try:
            # Get conversation
            conversation = Conversation.objects.get(id=request.conversation_id)

            # Validate request
            validation_error = ConversationService.validate_message_request(request)
            if validation_error:
                if streaming:
                    return ConversationService._create_error_stream(validation_error)
                else:
                    return MessageProcessingResult(
                        user_message_id=UUID("00000000-0000-0000-0000-000000000000"),
                        ai_message_id=UUID("00000000-0000-0000-0000-000000000000"),
                        success=False,
                        error=validation_error,
                    )

            # Authorize request
            if not ConversationService.authorize_message_request(request):
                error_msg = (
                    "You don't have permission to send messages in this conversation."
                )
                if streaming:
                    return ConversationService._create_error_stream(error_msg)
                else:
                    return MessageProcessingResult(
                        user_message_id=UUID("00000000-0000-0000-0000-000000000000"),
                        ai_message_id=UUID("00000000-0000-0000-0000-000000000000"),
                        success=False,
                        error=error_msg,
                    )

            # Create user message
            user_message = Message.objects.create(
                conversation=conversation,
                content=request.content,
                message_type=request.message_type,
            )

            if streaming:
                # Return streaming generator
                return ConversationService._process_streaming_response(
                    conversation, user_message, request.content, request.message_type
                )
            else:
                # Get complete AI response
                ai_response = LLMService.get_response(
                    conversation, request.content, request.message_type
                )

                # Create AI message
                ai_message = Message.objects.create(
                    conversation=conversation,
                    content=ai_response,
                    message_type=Message.MESSAGE_TYPE_AI,
                )

                return MessageProcessingResult(
                    user_message_id=user_message.id,
                    ai_message_id=ai_message.id,
                    success=True,
                )

        except Conversation.DoesNotExist:
            error_msg = "Conversation not found."
            if streaming:
                return ConversationService._create_error_stream(error_msg)
            else:
                return MessageProcessingResult(
                    user_message_id=UUID("00000000-0000-0000-0000-000000000000"),
                    ai_message_id=UUID("00000000-0000-0000-0000-000000000000"),
                    success=False,
                    error=error_msg,
                )
        except Exception as e:
            error_msg = str(e)
            if streaming:
                return ConversationService._create_error_stream(error_msg)
            else:
                return MessageProcessingResult(
                    user_message_id=UUID("00000000-0000-0000-0000-000000000000"),
                    ai_message_id=UUID("00000000-0000-0000-0000-000000000000"),
                    success=False,
                    error=error_msg,
                )

    @staticmethod
    def validate_message_request(request: MessageProcessingRequest) -> Optional[str]:
        """
        Centralized validation for message requests.

        Args:
            request: MessageProcessingRequest to validate

        Returns:
            Error message if validation fails, None if valid
        """
        # Validate content
        if not request.content or not request.content.strip():
            return "Message content is required."

        # Validate message type
        if not request.message_type:
            return "Message type is required."

        return None

    @staticmethod
    def authorize_message_request(request: MessageProcessingRequest) -> bool:
        """
        Centralized authorization for message requests.

        Args:
            request: MessageProcessingRequest to authorize

        Returns:
            True if authorized, False otherwise
        """
        from .models import Conversation

        try:
            conversation = Conversation.objects.get(id=request.conversation_id)

            # Check if user owns this conversation
            if conversation.user != request.user:
                return False

            # Check if conversation is not deleted
            if conversation.is_deleted:
                return False

            return True
        except Conversation.DoesNotExist:
            return False

    @staticmethod
    def _process_streaming_response(
        conversation: "Conversation", user_message, content: str, message_type: str
    ) -> Iterator[StreamEvent]:
        """
        Process streaming AI response using enhanced streaming with intelligent retry.

        Args:
            conversation: Conversation object
            user_message: Created user message
            content: Message content
            message_type: Message type

        Yields:
            StreamEvent objects for the streaming response
        """
        from .models import Message
        from llm.services import LLMService, StreamingError

        try:
            # Send user message confirmation
            yield StreamEvent(
                type="user_message",
                timestamp=datetime.now(),
                data={
                    "message_id": str(user_message.id),
                    "content": content,
                    "message_type": message_type,
                },
            )

            # Create AI message placeholder (empty content initially)
            ai_message = Message.objects.create(
                conversation=conversation,
                content="",  # Will be set only on successful completion
                message_type=Message.MESSAGE_TYPE_AI,
            )

            # Send AI message start
            yield StreamEvent(
                type="ai_message_start",
                timestamp=datetime.now(),
                data={"message_id": str(ai_message.id)},
            )

            # Use enhanced streaming with intelligent retry
            for stream_token in LLMService.stream_response_with_completion(
                conversation, content, message_type
            ):
                if stream_token.type == "token":
                    # Stream token to frontend
                    yield StreamEvent(
                        type="ai_token",
                        timestamp=datetime.now(),
                        data={
                            "message_id": str(ai_message.id),
                            "token": stream_token.content,
                        },
                    )
                elif stream_token.type == "complete":
                    # Save complete response to database
                    ai_message.content = stream_token.content
                    ai_message.save()

                    # Signal completion to frontend
                    yield StreamEvent(
                        type="ai_message_complete",
                        timestamp=datetime.now(),
                        data={
                            "message_id": str(ai_message.id),
                            "final_content": stream_token.content,
                        },
                    )
                    return

        except StreamingError as e:
            # Delete the empty AI message since we failed
            ai_message.delete()

            # Send error to frontend
            yield StreamEvent(
                type="error", timestamp=datetime.now(), data={"message": str(e)}
            )
        except Exception as e:
            # Delete the empty AI message since we failed
            ai_message.delete()

            # Send error to frontend
            yield StreamEvent(
                type="error",
                timestamp=datetime.now(),
                data={"message": f"Unexpected error: {str(e)}"},
            )

    @staticmethod
    def _create_error_stream(error_message: str) -> Iterator[StreamEvent]:
        """
        Create an error stream event.

        Args:
            error_message: Error message to send

        Yields:
            Single error StreamEvent
        """
        yield StreamEvent(
            type="error", timestamp=datetime.now(), data={"message": error_message}
        )

    @staticmethod
    def _create_initial_message(section: "Section") -> str:
        """
        Create initial AI message for a section that includes the question.

        Args:
            section: Section object

        Returns:
            String containing the initial message with the section question
        """
        return f"Hello! I'm here to help you with Section {section.order}: {section.title}.\n\n{section.content}\n\nHow can I assist you with this question?"


class SubmissionService:
    """
    Service class for submission-related business logic.

    This service follows a testable-first approach with clear data contracts
    and properly typed methods for easier testing and maintenance.
    """

    # Data Contracts
    @dataclass
    class SubmissionResult:
        submission_id: Optional[UUID] = None
        conversation_id: Optional[UUID] = None
        section_id: Optional[UUID] = None
        is_new: bool = True
        success: bool = True
        error: Optional[str] = None

    @dataclass
    class SubmissionData:
        id: UUID
        conversation_id: UUID
        section_id: UUID
        section_title: str
        student_id: UUID
        student_name: str
        submitted_at: datetime

    @dataclass
    class AutoSubmitResult:
        total_sections: int
        processed_sections: int
        created_submissions: int
        error_count: int
        details: List[Dict[str, Any]]

    @staticmethod
    def submit_section(
        user: User, conversation: "Conversation"
    ) -> "SubmissionService.SubmissionResult":
        """
        Submit a section with the selected conversation.

        Args:
            user: User object submitting the section
            conversation: Conversation object to submit

        Returns:
            SubmissionResult object with operation results
        """
        from .models import Submission

        try:
            with transaction.atomic():
                # Check if submission already exists for this user and section
                existing_submission = Submission.objects.filter(
                    conversation__user=user, conversation__section=conversation.section
                ).first()

                if existing_submission:
                    # Update existing submission
                    is_new = False
                    existing_submission.conversation = conversation
                    existing_submission.save()

                    return SubmissionService.SubmissionResult(
                        submission_id=existing_submission.id,
                        conversation_id=conversation.id,
                        section_id=conversation.section.id,
                        is_new=is_new,
                    )
                else:
                    # Create new submission
                    is_new = True
                    submission = Submission.objects.create(conversation=conversation)

                    return SubmissionService.SubmissionResult(
                        submission_id=submission.id,
                        conversation_id=conversation.id,
                        section_id=conversation.section.id,
                        is_new=is_new,
                    )
        except Exception as e:
            # Return failure result
            return SubmissionService.SubmissionResult(success=False, error=str(e))

    @staticmethod
    def get_submission_data(
        submission_id: UUID,
    ) -> Optional["SubmissionService.SubmissionData"]:
        """
        Get detailed submission data.

        Args:
            submission_id: UUID of the submission to retrieve

        Returns:
            SubmissionData if found, None otherwise
        """
        from .models import Submission

        try:
            # Get submission with optimized query
            submission = Submission.objects.select_related(
                "conversation__user__student_profile", "conversation__section"
            ).get(id=submission_id)

            # Get student's name
            user = submission.conversation.user
            student_name = f"{user.first_name} {user.last_name}"
            if not student_name.strip():
                student_name = user.username

            # Create and return submission data
            return SubmissionService.SubmissionData(
                id=submission.id,
                conversation_id=submission.conversation.id,
                section_id=submission.conversation.section.id,
                section_title=submission.conversation.section.title,
                student_id=submission.conversation.user.student_profile.id,
                student_name=student_name,
                submitted_at=submission.submitted_at,
            )
        except Submission.DoesNotExist:
            return None
        except Exception:
            return None

    @staticmethod
    def auto_submit_overdue_sections() -> "SubmissionService.AutoSubmitResult":
        """
        Automatically submit overdue sections for all students.

        Returns:
            AutoSubmitResult with operation statistics
        """
        from django.utils import timezone
        from homeworks.models import Section

        class _ResultsDict(TypedDict):
            total_sections: int
            processed_sections: int
            created_submissions: int
            error_count: int
            details: list[dict[str, Any]]

        # Initialize results dictionary
        results: _ResultsDict = {
            "total_sections": 0,
            "processed_sections": 0,
            "created_submissions": 0,
            "error_count": 0,
            "details": [],
        }

        try:
            # Get all overdue sections
            overdue_sections = Section.objects.filter(
                homework__due_date__lt=timezone.now()
            ).select_related("homework")

            results["total_sections"] = overdue_sections.count()

            # Process each overdue section
            for section in overdue_sections:
                results["processed_sections"] += 1
                section_result = {
                    "section_id": str(section.id),
                    "homework_id": str(section.homework.id),
                    "students_processed": 0,
                    "submissions_created": 0,
                    "errors": 0,
                }

                # We need to find students who don't have submissions for this section
                # In real implementation, we would need access to a students relation on homework
                # For now, we'll stub this part since it requires more context about how students
                # are associated with homeworks

                # In a real implementation, we'd do something like this:
                # students_without_submissions = Student.objects.filter(
                #     user__in=section.homework.students
                # ).exclude(
                #     user__conversations__submission__conversation__section=section
                # )

                # For now, we'll just return the results structure

                results["details"].append(section_result)

            return SubmissionService.AutoSubmitResult(
                total_sections=results["total_sections"],
                processed_sections=results["processed_sections"],
                created_submissions=results["created_submissions"],
                error_count=results["error_count"],
                details=results["details"],
            )
        except Exception as e:
            # Return error result
            return SubmissionService.AutoSubmitResult(
                total_sections=0,
                processed_sections=0,
                created_submissions=0,
                error_count=1,
                details=[{"error": str(e)}],
            )

    @staticmethod
    def get_student_submissions(
        student: "Student",
    ) -> List["SubmissionService.SubmissionData"]:
        """
        Get all submissions for a student.

        Args:
            student: Student object

        Returns:
            List of SubmissionData for the student's submissions
        """
        from .models import Submission

        try:
            # Get all submissions for this student with optimized query
            submissions = (
                Submission.objects.filter(conversation__user=student.user)
                .select_related("conversation__section", "conversation__user")
                .order_by("-submitted_at")
            )

            # Create SubmissionData objects for each submission
            submission_data_list: List[SubmissionService.SubmissionData] = []
            for submission in submissions:
                # Get student's name
                user = submission.conversation.user
                student_name = f"{user.first_name} {user.last_name}"
                if not student_name.strip():
                    student_name = user.username

                submission_data = SubmissionService.SubmissionData(
                    id=submission.id,
                    conversation_id=submission.conversation.id,
                    section_id=submission.conversation.section.id,
                    section_title=submission.conversation.section.title,
                    student_id=student.id,
                    student_name=student_name,
                    submitted_at=submission.submitted_at,
                )
                submission_data_list.append(submission_data)

            return submission_data_list
        except Exception:
            return []

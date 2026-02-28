"""
Views for the conversations app.

This module provides views for managing conversations between users and AI tutors,
following the testable-first architecture with typed data contracts.
"""

from dataclasses import dataclass
from typing import Dict, Optional, List
from uuid import UUID
from datetime import datetime

from django.views import View
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    Http404,
    StreamingHttpResponse,
    JsonResponse,
)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from opentelemetry import trace
from django.views.decorators.csrf import csrf_exempt
import json
import logging

from llteacher.tracing import record_exception

logger = logging.getLogger(__name__)

from homeworks.models import Section
from .models import Conversation, PasteEvent, RapidTextGrowthEvent
from .services import (
    ConversationService,
    SubmissionService,
    MessageProcessingRequest,
    StreamEvent,
)


@dataclass
class ConversationStartFormData:
    """Data structure for the conversation start form view."""

    section_id: UUID
    section_title: str
    errors: Optional[Dict[str, str]] = None


@dataclass
class ConversationStartViewData:
    """Data structure for rendering the conversation start view."""

    section_id: UUID
    section_title: str
    homework_id: UUID
    homework_title: str


@dataclass
class MessageViewData:
    """Data structure for message display in conversation detail view."""

    id: UUID
    content: str
    message_type: str
    timestamp: datetime
    is_from_student: bool
    is_from_ai: bool
    is_system_message: bool
    css_class: str  # For styling


@dataclass
class PasteEventViewData:
    """Data structure for paste event display."""

    id: UUID
    pasted_content: str
    word_count: int
    content_length: int
    timestamp: datetime


@dataclass
class RapidTextGrowthEventViewData:
    """Data structure for rapid text growth event display."""

    id: UUID
    added_text: str
    timestamp: datetime


@dataclass
class ConversationDetailData:
    """Data structure for the conversation detail view."""

    id: UUID
    section_id: UUID
    section_title: str
    homework_id: UUID
    homework_title: str
    messages: List[MessageViewData]
    can_submit: bool
    is_teacher_test: bool
    paste_events: List[PasteEventViewData] = None
    rapid_text_growth_events: List[RapidTextGrowthEventViewData] = None
    user_id: UUID = None


@dataclass
class MessageSendFormData:
    """Data structure for the message send form."""

    conversation_id: UUID
    content: str
    message_type: str = "student"
    errors: Optional[Dict[str, str]] = None


@dataclass
class MessageSendResult:
    """Result of a message send operation."""

    success: bool
    conversation_id: UUID
    error: Optional[str] = None


class MessageProcessingMixin:
    """Mixin providing common message processing functionality."""

    def validate_and_authorize_request(
        self, request: HttpRequest, conversation_id: UUID
    ) -> tuple[MessageProcessingRequest | None, str | None]:
        """
        Common validation and authorization logic.

        Args:
            request: HTTP request object
            conversation_id: UUID of the conversation

        Returns:
            (MessageProcessingRequest, None) if valid, (None, error_message) if invalid
        """
        # Parse message content
        content, message_type = self.parse_message_content(request)
        if not content:
            return None, "Message content is required."

        # Create processing request
        processing_request = MessageProcessingRequest(
            conversation_id=conversation_id,
            user=request.user,
            content=content,
            message_type=message_type,
        )

        # Validate request
        validation_error = ConversationService.validate_message_request(
            processing_request
        )
        if validation_error:
            return None, validation_error

        # Authorize request
        if not ConversationService.authorize_message_request(processing_request):
            return (
                None,
                "You don't have permission to send messages in this conversation.",
            )

        return processing_request, None

    def parse_message_content(self, request: HttpRequest) -> tuple[str | None, str]:
        """
        Parse message content from either form data or JSON.

        Args:
            request: HTTP request object

        Returns:
            (content, message_type) if valid, (None, message_type) if invalid
        """
        if request.content_type == "application/json":
            # Parse JSON data (for streaming requests)
            try:
                data = json.loads(request.body)
                content = data.get("content", "").strip()
                message_type = data.get("message_type", "student")
                return content if content else None, message_type
            except json.JSONDecodeError:
                return None, "student"
        else:
            # Parse form data (for traditional POST requests)
            content = request.POST.get("content", "").strip()
            message_type = request.POST.get("message_type", "student").strip()
            if not message_type:
                message_type = "student"
            return content if content else None, message_type


class ConversationStartView(View):
    """View for starting a new conversation on a section."""

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: HttpRequest, section_id: UUID) -> HttpResponse:
        """Handle GET requests to display the conversation start form."""
        # Get the section (404 if not found)
        section = get_object_or_404(
            Section.objects.select_related("homework"), id=section_id
        )

        # Create view data
        view_data = self._get_view_data(section)

        # Render the form
        return render(request, "conversations/start.html", {"view_data": view_data})

    def post(self, request: HttpRequest, section_id: UUID) -> HttpResponse:
        """Handle POST requests to start a new conversation."""
        # Get the section (404 if not found)
        section = get_object_or_404(
            Section.objects.select_related("homework"), id=section_id
        )

        # Start conversation using service
        result = ConversationService.start_conversation(request.user, section)

        if result.success:
            # Redirect to conversation detail
            messages.success(request, "Conversation started successfully.")
            return redirect(
                "conversations:detail", conversation_id=result.conversation_id
            )
        else:
            # Show error message
            messages.error(request, result.error or "Failed to start conversation.")

            # Create view data
            view_data = self._get_view_data(section)

            # Render the form with errors
            return render(
                request,
                "conversations/start.html",
                {"view_data": view_data, "error": result.error},
            )

    def _get_view_data(self, section: Section) -> ConversationStartViewData:
        """Prepare data for rendering the conversation start form."""
        return ConversationStartViewData(
            section_id=section.id,
            section_title=section.title,
            homework_id=section.homework.id,
            homework_title=section.homework.title,
        )


class ConversationDetailView(View):
    """View for viewing an existing conversation."""

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)

    def get(self, request: HttpRequest, conversation_id: UUID) -> HttpResponse:
        """Handle GET requests to display the conversation."""
        # Get conversation data using service
        conversation_data = ConversationService.get_conversation_data(
            conversation_id, request.user
        )

        # Check if conversation exists
        if not conversation_data:
            messages.error(request, "Conversation not found.")
            # Raise 404 instead of trying to render 404.html directly
            raise Http404("Conversation not found.")

        # Check access permissions
        if not self._check_conversation_access(request.user, conversation_data):
            return HttpResponseForbidden(
                "You don't have permission to view this conversation."
            )

        # Process message styling for display
        conversation_data = self._process_message_styling(conversation_data)

        # Create combined timeline for teacher view
        is_teacher_viewing = (
            hasattr(request.user, "teacher_profile")
            and request.user.id != conversation_data.user_id
        )
        timeline = self._create_timeline(conversation_data, is_teacher_viewing)

        # Render the conversation detail template
        return render(
            request,
            "conversations/detail.html",
            {
                "conversation_data": conversation_data,
                "timeline": timeline,
                "is_teacher_viewing": is_teacher_viewing,
            },
        )

    def _check_conversation_access(self, user, conversation_data):
        """
        Check if the user has access to view this conversation.

        Args:
            user: The user trying to access the conversation
            conversation_data: ConversationData object

        Returns:
            Boolean indicating if access is allowed
        """
        # User owns the conversation
        if str(user.id) == str(conversation_data.user_id):
            return True

        # Teacher can view student conversations (but not other teachers)
        has_teacher_profile = hasattr(user, "teacher_profile")
        if has_teacher_profile and not conversation_data.is_teacher_test:
            return True

        return False

    def _process_message_styling(self, conversation_data):
        """
        Process messages to add CSS styling based on message types.

        Args:
            conversation_data: ConversationData object

        Returns:
            ConversationData with updated message styling
        """
        if conversation_data.messages:
            for message in conversation_data.messages:
                # Assign CSS classes based on message type
                if message.is_from_student:
                    message.css_class = "message-chat"
                elif message.is_from_ai:
                    message.css_class = "message-ai"
                elif message.is_system_message:
                    message.css_class = "message-system"
                else:
                    message.css_class = "message-default"

        return conversation_data

    def _create_timeline(self, conversation_data, is_teacher_viewing):
        """
        Create a combined timeline of messages, paste events, and rapid text growth events.

        Args:
            conversation_data: ConversationData object
            is_teacher_viewing: Boolean indicating if teacher is viewing

        Returns:
            List of timeline items (messages, paste events, and rapid text growth events) sorted by timestamp
        """
        timeline = []

        # Add all messages with type marker
        if conversation_data.messages:
            for message in conversation_data.messages:
                timeline.append({
                    'type': 'message',
                    'data': message,
                    'timestamp': message.timestamp
                })

        # Add paste events if teacher is viewing
        if is_teacher_viewing and conversation_data.paste_events:
            for paste_event in conversation_data.paste_events:
                timeline.append({
                    'type': 'paste_event',
                    'data': paste_event,
                    'timestamp': paste_event.timestamp
                })

        # Add rapid text growth events if teacher is viewing
        if is_teacher_viewing and conversation_data.rapid_text_growth_events:
            for rapid_text_growth_event in conversation_data.rapid_text_growth_events:
                timeline.append({
                    'type': 'rapid_text_growth_event',
                    'data': rapid_text_growth_event,
                    'timestamp': rapid_text_growth_event.timestamp
                })

        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])

        return timeline


class MessageSendView(MessageProcessingMixin, View):
    """View for sending messages in a conversation."""

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)

    def post(self, request: HttpRequest, conversation_id: UUID) -> HttpResponse:
        """Handle POST requests to send a message."""
        # Use unified validation and authorization
        message_request, error = self.validate_and_authorize_request(
            request, conversation_id
        )
        if error or message_request is None:
            messages.error(request, error or "Invalid request")
            return self._render_error_form(
                request, conversation_id, error or "Invalid request"
            )

        # Use unified service for non-streaming processing
        result = ConversationService.process_message(message_request, streaming=False)

        # Handle the result (should be MessageProcessingResult when streaming=False)
        if hasattr(result, "success") and result.success:
            # Redirect to conversation detail
            messages.success(request, "Message sent successfully.")
            return redirect("conversations:detail", conversation_id=conversation_id)
        else:
            # Show error message
            error_msg = getattr(result, "error", None) or "Failed to send message."
            messages.error(request, error_msg)
            return self._render_error_form(request, conversation_id, error_msg)

    def _render_error_form(
        self, request: HttpRequest, conversation_id: UUID, error: str
    ) -> HttpResponse:
        """
        Render the message form with error information.

        Args:
            request: HTTP request object
            conversation_id: UUID of the conversation
            error: Error message to display

        Returns:
            HttpResponse with error form
        """
        # Create form data with error
        content, message_type = self.parse_message_content(request)
        form_data = MessageSendFormData(
            conversation_id=conversation_id,
            content=content or "",
            message_type=message_type,
            errors={"service": error},
        )

        return render(
            request,
            "conversations/message_form.html",
            {"form_data": form_data, "conversation_id": conversation_id},
        )


# Simple API Views for Real-time Chat
class ConversationStreamView(MessageProcessingMixin, View):
    """Server-Sent Events view for streaming LLM responses."""

    @method_decorator(login_required)
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(
        self, request: HttpRequest, conversation_id: UUID
    ) -> StreamingHttpResponse:
        """Stream LLM response via Server-Sent Events."""

        def stream_llm_response():
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("SSE stream_llm_response") as span:
                try:
                    span.set_attribute("conversation_id", str(conversation_id))

                    # Use unified validation and authorization
                    message_request, error = self.validate_and_authorize_request(
                        request, conversation_id
                    )
                    if error or message_request is None:
                        yield self._format_sse_error(error or "Invalid request")
                        return

                    # Use unified service for streaming processing
                    event_stream = ConversationService.process_message(
                        message_request, streaming=True
                    )

                    # Convert StreamEvent objects to SSE format
                    for event in event_stream:
                        yield self._format_sse_event(event)

                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    yield self._format_sse_error(str(e))

        response = StreamingHttpResponse(
            stream_llm_response(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["Access-Control-Allow-Origin"] = "*"
        return response

    def _format_sse_event(self, event: StreamEvent) -> bytes:
        """
        Format a StreamEvent as Server-Sent Event data.

        Args:
            event: StreamEvent to format

        Returns:
            Formatted SSE data as bytes
        """
        sse_data = {
            "type": event.type,
            "timestamp": event.timestamp.isoformat(),
            **event.data,
        }
        return f"data: {json.dumps(sse_data)}\n\n".encode("utf-8")

    def _format_sse_error(self, error_message: str) -> bytes:
        """
        Format an error message as Server-Sent Event data.

        Args:
            error_message: Error message to format

        Returns:
            Formatted SSE error data as bytes
        """
        sse_data = {"type": "error", "message": error_message}
        return f"data: {json.dumps(sse_data)}\n\n".encode("utf-8")


class ConversationSubmitView(View):
    """View for directly submitting a conversation."""

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)

    def post(self, request: HttpRequest, conversation_id: UUID) -> HttpResponse:
        """Handle POST requests to submit the current conversation."""
        # Get the conversation and check permissions
        conversation = get_object_or_404(Conversation, id=conversation_id)

        # Check if user owns this conversation
        if conversation.user != request.user:
            return HttpResponseForbidden("You can only submit your own conversations.")

        # Check if user is a student
        if not hasattr(request.user, "student_profile"):
            return HttpResponseForbidden("Only students can submit conversations.")

        # Check if conversation is not deleted
        if conversation.is_deleted:
            messages.error(request, "Cannot submit a deleted conversation.")
            return redirect("conversations:detail", conversation_id=conversation_id)

        # Submit the conversation using service
        result = SubmissionService.submit_section(request.user, conversation)

        if result.success:
            # Redirect to section detail with success message
            messages.success(
                request,
                f"Conversation submitted successfully for section '{conversation.section.title}'."
                + (" (Updated existing submission)" if not result.is_new else ""),
            )
            return redirect(
                "homeworks:section_detail",
                homework_id=conversation.section.homework.id,
                section_id=conversation.section.id,
            )
        else:
            # Show error message and redirect back to conversation
            messages.error(request, result.error or "Failed to submit conversation.")
            return redirect("conversations:detail", conversation_id=conversation_id)


class ConversationDeleteAndRestartView(View):
    """View for deleting a conversation and starting a new one."""

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        """Ensure user is logged in before accessing view."""
        return super().dispatch(*args, **kwargs)

    def post(self, request: HttpRequest, conversation_id: UUID) -> HttpResponse:
        """Handle POST requests to delete conversation and start new one."""
        # Get the conversation and check permissions
        conversation = get_object_or_404(Conversation, id=conversation_id)

        # Check if user owns this conversation
        if conversation.user != request.user:
            return HttpResponseForbidden("You can only delete your own conversations.")

        # Store section info before deleting
        section = conversation.section

        # Delete the conversation (soft delete)
        conversation.soft_delete()

        # Start a new conversation for the same section
        result = ConversationService.start_conversation(request.user, section)

        if result.success:
            messages.success(
                request, "Previous conversation deleted and new one started."
            )
            return redirect(
                "conversations:detail", conversation_id=result.conversation_id
            )
        else:
            messages.error(request, f"Error starting new conversation: {result.error}")
            return redirect("homeworks:detail", homework_id=section.homework.id)


class PasteLogView(View):
    """API view for logging paste detection events."""

    @method_decorator(login_required)
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request: HttpRequest, conversation_id: UUID) -> JsonResponse:
        """Handle POST requests to log paste events."""
        try:
            # Parse the JSON request first
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "Invalid JSON data."}, status=400
            )

        # Get the conversation and check permissions
        # get_object_or_404 will raise Http404 which Django handles automatically
        conversation = get_object_or_404(Conversation, id=conversation_id)

        # Check if user owns this conversation
        if conversation.user != request.user:
            return JsonResponse(
                {"error": "You can only log paste events in your own conversations."},
                status=403,
            )

        try:
            pasted_content = data.get("pasted_content", "")
            word_count = data.get("word_count", 0)
            content_length = data.get("content_length", 0)

            # Get the last message in the conversation
            last_message = conversation.messages.order_by("-timestamp").first()

            # Create the paste event
            paste_event = PasteEvent.objects.create(
                last_message_before_paste=last_message,
                pasted_content=pasted_content,
                word_count=word_count,
                content_length=content_length,
            )

            return JsonResponse(
                {
                    "success": True,
                    "paste_event_id": str(paste_event.id),
                    "message": "Paste event logged successfully.",
                },
                status=201,
            )

        except Exception as e:
            logger.exception("Failed to log paste event")
            record_exception(e)
            return JsonResponse(
                {"error": f"Failed to log paste event: {str(e)}"}, status=500
            )


class RapidTextGrowthLogView(View):
    """API view for logging rapid text growth detection events."""

    @method_decorator(login_required)
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request: HttpRequest, conversation_id: UUID) -> JsonResponse:
        """Handle POST requests to log rapid text growth events."""
        try:
            # Parse the JSON request first
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "Invalid JSON data."}, status=400
            )

        # Get the conversation and check permissions
        conversation = get_object_or_404(Conversation, id=conversation_id)

        # Check if user owns this conversation
        if conversation.user != request.user:
            return JsonResponse(
                {"error": "You can only log rapid text growth events in your own conversations."},
                status=403,
            )

        try:
            added_text = data.get("added_text", "")

            # Get the last message in the conversation
            last_message = conversation.messages.order_by("-timestamp").first()

            # Create the rapid text growth event
            RapidTextGrowthEvent.objects.create(
                last_message_before_event=last_message,
                added_text=added_text,
            )

            return JsonResponse({}, status=201)

        except Exception as e:
            logger.exception("Failed to log rapid text growth event")
            record_exception(e)
            return JsonResponse(
                {"error": f"Failed to log rapid text growth event: {str(e)}"}, status=500
            )

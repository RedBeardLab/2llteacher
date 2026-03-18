"""
LLM Service

This module provides services for configuring and interacting with language model APIs.
Following a testable-first approach with typed data contracts.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List, TYPE_CHECKING, Iterator
from uuid import UUID
import uuid
import logging
import time
import json
from enum import StrEnum

# Handle imports for type checking
if TYPE_CHECKING:
    from conversations.models import Conversation
    from .models import LLMConfig

from django.conf import settings
import httpx
from openai import OpenAI, APITimeoutError, APIConnectionError
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from llteacher.tracing import traced, set_span_attributes, record_exception


class StreamTokenType(StrEnum):
    """Types of streaming tokens."""

    TOKEN = "token"
    COMPLETE = "complete"


class FinishReason(StrEnum):
    """OpenAI finish reasons."""

    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    FUNCTION_CALL = "function_call"
    TOOL_CALLS = "tool_calls"


class StreamingError(Exception):
    """Custom exception for streaming errors."""

    pass


logger = logging.getLogger(__name__)


# Data Contracts
@dataclass
class LLMConfigData:
    id: UUID
    name: str
    model_name: str
    api_key: str
    base_prompt: str
    temperature: float
    max_completion_tokens: int
    is_default: bool
    is_active: bool

    @classmethod
    def from_model(cls, llm_config: "LLMConfig") -> "LLMConfigData":
        """
        Create LLMConfigData from LLMConfig model instance.

        Args:
            llm_config: LLMConfig model instance

        Returns:
            LLMConfigData with all fields copied from model
        """
        if not llm_config.api_key.isascii():
            err = ValueError(
                f"LLM config '{llm_config.name}' (id={llm_config.id}) has non-ASCII api_key — fields may be swapped with base_prompt"
            )
            logger.error(str(err))
            record_exception(err)

        return cls(
            id=llm_config.id,
            name=llm_config.name,
            model_name=llm_config.model_name,
            api_key=llm_config.api_key,
            base_prompt=llm_config.base_prompt,
            temperature=llm_config.temperature,
            max_completion_tokens=llm_config.max_completion_tokens,
            is_default=llm_config.is_default,
            is_active=llm_config.is_active,
        )


@dataclass
class LLMResponseResult:
    response_text: str
    tokens_used: int
    success: bool = True
    error: Optional[str] = None


@dataclass
class LLMConfigCreateData:
    name: str
    model_name: str
    api_key: str
    base_prompt: str
    temperature: float = 0.7
    max_completion_tokens: int = 1000
    is_default: bool = False
    is_active: bool = True


@dataclass
class LLMConfigCreateResult:
    config_id: Optional[UUID] = None
    success: bool = True
    error: Optional[str] = None


@dataclass
class LLMConfigUpdateResult:
    success: bool = True
    error: Optional[str] = None


@dataclass
class ConversationContext:
    section_title: str
    section_content: str
    homework_title: str
    messages: list[
        dict[str, str]
    ]  # List of {"role": "user/assistant", "content": "..."}
    current_message: str
    message_type: str


@dataclass
class FunctionDefinition:
    """Definition of a function that can be called by the LLM."""

    name: str
    description: str
    parameters: Dict[str, Any]  # OpenAI format parameters object

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class FunctionCall:
    """Represents a function call requested by the LLM."""

    id: str  # Tool call ID from OpenAI
    name: str
    arguments: Dict[str, Any]  # Parsed JSON arguments


@dataclass
class StreamToken:
    """Token object for streaming with completion signal and function calls."""

    type: StreamTokenType
    content: str
    finish_reason: FinishReason | None = None
    function_calls: List[FunctionCall] | None = None

    @property
    def has_function_calls(self) -> bool:
        """Check if token contains function calls."""
        return self.function_calls is not None and len(self.function_calls) > 0


@dataclass
class LLMResponseWithTools:
    """Response that may include function calls."""

    response_text: str | None = None
    function_calls: List[FunctionCall] | None = None
    tokens_used: int = 0
    success: bool = True
    error: str | None = None
    finish_reason: FinishReason | None = None

    @property
    def has_function_calls(self) -> bool:
        """Check if response contains function calls."""
        return self.function_calls is not None and len(self.function_calls) > 0


class LLMService:
    """
    Service class for LLM-related business logic.

    This service follows a testable-first approach with clear data contracts
    and properly typed methods for easier testing and maintenance.
    """

    @staticmethod
    @traced
    def get_stopping_rule_function() -> FunctionDefinition:
        """
        Get the stopping rule function definition.

        Returns:
            FunctionDefinition for mark_section_complete
        """
        return FunctionDefinition(
            name="mark_section_complete",
            description=(
                "Call this function when the student has demonstrated some understanding "
                "of the section's key concepts and provided an reasonable answer to the main question. "
                "Students MUST NOT be blocked, and they are allowed to keep working toward the problem. "
                "Our goal is to UNBLOCK them as soon as possible and avoid them being frustrated."
                "DO NOT be pedantic. If a correct answer is provided call this function immediately. Even if you think the student doesn't master the concept yet."
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

    @staticmethod
    @traced
    def get_response(
        conversation: "Conversation",
        content: str,
        message_type: str,
        available_functions: List[FunctionDefinition],
    ) -> LLMResponseWithTools:
        """
        Generate an AI response based on conversation context.

        Args:
            conversation: Conversation object
            content: Latest message content
            message_type: Type of message
            available_functions: List of functions the LLM can call

        Returns:
            LLMResponseWithTools containing response text and/or function calls
        """
        try:
            # Get LLM config - first from the homework, then fallback to default
            llm_config = None
            if (
                hasattr(conversation.section, "homework")
                and conversation.section.homework.llm_config
            ):
                llm_config = LLMConfigData.from_model(
                    conversation.section.homework.llm_config
                )

            # If no config on homework, get default config
            if not llm_config:
                llm_config = LLMService.get_default_config()
                if not llm_config:
                    return LLMResponseWithTools(
                        success=False,
                        error="No valid LLM configuration available",
                    )

            # Build conversation context
            context = LLMService._build_conversation_context(
                conversation, content, message_type
            )

            # Generate response using OpenAI client with tools
            return LLMService._generate_openai_response(
                llm_config, context, available_functions
            )

        except Exception as e:
            error_id = uuid.uuid4()
            logger.error(f"Error generating AI response [ID: {error_id}]: {str(e)}")
            record_exception(e)
            return LLMResponseWithTools(
                success=False,
                error=f"Technical issue [ID: {error_id}]: {str(e)}",
            )

    @staticmethod
    @traced
    def _generate_openai_response(
        llm_config: LLMConfigData,
        context: ConversationContext,
        available_functions: List[FunctionDefinition],
    ) -> LLMResponseWithTools:
        """
        Generate response using OpenAI client with function calling support.

        Args:
            llm_config: LLM configuration data
            context: Conversation context data
            available_functions: List of functions the LLM can call

        Returns:
            LLMResponseWithTools with response text and/or function calls
        """
        start_time = time.perf_counter()

        try:
            # Initialize OpenAI client with OpenRouter endpoint
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=llm_config.api_key,
                timeout=httpx.Timeout(
                    connect=settings.LLM_API_CONNECTION_TIMEOUT,
                    read=settings.LLM_API_TIMEOUT,
                    write=10.0,
                    pool=5.0,
                ),
            )

            # Build messages for OpenAI API with proper typing
            # System message includes base prompt and section context
            system_message = LLMService._build_system_message(llm_config, context)
            messages = [{"role": "system", "content": system_message}]

            # Add conversation history (plain text messages)
            for msg in context.messages:
                messages.append({"role": msg["role"], "content": msg["content"]})

            # Add current message (plain text)
            messages.append({"role": "user", "content": context.current_message})

            # Record time after query preparation
            query_prepared_time = time.perf_counter()
            query_preparation_ms = int((query_prepared_time - start_time) * 1000)

            # Prepare tools parameter
            tools = [func.to_openai_format() for func in available_functions]

            # Log LLM request details
            request_attrs = {
                "event_type": "llm_request",
                "model_name": llm_config.model_name,
                "response_mode": "non_streaming",
                "messages_count": len(messages),
                "tools_count": len(tools),
                "tools": tools,
                "temperature": llm_config.temperature,
                "max_completion_tokens": llm_config.max_completion_tokens,
                "section_title": context.section_title,
                "homework_title": context.homework_title,
            }
            logger.info("LLM API request", extra=request_attrs)
            set_span_attributes(request_attrs)

            # Make API call with tools
            response = client.chat.completions.create(
                model=llm_config.model_name,
                messages=messages,  # type: ignore
                temperature=llm_config.temperature,
                max_completion_tokens=llm_config.max_completion_tokens,
                tools=tools,  # type: ignore
            )

            # Calculate total response time
            end_time = time.perf_counter()
            total_response_time_ms = int((end_time - start_time) * 1000)
            api_response_time_ms = int((end_time - query_prepared_time) * 1000)

            # Extract response
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                response_text = choice.message.content or ""
                tokens_used = response.usage.total_tokens if response.usage else 0

                # Extract function calls if present
                function_calls = []
                if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                    for tool_call in choice.message.tool_calls:
                        if not hasattr(tool_call, "function"):
                            continue
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                            function_calls.append(
                                FunctionCall(
                                    id=tool_call.id,
                                    name=tool_call.function.name,
                                    arguments=arguments,
                                )
                            )
                        except json.JSONDecodeError as e:
                            logger.error(
                                f"Failed to parse function arguments: {tool_call.function.arguments}, error: {e}"
                            )

                # Determine finish reason
                finish_reason = None
                if choice.finish_reason:
                    try:
                        finish_reason = FinishReason(choice.finish_reason)
                    except ValueError:
                        logger.warning(
                            f"Unknown finish reason from OpenAI: {choice.finish_reason}"
                        )

                # Log response timing
                response_attrs = {
                    "event_type": "llm_response_timing",
                    "model_name": llm_config.model_name,
                    "response_mode": "non_streaming",
                    "query_preparation_ms": query_preparation_ms,
                    "api_response_time_ms": api_response_time_ms,
                    "total_response_time_ms": total_response_time_ms,
                    "token_count": tokens_used,
                    "success": True,
                    "has_function_calls": len(function_calls) > 0,
                    "function_calls_count": len(function_calls),
                    "finish_reason": finish_reason.value if finish_reason else None,
                    "section_title": context.section_title,
                    "homework_title": context.homework_title,
                    "message_type": context.message_type,
                }
                logger.info("LLM response timing", extra=response_attrs)
                set_span_attributes(response_attrs)

                return LLMResponseWithTools(
                    response_text=response_text if response_text else None,
                    function_calls=function_calls,
                    tokens_used=tokens_used,
                    success=True,
                    finish_reason=finish_reason,
                )
            else:
                # Log failed response timing
                error_attrs = {
                    "event_type": "llm_response_timing",
                    "model_name": llm_config.model_name,
                    "response_mode": "non_streaming",
                    "query_preparation_ms": query_preparation_ms,
                    "api_response_time_ms": api_response_time_ms,
                    "total_response_time_ms": total_response_time_ms,
                    "token_count": 0,
                    "success": False,
                    "error": "No response generated from OpenAI API",
                    "section_title": context.section_title,
                    "homework_title": context.homework_title,
                    "message_type": context.message_type,
                }
                logger.info("LLM response timing", extra=error_attrs)
                set_span_attributes(error_attrs)

                return LLMResponseWithTools(
                    tokens_used=0,
                    success=False,
                    error="No response generated from OpenAI API",
                )

        except Exception as e:
            # Calculate response time even for errors
            end_time = time.perf_counter()
            total_response_time_ms = int((end_time - start_time) * 1000)

            # Log error timing
            exc_attrs = {
                "event_type": "llm_response_timing",
                "model_name": llm_config.model_name,
                "response_mode": "non_streaming",
                "total_response_time_ms": total_response_time_ms,
                "token_count": 0,
                "success": False,
                "error": str(e),
                "section_title": context.section_title,
                "homework_title": context.homework_title,
                "message_type": context.message_type,
            }
            logger.info("LLM response timing", extra=exc_attrs)
            set_span_attributes(exc_attrs)

            logger.error(f"OpenAI API error: {str(e)}")
            return LLMResponseWithTools(tokens_used=0, success=False, error=str(e))

    @staticmethod
    def _is_meaningful_chunk(content: str) -> bool:
        """
        Validate that chunk contains meaningful content.

        Args:
            content: Chunk content to validate

        Returns:
            True if chunk contains meaningful content, False otherwise
        """
        if not content:
            return False

        # Strip whitespace and check if anything meaningful remains
        stripped = content.strip()
        return len(stripped) > 0 and not stripped.isspace()

    @staticmethod
    @traced
    def stream_response_with_completion(
        conversation: "Conversation",
        content: str,
        message_type: str,
        available_functions: List[FunctionDefinition],
    ) -> Iterator[StreamToken]:
        """
        Enhanced streaming that yields tokens and signals completion with final response.
        Handles retries transparently with finish reason detection and meaningful content validation.
        Supports function calling.

        Args:
            conversation: Conversation object
            content: Latest message content
            message_type: Type of message
            available_functions: List of functions the LLM can call

        Yields:
            StreamToken objects for tokens and completion signal (may include function calls)

        Raises:
            StreamingError: When all retry attempts fail
        """
        try:
            # Get LLM config - first from the homework, then fallback to default
            llm_config = None
            if (
                hasattr(conversation.section, "homework")
                and conversation.section.homework.llm_config
            ):
                llm_config = LLMConfigData.from_model(
                    conversation.section.homework.llm_config
                )

            # If no config on homework, get default config
            if not llm_config:
                llm_config = LLMService.get_default_config()
                if not llm_config:
                    raise StreamingError("No valid LLM configuration available")

            # Build conversation context
            context = LLMService._build_conversation_context(
                conversation, content, message_type
            )

            # Generate streaming response with intelligent retry
            yield from LLMService._stream_with_intelligent_retry(
                llm_config, context, available_functions
            )

        except Exception as e:
            error_id = uuid.uuid4()
            logger.error(
                f"Error in stream_response_with_completion [ID: {error_id}]: {str(e)}"
            )
            raise StreamingError(f"Streaming failed: {str(e)}")

    @staticmethod
    @traced
    def _stream_with_intelligent_retry(
        llm_config: LLMConfigData,
        context: ConversationContext,
        available_functions: List[FunctionDefinition],
        max_retries: int = 3,
    ) -> Iterator[StreamToken]:
        """
        Stream with intelligent retry logic based on finish reasons and content validation.
        Supports function calling.

        Args:
            llm_config: LLM configuration data
            context: Conversation context data
            available_functions: List of functions the LLM can call
            max_retries: Maximum number of retry attempts

        Yields:
            StreamToken objects for tokens and completion (may include function calls)

        Raises:
            StreamingError: When all retries fail or length limit hit
        """
        retry_history = []  # Track (attempt, reason) for monitoring
        for attempt in range(max_retries):
            try:
                accumulated_response = ""
                chunk_count = 0
                meaningful_chunks = 0
                accumulated_function_calls = []

                # Stream with finish reason detection and function calls
                for (
                    token,
                    function_calls,
                    finish_reason,
                ) in LLMService._stream_with_finish_reason_detection(
                    llm_config, context, available_functions
                ):
                    if token:  # Only process non-empty tokens
                        chunk_count += 1
                        accumulated_response += token

                        # Check if token is meaningful
                        if LLMService._is_meaningful_chunk(token):
                            meaningful_chunks += 1
                            yield StreamToken(type=StreamTokenType.TOKEN, content=token)

                    # Accumulate function calls
                    if function_calls:
                        accumulated_function_calls.extend(function_calls)

                # Validate response quality before checking finish reason
                response_length = len(accumulated_response)

                # For tool calls, we don't require meaningful content
                has_tool_calls = len(accumulated_function_calls) > 0

                # Check if we got sufficient meaningful content OR tool calls
                if not has_tool_calls and (
                    meaningful_chunks == 0 or response_length < 3
                ):
                    logger.warning(
                        f"Insufficient content on attempt {attempt + 1}/{max_retries} "
                        f"(chunks: {chunk_count}, meaningful: {meaningful_chunks}, length: {response_length})"
                    )
                    retry_history.append((attempt + 1, "insufficient_content"))
                    # Treat as interrupted stream, continue to retry
                    continue

                # Check completion reason
                if finish_reason == FinishReason.STOP:
                    # Success! Signal completion with full response
                    # Add retry monitoring context
                    if retry_history:
                        retry_reasons = [reason for _, reason in retry_history]
                        set_span_attributes(
                            {
                                "total_attempts": attempt + 1,
                                "had_retries": True,
                                "retry_reasons": retry_reasons,
                            }
                        )
                    else:
                        set_span_attributes(
                            {
                                "total_attempts": 1,
                                "had_retries": False,
                            }
                        )
                    yield StreamToken(
                        type=StreamTokenType.COMPLETE,
                        content=accumulated_response,
                        finish_reason=finish_reason,
                        function_calls=accumulated_function_calls
                        if accumulated_function_calls
                        else None,
                    )
                    return
                elif finish_reason == FinishReason.TOOL_CALLS:
                    # LLM wants to call functions
                    # Add retry monitoring context
                    if retry_history:
                        retry_reasons = [reason for _, reason in retry_history]
                        set_span_attributes(
                            {
                                "total_attempts": attempt + 1,
                                "had_retries": True,
                                "retry_reasons": retry_reasons,
                            }
                        )
                    else:
                        set_span_attributes(
                            {
                                "total_attempts": 1,
                                "had_retries": False,
                            }
                        )
                    yield StreamToken(
                        type=StreamTokenType.COMPLETE,
                        content=accumulated_response if accumulated_response else "",
                        finish_reason=finish_reason,
                        function_calls=accumulated_function_calls
                        if accumulated_function_calls
                        else None,
                    )
                    return
                elif finish_reason == FinishReason.LENGTH:
                    # Hit token limit - this is an error condition
                    raise StreamingError("Response exceeded maximum length limit")
                elif finish_reason == FinishReason.CONTENT_FILTER:
                    # Content policy violation - don't retry
                    raise StreamingError("Response blocked by content filter")
                elif finish_reason is None:
                    # Stream was interrupted - retry
                    logger.warning(
                        f"Stream interrupted on attempt {attempt + 1}/{max_retries}, retrying..."
                    )
                    retry_history.append((attempt + 1, "interrupted_stream"))
                    continue
                else:
                    # Unknown finish reason - treat as error and retry
                    logger.warning(
                        f"Unknown finish reason: {finish_reason}, retrying..."
                    )
                    continue

            except StreamingError:
                # Re-raise streaming errors (don't retry for LENGTH, CONTENT_FILTER)
                raise
            except (APITimeoutError, APIConnectionError) as e:
                # Log timeout/connection errors with retry context
                error_type = (
                    "timeout" if isinstance(e, APITimeoutError) else "connection"
                )
                retry_history.append((attempt + 1, error_type))

                logger.warning(
                    f"API {error_type} error on attempt {attempt + 1}/{max_retries}: {str(e)}",
                    extra={
                        "event_type": "llm_retry",
                        "retry_attempt": attempt + 1,
                        "max_retries": max_retries,
                        "retry_reason": error_type,
                        "error_message": str(e),
                        "model_name": llm_config.model_name,
                        "section_title": context.section_title,
                        "homework_title": context.homework_title,
                        "response_mode": "streaming",
                    },
                )
                set_span_attributes(
                    {
                        "retry_attempt": attempt + 1,
                        "retry_reason": error_type,
                    }
                )
                record_exception(e)

                if attempt == max_retries - 1:
                    raise StreamingError(
                        f"LLM API {error_type} after {max_retries} attempts: {str(e)}"
                    )
                continue

            except Exception as e:
                # Other errors (API errors, network issues)
                error_type = type(e).__name__
                retry_history.append((attempt + 1, "api_error"))

                logger.error(
                    f"Streaming error on attempt {attempt + 1}/{max_retries}: {str(e)}",
                    extra={
                        "event_type": "llm_retry",
                        "retry_attempt": attempt + 1,
                        "max_retries": max_retries,
                        "retry_reason": "api_error",
                        "error_type": error_type,
                        "error_message": str(e),
                        "model_name": llm_config.model_name,
                        "section_title": context.section_title,
                        "homework_title": context.homework_title,
                        "response_mode": "streaming",
                    },
                )
                set_span_attributes(
                    {
                        "retry_attempt": attempt + 1,
                        "retry_reason": "api_error",
                        "error_type": error_type,
                    }
                )
                record_exception(e)

                if attempt == max_retries - 1:
                    raise StreamingError(
                        f"Failed to generate response after {max_retries} attempts: {str(e)}"
                    )
                continue

        # All retries exhausted - this should be the primary path for max retries
        raise StreamingError(
            f"Failed to generate response after {max_retries} attempts"
        )

    @staticmethod
    @traced
    def _stream_with_finish_reason_detection(
        llm_config: LLMConfigData,
        context: ConversationContext,
        available_functions: List[FunctionDefinition],
    ) -> Iterator[tuple[str, List[FunctionCall], FinishReason | None]]:
        """
        Stream tokens while detecting finish reason and function calls.

        Args:
            llm_config: LLM configuration data
            context: Conversation context data
            available_functions: List of functions the LLM can call

        Yields:
            Tuples of (token, function_calls, finish_reason).
            finish_reason is None until the final chunk.

        Raises:
            Exception: Any OpenAI API or streaming errors are propagated up
        """
        start_time = time.perf_counter()

        # Initialize OpenAI client with OpenRouter endpoint
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=llm_config.api_key,
            timeout=httpx.Timeout(
                connect=settings.LLM_API_CONNECTION_TIMEOUT,
                read=settings.LLM_API_TIMEOUT,
                write=10.0,
                pool=5.0,
            ),
        )

        # Build messages for OpenAI API
        # System message includes base prompt and section context
        system_message = LLMService._build_system_message(llm_config, context)
        messages = [{"role": "system", "content": system_message}]

        # Add conversation history (plain text messages)
        for msg in context.messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current message (plain text)
        messages.append({"role": "user", "content": context.current_message})

        # Record time after query preparation
        query_prepared_time = time.perf_counter()
        query_preparation_ms = int((query_prepared_time - start_time) * 1000)

        # Prepare tools parameter
        tools = [func.to_openai_format() for func in available_functions]

        # Log LLM request details
        request_attrs = {
            "event_type": "llm_request",
            "model_name": llm_config.model_name,
            "response_mode": "streaming",
            "messages_count": len(messages),
            "tools_count": len(tools),
            "tools": tools,
            "temperature": llm_config.temperature,
            "max_completion_tokens": llm_config.max_completion_tokens,
            "section_title": context.section_title,
            "homework_title": context.homework_title,
            "timeout_connect_seconds": settings.LLM_API_CONNECTION_TIMEOUT,
            "timeout_read_seconds": settings.LLM_API_TIMEOUT,
        }
        logger.info("LLM API request", extra=request_attrs)
        set_span_attributes(request_attrs)

        # Make streaming API call with tools
        stream = client.chat.completions.create(
            model=llm_config.model_name,
            messages=messages,  # type: ignore
            temperature=llm_config.temperature,
            max_completion_tokens=llm_config.max_completion_tokens,
            stream=True,  # Enable streaming
            tools=tools,  # type: ignore
        )

        # Stream tokens and capture finish reason and tool calls
        finish_reason = None
        first_token_time = None
        token_count = 0
        tool_calls_accumulator = {}  # Accumulate tool call deltas by index

        for chunk in stream:
            if not isinstance(chunk, ChatCompletionChunk):
                continue
            if chunk.choices and len(chunk.choices) > 0:
                choice = chunk.choices[0]

                # Extract token content
                if hasattr(choice.delta, "content") and choice.delta.content:
                    # Record time of first token
                    if first_token_time is None:
                        first_token_time = time.perf_counter()

                    token_count += 1
                    yield choice.delta.content, [], None

                # Extract tool calls from delta
                if hasattr(choice.delta, "tool_calls") and choice.delta.tool_calls:
                    for tool_call_delta in choice.delta.tool_calls:
                        index = tool_call_delta.index
                        if index not in tool_calls_accumulator:
                            tool_calls_accumulator[index] = {
                                "id": "",
                                "name": "",
                                "arguments": "",
                            }

                        if hasattr(tool_call_delta, "id") and tool_call_delta.id:
                            tool_calls_accumulator[index]["id"] = tool_call_delta.id

                        if (
                            hasattr(tool_call_delta, "function")
                            and tool_call_delta.function
                        ):
                            if (
                                hasattr(tool_call_delta.function, "name")
                                and tool_call_delta.function.name
                            ):
                                tool_calls_accumulator[index]["name"] = (
                                    tool_call_delta.function.name
                                )

                            if (
                                hasattr(tool_call_delta.function, "arguments")
                                and tool_call_delta.function.arguments
                            ):
                                tool_calls_accumulator[index]["arguments"] += (
                                    tool_call_delta.function.arguments
                                )

                # Capture finish reason from final chunk
                if hasattr(choice, "finish_reason") and choice.finish_reason:
                    finish_reason_str = choice.finish_reason
                    # Convert string to FinishReason enum
                    try:
                        finish_reason = FinishReason(finish_reason_str)
                    except ValueError:
                        # Unknown finish reason
                        logger.warning(
                            f"Unknown finish reason from OpenAI: {finish_reason_str}"
                        )
                        finish_reason = None

        # Process accumulated tool calls
        function_calls = []
        for index in sorted(tool_calls_accumulator.keys()):
            tool_call_data = tool_calls_accumulator[index]
            try:
                arguments = json.loads(tool_call_data["arguments"])
                function_calls.append(
                    FunctionCall(
                        id=tool_call_data["id"],
                        name=tool_call_data["name"],
                        arguments=arguments,
                    )
                )
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse function arguments in streaming: {tool_call_data['arguments']}, error: {e}"
                )

        # Calculate timing metrics
        end_time = time.perf_counter()
        total_response_time_ms = int((end_time - start_time) * 1000)

        if first_token_time is not None:
            time_to_first_token_ms = int(
                (first_token_time - query_prepared_time) * 1000
            )
            total_streaming_time_ms = int((end_time - first_token_time) * 1000)
        else:
            time_to_first_token_ms = 0
            total_streaming_time_ms = 0

        # Log streaming timing
        timing_attrs = {
            "event_type": "llm_response_timing",
            "model_name": llm_config.model_name,
            "response_mode": "streaming",
            "query_preparation_ms": query_preparation_ms,
            "time_to_first_token_ms": time_to_first_token_ms,
            "total_streaming_time_ms": total_streaming_time_ms,
            "total_response_time_ms": total_response_time_ms,
            "token_count": token_count,
            "success": finish_reason in [FinishReason.STOP, FinishReason.TOOL_CALLS]
            if finish_reason
            else False,
            "finish_reason": finish_reason.value if finish_reason else None,
            "has_function_calls": len(function_calls) > 0,
            "function_calls_count": len(function_calls),
            "section_title": context.section_title,
            "homework_title": context.homework_title,
            "message_type": context.message_type,
        }
        logger.info("LLM response timing", extra=timing_attrs)
        set_span_attributes(timing_attrs)

        # Yield final finish reason and function calls (even if None for interrupted streams)
        yield "", function_calls, finish_reason

    @staticmethod
    @traced
    def _build_conversation_context(
        conversation: "Conversation", content: str, message_type: str
    ) -> ConversationContext:
        """
        Build conversation context for LLM prompt.

        Args:
            conversation: Conversation object
            content: Latest message content
            message_type: Type of message

        Returns:
            ConversationContext with all relevant data
        """
        # Get previous messages
        messages = []
        for msg in conversation.messages.all().order_by("timestamp"):
            if msg.is_from_student:
                messages.append({"role": "user", "content": msg.content})
            elif msg.is_from_ai:
                messages.append({"role": "assistant", "content": msg.content})
            # Skip system messages for OpenAI context

        return ConversationContext(
            section_title=conversation.section.title,
            section_content=conversation.section.content,
            homework_title=conversation.section.homework.title,
            messages=messages,
            current_message=content,
            message_type=message_type,
        )

    @staticmethod
    def _build_system_message(
        llm_config: LLMConfigData, context: ConversationContext
    ) -> str:
        """
        Build system message with base prompt and section context.

        Section context is included once in the system message to avoid repetition
        in every user message, significantly reducing token usage in multi-turn conversations.

        Args:
            llm_config: LLM configuration data
            context: Conversation context data

        Returns:
            String containing the system message with base prompt and section context
        """
        parts = [
            llm_config.base_prompt,
            "",  # Empty line for separation
            f"Homework: {context.homework_title}",
            f"Section: {context.section_title}",
            f"Section Content: {context.section_content}",
            "",  # Empty line for separation
            "Please respond as an AI tutor helping the student with this section. Guide them without giving away the complete answer.",
        ]

        return "\n".join(parts)

    @staticmethod
    @traced
    def get_default_config() -> Optional[LLMConfigData]:
        """
        Get the default LLM configuration data.

        Returns:
            LLMConfigData if default config found, None otherwise
        """
        from .models import LLMConfig

        try:
            # Get default config
            config = LLMConfig.objects.get(is_default=True, is_active=True)
            return LLMConfigData.from_model(config)
        except LLMConfig.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting default LLM config: {str(e)}")
            record_exception(e)
            return None

    @staticmethod
    @traced
    def get_config_by_id(config_id: UUID) -> Optional[LLMConfigData]:
        """
        Get LLM configuration by ID.

        Args:
            config_id: UUID of the configuration

        Returns:
            LLMConfigData if found, None otherwise
        """
        from .models import LLMConfig

        try:
            config = LLMConfig.objects.get(id=config_id, is_active=True)
            return LLMConfigData.from_model(config)
        except LLMConfig.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting LLM config by ID: {str(e)}")
            record_exception(e)
            return None

    @staticmethod
    @traced
    def get_all_configs() -> List[LLMConfigData]:
        """
        Get all active LLM configurations.

        Returns:
            List of LLMConfigData objects
        """
        from .models import LLMConfig

        try:
            configs = LLMConfig.objects.filter(is_active=True).order_by("name")
            return [LLMConfigData.from_model(config) for config in configs]
        except Exception as e:
            logger.error(f"Error getting all LLM configs: {str(e)}")
            record_exception(e)
            return []

    @staticmethod
    @traced
    def create_config(data: LLMConfigCreateData) -> LLMConfigCreateResult:
        """
        Create a new LLM configuration.

        Args:
            data: LLMConfigCreateData with configuration parameters

        Returns:
            LLMConfigCreateResult with success status and config ID
        """
        from .models import LLMConfig

        try:
            # Create config
            config = LLMConfig.objects.create(
                name=data.name,
                model_name=data.model_name,
                api_key=data.api_key,
                base_prompt=data.base_prompt,
                temperature=data.temperature,
                max_completion_tokens=data.max_completion_tokens,
                is_default=data.is_default,
                is_active=data.is_active,
            )

            return LLMConfigCreateResult(config_id=config.id, success=True)
        except Exception as e:
            logger.error(f"Error creating LLM config: {str(e)}")
            record_exception(e)
            return LLMConfigCreateResult(success=False, error=str(e))

    @staticmethod
    @traced
    def update_config(config_id: UUID, data: Dict[str, Any]) -> LLMConfigUpdateResult:
        """
        Update an existing LLM configuration.

        Args:
            config_id: UUID of the configuration to update
            data: Dictionary with configuration parameters to update

        Returns:
            LLMConfigUpdateResult with success status
        """
        from .models import LLMConfig

        try:
            # Get config
            config = LLMConfig.objects.get(id=config_id)

            # Update fields if provided
            if "name" in data:
                config.name = data["name"]
            if "model_name" in data:
                config.model_name = data["model_name"]
            if "api_key" in data:
                config.api_key = data["api_key"]
            if "base_prompt" in data:
                config.base_prompt = data["base_prompt"]
            if "temperature" in data:
                config.temperature = data["temperature"]
            if "max_completion_tokens" in data:
                config.max_completion_tokens = data["max_completion_tokens"]
            if "is_default" in data:
                config.is_default = data["is_default"]
            if "is_active" in data:
                config.is_active = data["is_active"]

            # Save changes
            config.save()

            return LLMConfigUpdateResult(success=True)
        except LLMConfig.DoesNotExist:
            return LLMConfigUpdateResult(success=False, error="Configuration not found")
        except Exception as e:
            logger.error(f"Error updating LLM config: {str(e)}")
            record_exception(e)
            return LLMConfigUpdateResult(success=False, error=str(e))

    @staticmethod
    @traced
    def delete_config(config_id: UUID) -> LLMConfigUpdateResult:
        """
        Delete (deactivate) an LLM configuration.

        Args:
            config_id: UUID of the configuration to delete

        Returns:
            LLMConfigUpdateResult with success status
        """
        from .models import LLMConfig

        try:
            config = LLMConfig.objects.get(id=config_id)

            # Don't allow deleting the default config
            if config.is_default:
                return LLMConfigUpdateResult(
                    success=False, error="Cannot delete the default configuration"
                )

            # Soft delete by setting is_active to False
            config.is_active = False
            config.save()

            return LLMConfigUpdateResult(success=True)
        except LLMConfig.DoesNotExist:
            return LLMConfigUpdateResult(success=False, error="Configuration not found")
        except Exception as e:
            logger.error(f"Error deleting LLM config: {str(e)}")
            record_exception(e)
            return LLMConfigUpdateResult(success=False, error=str(e))

    @staticmethod
    @traced
    def test_config(
        config_id: UUID, test_message: str = "Hello, this is a test message."
    ) -> LLMResponseWithTools:
        """
        Test an LLM configuration with a simple message.

        Args:
            config_id: UUID of the configuration to test
            test_message: Message to send for testing

        Returns:
            LLMResponseWithTools with test response or error
        """
        try:
            # Get config
            config_data = LLMService.get_config_by_id(config_id)
            if not config_data:
                return LLMResponseWithTools(
                    response_text="",
                    tokens_used=0,
                    success=False,
                    error="Configuration not found",
                )

            # Create test context
            test_context = ConversationContext(
                section_title="Test Section",
                section_content="This is a test section for configuration validation.",
                homework_title="Test Homework",
                messages=[],
                current_message=test_message,
                message_type="student",
            )

            # Generate test response - use empty function list for testing
            return LLMService._generate_openai_response(
                config_data, test_context, available_functions=[]
            )

        except Exception as e:
            logger.error(f"Error testing LLM config: {str(e)}")
            record_exception(e)
            return LLMResponseWithTools(
                response_text="", tokens_used=0, success=False, error=str(e)
            )

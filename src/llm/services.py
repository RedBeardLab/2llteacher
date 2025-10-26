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
from enum import StrEnum

# Handle imports for type checking
if TYPE_CHECKING:
    from conversations.models import Conversation, Message
    from .models import LLMConfig

from openai import OpenAI


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
class StreamToken:
    """Token object for streaming with completion signal."""
    type: StreamTokenType
    content: str
    finish_reason: FinishReason | None = None


@dataclass
class ConversationContext:
    section_title: str
    section_content: str
    homework_title: str
    messages: list[dict[str, str]]  # List of {"role": "user/assistant", "content": "..."}
    current_message: str
    message_type: str


class LLMService:
    """
    Service class for LLM-related business logic.

    This service follows a testable-first approach with clear data contracts
    and properly typed methods for easier testing and maintenance.
    """


    @staticmethod
    def get_response(
        conversation: "Conversation", content: str, message_type: str
    ) -> str:
        """
        Generate an AI response based on conversation context.

        Args:
            conversation: Conversation object
            content: Latest message content
            message_type: Type of message

        Returns:
            String containing the AI response
        """
        try:
            # Get LLM config - first from the homework, then fallback to default
            llm_config = None
            if (
                hasattr(conversation.section, "homework")
                and conversation.section.homework.llm_config
            ):
                llm_config = LLMConfigData.from_model(conversation.section.homework.llm_config)

            # If no config on homework, get default config
            if not llm_config:
                llm_config = LLMService.get_default_config()
                if not llm_config:
                    return "I'm sorry, but there's no valid LLM configuration available right now."

            # Build conversation context
            context = LLMService._build_conversation_context(
                conversation, content, message_type
            )

            # Generate response using OpenAI client
            response_result = LLMService._generate_openai_response(llm_config, context)

            if response_result.success:
                return response_result.response_text
            else:
                error_id = uuid.uuid4()
                logger.error(
                    f"LLM response generation failed [ID: {error_id}]: {response_result.error}"
                )
                return f"I'm sorry, there was a technical issue. Please contact your administrator with reference ID: {error_id}"

        except Exception as e:
            error_id = uuid.uuid4()
            logger.error(f"Error generating AI response [ID: {error_id}]: {str(e)}")
            return f"I'm sorry, there was a technical issue. Please contact your administrator with reference ID: {error_id}"

    @staticmethod
    def _generate_openai_response(
        llm_config: LLMConfigData, context: ConversationContext
    ) -> LLMResponseResult:
        """
        Generate response using OpenAI client.

        Args:
            llm_config: LLM configuration data
            context: Conversation context data

        Returns:
            LLMResponseResult with response or error
        """
        start_time = time.perf_counter()
        
        try:
            # Initialize OpenAI client with OpenRouter endpoint
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=llm_config.api_key
            )

            # Build messages for OpenAI API with proper typing
            messages = [{"role": "system", "content": llm_config.base_prompt}]

            # Add conversation history
            for msg in context.messages:
                messages.append({"role": msg["role"], "content": msg["content"]})

            # Add current message with context
            current_prompt = LLMService._build_current_prompt(context)
            messages.append({"role": "user", "content": current_prompt})

            # Record time after query preparation
            query_prepared_time = time.perf_counter()
            query_preparation_ms = int((query_prepared_time - start_time) * 1000)

            # Make API call
            response = client.chat.completions.create(
                model=llm_config.model_name,
                messages=messages,  # type: ignore
                temperature=llm_config.temperature,
                max_completion_tokens=llm_config.max_completion_tokens,
            )

            # Calculate total response time
            end_time = time.perf_counter()
            total_response_time_ms = int((end_time - start_time) * 1000)
            api_response_time_ms = int((end_time - query_prepared_time) * 1000)

            # Extract response
            if response.choices and len(response.choices) > 0:
                response_text = response.choices[0].message.content or ""
                tokens_used = response.usage.total_tokens if response.usage else 0

                # Log response timing
                logger.info("LLM response timing", extra={
                    "event_type": "llm_response_timing",
                    "model_name": llm_config.model_name,
                    "response_mode": "non_streaming",
                    "query_preparation_ms": query_preparation_ms,
                    "api_response_time_ms": api_response_time_ms,
                    "total_response_time_ms": total_response_time_ms,
                    "token_count": tokens_used,
                    "success": True,
                    "section_title": context.section_title,
                    "homework_title": context.homework_title,
                    "message_type": context.message_type
                })

                return LLMResponseResult(
                    response_text=response_text, tokens_used=tokens_used, success=True
                )
            else:
                # Log failed response timing
                logger.info("LLM response timing", extra={
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
                    "message_type": context.message_type
                })

                return LLMResponseResult(
                    response_text="",
                    tokens_used=0,
                    success=False,
                    error="No response generated from OpenAI API",
                )

        except Exception as e:
            # Calculate response time even for errors
            end_time = time.perf_counter()
            total_response_time_ms = int((end_time - start_time) * 1000)

            # Log error timing
            logger.info("LLM response timing", extra={
                "event_type": "llm_response_timing",
                "model_name": llm_config.model_name,
                "response_mode": "non_streaming",
                "total_response_time_ms": total_response_time_ms,
                "token_count": 0,
                "success": False,
                "error": str(e),
                "section_title": context.section_title,
                "homework_title": context.homework_title,
                "message_type": context.message_type
            })

            logger.error(f"OpenAI API error: {str(e)}")
            return LLMResponseResult(
                response_text="", tokens_used=0, success=False, error=str(e)
            )



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
    def stream_response_with_completion(
        conversation: "Conversation", content: str, message_type: str
    ) -> Iterator[StreamToken]:
        """
        Enhanced streaming that yields tokens and signals completion with final response.
        Handles retries transparently with finish reason detection and meaningful content validation.

        Args:
            conversation: Conversation object
            content: Latest message content
            message_type: Type of message

        Yields:
            StreamToken objects for tokens and completion signal

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
                llm_config = LLMConfigData.from_model(conversation.section.homework.llm_config)

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
            yield from LLMService._stream_with_intelligent_retry(llm_config, context)

        except Exception as e:
            error_id = uuid.uuid4()
            logger.error(f"Error in stream_response_with_completion [ID: {error_id}]: {str(e)}")
            raise StreamingError(f"Streaming failed: {str(e)}")

    @staticmethod
    def _stream_with_intelligent_retry(
        llm_config: LLMConfigData, context: ConversationContext, max_retries: int = 3
    ) -> Iterator[StreamToken]:
        """
        Stream with intelligent retry logic based on finish reasons and content validation.

        Args:
            llm_config: LLM configuration data
            context: Conversation context data
            max_retries: Maximum number of retry attempts

        Yields:
            StreamToken objects for tokens and completion

        Raises:
            StreamingError: When all retries fail or length limit hit
        """
        for attempt in range(max_retries):
            try:
                accumulated_response = ""
                chunk_count = 0
                meaningful_chunks = 0
                
                # Stream with finish reason detection
                for token, finish_reason in LLMService._stream_with_finish_reason_detection(
                    llm_config, context
                ):
                    if token:  # Only process non-empty tokens
                        chunk_count += 1
                        accumulated_response += token
                        
                        # Check if token is meaningful
                        if LLMService._is_meaningful_chunk(token):
                            meaningful_chunks += 1
                            yield StreamToken(type=StreamTokenType.TOKEN, content=token)
                
                # Validate response quality before checking finish reason
                response_length = len(accumulated_response)
                
                # Check if we got sufficient meaningful content
                if meaningful_chunks == 0 or response_length < 3:
                    logger.warning(
                        f"Insufficient content on attempt {attempt + 1}/{max_retries} "
                        f"(chunks: {chunk_count}, meaningful: {meaningful_chunks}, length: {response_length})"
                    )
                    # Treat as interrupted stream, continue to retry
                    continue
                
                # Check completion reason
                if finish_reason == FinishReason.STOP:
                    # Success! Signal completion with full response
                    yield StreamToken(
                        type=StreamTokenType.COMPLETE,
                        content=accumulated_response,
                        finish_reason=finish_reason
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
                    continue
                else:
                    # Unknown finish reason - treat as error and retry
                    logger.warning(f"Unknown finish reason: {finish_reason}, retrying...")
                    continue
                    
            except StreamingError:
                # Re-raise streaming errors (don't retry)
                raise
            except Exception as e:
                logger.error(f"Streaming error on attempt {attempt + 1}/{max_retries}: {str(e)}")
                if attempt == max_retries - 1:
                    # Final attempt failed
                    raise StreamingError(f"Failed to generate response after {max_retries} attempts")
        
        # All retries exhausted - this should be the primary path for max retries
        raise StreamingError(f"Failed to generate response after {max_retries} attempts")

    @staticmethod
    def _stream_with_finish_reason_detection(
        llm_config: LLMConfigData, context: ConversationContext
    ) -> Iterator[tuple[str, FinishReason | None]]:
        """
        Stream tokens while detecting finish reason.

        Args:
            llm_config: LLM configuration data
            context: Conversation context data

        Yields:
            Tuples of (token, finish_reason). finish_reason is None until the final chunk.

        Raises:
            Exception: Any OpenAI API or streaming errors are propagated up
        """
        start_time = time.perf_counter()
        
        # Initialize OpenAI client with OpenRouter endpoint
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=llm_config.api_key
        )

        # Build messages for OpenAI API
        messages = [{"role": "system", "content": llm_config.base_prompt}]

        # Add conversation history
        for msg in context.messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current message with context
        current_prompt = LLMService._build_current_prompt(context)
        messages.append({"role": "user", "content": current_prompt})

        # Record time after query preparation
        query_prepared_time = time.perf_counter()
        query_preparation_ms = int((query_prepared_time - start_time) * 1000)

        # Make streaming API call
        stream = client.chat.completions.create(
            model=llm_config.model_name,
            messages=messages,  # type: ignore
            temperature=llm_config.temperature,
            max_completion_tokens=llm_config.max_completion_tokens,
            stream=True,  # Enable streaming
        )

        # Stream tokens and capture finish reason
        finish_reason = None
        first_token_time = None
        token_count = 0
        
        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                
                # Extract token content
                if hasattr(choice.delta, "content") and choice.delta.content:
                    # Record time of first token
                    if first_token_time is None:
                        first_token_time = time.perf_counter()
                    
                    token_count += 1
                    yield choice.delta.content, None
                
                # Capture finish reason from final chunk
                if hasattr(choice, "finish_reason") and choice.finish_reason:
                    finish_reason_str = choice.finish_reason
                    # Convert string to FinishReason enum
                    try:
                        finish_reason = FinishReason(finish_reason_str)
                    except ValueError:
                        # Unknown finish reason
                        logger.warning(f"Unknown finish reason from OpenAI: {finish_reason_str}")
                        finish_reason = None
        
        # Calculate timing metrics
        end_time = time.perf_counter()
        total_response_time_ms = int((end_time - start_time) * 1000)
        
        if first_token_time is not None:
            time_to_first_token_ms = int((first_token_time - query_prepared_time) * 1000)
            total_streaming_time_ms = int((end_time - first_token_time) * 1000)
        else:
            time_to_first_token_ms = 0
            total_streaming_time_ms = 0

        # Log streaming timing
        logger.info("LLM response timing", extra={
            "event_type": "llm_response_timing",
            "model_name": llm_config.model_name,
            "response_mode": "streaming",
            "query_preparation_ms": query_preparation_ms,
            "time_to_first_token_ms": time_to_first_token_ms,
            "total_streaming_time_ms": total_streaming_time_ms,
            "total_response_time_ms": total_response_time_ms,
            "token_count": token_count,
            "success": finish_reason == FinishReason.STOP if finish_reason else False,
            "finish_reason": finish_reason.value if finish_reason else None,
            "section_title": context.section_title,
            "homework_title": context.homework_title,
            "message_type": context.message_type
        })
        
        # Yield final finish reason (even if None for interrupted streams)
        yield "", finish_reason

    @staticmethod
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
    def _build_current_prompt(context: ConversationContext) -> str:
        """
        Build the current prompt with section context.

        Args:
            context: Conversation context data

        Returns:
            String containing the prompt for the language model
        """
        # Build context parts
        context_parts = [
            f"Homework: {context.homework_title}",
            f"Section: {context.section_title}",
            f"Section Content: {context.section_content}",
        ]

        # Add current message based on type
        if context.message_type == "student":
            context_parts.append(f"\nStudent Question: {context.current_message}")
        elif context.message_type == "code":
            context_parts.append(
                f"\nStudent Code Submission:\n```\n{context.current_message}\n```"
            )
        else:
            context_parts.append(f"\nStudent Message: {context.current_message}")

        # Add instruction
        context_parts.append(
            "\nPlease respond as an AI tutor helping the student with this section. Guide them without giving away the complete answer."
        )

        return "\n\n".join(context_parts)

    @staticmethod
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
            return None

    @staticmethod
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
            return None

    @staticmethod
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
            return []

    @staticmethod
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
            return LLMConfigCreateResult(success=False, error=str(e))

    @staticmethod
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
            return LLMConfigUpdateResult(success=False, error=str(e))

    @staticmethod
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
            return LLMConfigUpdateResult(success=False, error=str(e))

    @staticmethod
    def test_config(
        config_id: UUID, test_message: str = "Hello, this is a test message."
    ) -> LLMResponseResult:
        """
        Test an LLM configuration with a simple message.

        Args:
            config_id: UUID of the configuration to test
            test_message: Message to send for testing

        Returns:
            LLMResponseResult with test response or error
        """
        try:
            # Get config
            config_data = LLMService.get_config_by_id(config_id)
            if not config_data:
                return LLMResponseResult(
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

            # Generate test response using the config data we already have
            return LLMService._generate_openai_response(config_data, test_context)

        except Exception as e:
            logger.error(f"Error testing LLM config: {str(e)}")
            return LLMResponseResult(
                response_text="", tokens_used=0, success=False, error=str(e)
            )

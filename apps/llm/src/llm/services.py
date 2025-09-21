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

# Handle imports for type checking
if TYPE_CHECKING:
    from conversations.models import Conversation
    from .models import LLMConfig

from openai import OpenAI

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
    messages: List[
        Dict[str, str]
    ]  # List of {"role": "user/assistant", "content": "..."}
    current_message: str
    message_type: str


class LLMService:
    """
    Service class for LLM-related business logic.

    This service follows a testable-first approach with clear data contracts
    and properly typed methods for easier testing and maintenance.
    """

    @staticmethod
    def generate_response(
        conversation: "Conversation",
        content: str,
        message_type: str,
        streaming: bool = False,
    ) -> str | Iterator[str]:
        """
        Unified response generation supporting both streaming and non-streaming modes.

        Args:
            conversation: Conversation object
            content: Latest message content
            message_type: Type of message
            streaming: If True, returns Iterator[str], else complete string

        Returns:
            Complete response string or token iterator
        """
        if streaming:
            return LLMService.stream_response(conversation, content, message_type)
        else:
            return LLMService.get_response(conversation, content, message_type)

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
                llm_config = conversation.section.homework.llm_config

            # If no config on homework, get default config
            if not llm_config:
                config_data = LLMService.get_default_config()
                if not config_data:
                    return "I'm sorry, but there's no valid LLM configuration available right now."

                # Get actual LLM config object from data
                from .models import LLMConfig

                llm_config = LLMConfig.objects.get(id=config_data.id)

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
        llm_config: "LLMConfig", context: ConversationContext
    ) -> LLMResponseResult:
        """
        Generate response using OpenAI client.

        Args:
            llm_config: LLM configuration object
            context: Conversation context data

        Returns:
            LLMResponseResult with response or error
        """
        try:
            # Initialize OpenAI client
            client = OpenAI(api_key=llm_config.api_key)

            # Build messages for OpenAI API with proper typing
            messages = [{"role": "system", "content": llm_config.base_prompt}]

            # Add conversation history
            for msg in context.messages:
                messages.append({"role": msg["role"], "content": msg["content"]})

            # Add current message with context
            current_prompt = LLMService._build_current_prompt(context)
            messages.append({"role": "user", "content": current_prompt})

            # Make API call
            response = client.chat.completions.create(
                model=llm_config.model_name,
                messages=messages,
                temperature=llm_config.temperature,
                max_completion_tokens=llm_config.max_completion_tokens,
            )

            # Extract response
            if response.choices and len(response.choices) > 0:
                response_text = response.choices[0].message.content or ""
                tokens_used = response.usage.total_tokens if response.usage else 0

                return LLMResponseResult(
                    response_text=response_text, tokens_used=tokens_used, success=True
                )
            else:
                return LLMResponseResult(
                    response_text="",
                    tokens_used=0,
                    success=False,
                    error="No response generated from OpenAI API",
                )

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return LLMResponseResult(
                response_text="", tokens_used=0, success=False, error=str(e)
            )

    @staticmethod
    def stream_response(
        conversation: "Conversation", content: str, message_type: str
    ) -> Iterator[str]:
        """
        Generate a streaming AI response based on conversation context.

        Args:
            conversation: Conversation object
            content: Latest message content
            message_type: Type of message

        Yields:
            String tokens as they are generated by the LLM
        """
        try:
            # Get LLM config - first from the homework, then fallback to default
            llm_config = None
            if (
                hasattr(conversation.section, "homework")
                and conversation.section.homework.llm_config
            ):
                llm_config = conversation.section.homework.llm_config

            # If no config on homework, get default config
            if not llm_config:
                config_data = LLMService.get_default_config()
                if not config_data:
                    yield "I'm sorry, but there's no valid LLM configuration available right now."
                    return

                # Get actual LLM config object from data
                from .models import LLMConfig

                llm_config = LLMConfig.objects.get(id=config_data.id)

            # Build conversation context
            context = LLMService._build_conversation_context(
                conversation, content, message_type
            )

            # Generate streaming response using OpenAI client
            yield from LLMService._generate_streaming_openai_response(
                llm_config, context
            )

        except Exception as e:
            error_id = uuid.uuid4()
            logger.error(
                f"Error generating streaming AI response [ID: {error_id}]: {str(e)}"
            )
            yield f"I'm sorry, there was a technical issue. Please contact your administrator with reference ID: `{error_id}`"

    @staticmethod
    def _generate_streaming_openai_response(
        llm_config: "LLMConfig", context: ConversationContext
    ) -> Iterator[str]:
        """
        Generate streaming response using OpenAI client.

        Args:
            llm_config: LLM configuration object
            context: Conversation context data

        Yields:
            String tokens as they are generated
        """
        try:
            # Initialize OpenAI client
            client = OpenAI(api_key=llm_config.api_key)

            # Build messages for OpenAI API
            messages = [{"role": "system", "content": llm_config.base_prompt}]

            # Add conversation history
            for msg in context.messages:
                messages.append({"role": msg["role"], "content": msg["content"]})

            # Add current message with context
            current_prompt = LLMService._build_current_prompt(context)
            messages.append({"role": "user", "content": current_prompt})

            # Make streaming API call
            stream = client.chat.completions.create(
                model=llm_config.model_name,
                messages=messages,
                temperature=llm_config.temperature,
                max_completion_tokens=llm_config.max_completion_tokens,
                stream=True,  # Enable streaming
            )

            # Yield tokens as they arrive
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        yield delta.content

        except Exception as e:
            error_id = uuid.uuid4()
            logger.error(f"OpenAI streaming API error [ID: {error_id}]: {str(e)}")
            yield f"I'm sorry, there was a technical issue. Please contact your administrator with reference ID: `{error_id}`"

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
        Get the default LLM configuration.

        Returns:
            LLMConfigData if default config found, None otherwise
        """
        from .models import LLMConfig

        try:
            # Get default config
            config = LLMConfig.objects.get(is_default=True, is_active=True)

            # Convert to data contract
            return LLMConfigData(
                id=config.id,
                name=config.name,
                model_name=config.model_name,
                api_key=config.api_key,
                base_prompt=config.base_prompt,
                temperature=config.temperature,
                max_completion_tokens=config.max_completion_tokens,
                is_default=config.is_default,
                is_active=config.is_active,
            )
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

            return LLMConfigData(
                id=config.id,
                name=config.name,
                model_name=config.model_name,
                api_key=config.api_key,
                base_prompt=config.base_prompt,
                temperature=config.temperature,
                max_completion_tokens=config.max_completion_tokens,
                is_default=config.is_default,
                is_active=config.is_active,
            )
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

            return [
                LLMConfigData(
                    id=config.id,
                    name=config.name,
                    model_name=config.model_name,
                    api_key=config.api_key,
                    base_prompt=config.base_prompt,
                    temperature=config.temperature,
                    max_completion_tokens=config.max_completion_tokens,
                    is_default=config.is_default,
                    is_active=config.is_active,
                )
                for config in configs
            ]
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

            # Get LLM config object
            from .models import LLMConfig

            llm_config = LLMConfig.objects.get(id=config_id)

            # Generate test response
            return LLMService._generate_openai_response(llm_config, test_context)

        except Exception as e:
            logger.error(f"Error testing LLM config: {str(e)}")
            return LLMResponseResult(
                response_text="", tokens_used=0, success=False, error=str(e)
            )

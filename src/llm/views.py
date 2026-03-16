"""
LLM Views

Views for LLM configuration management following testable-first approach.
"""

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.core.exceptions import ValidationError

import logging

from llteacher.permissions.decorators import teacher_required, get_teacher_or_student
from llteacher.tracing import record_exception

from .services import (
    LLMService,
    LLMConfigData,
    LLMConfigCreateData,
    LLMConfigCreateResult,
    LLMConfigUpdateResult,
    LLMResponseResult,
)

logger = logging.getLogger(__name__)


# Data contracts for views
@dataclass
class LLMConfigListItem:
    id: UUID
    name: str
    model_name: str
    is_default: bool
    is_active: bool
    created_at: str
    updated_at: str


@dataclass
class LLMConfigListData:
    configs: List[LLMConfigListItem]
    total_count: int
    can_create: bool


@dataclass
class LLMConfigDetailData:
    config: LLMConfigData
    can_edit: bool
    can_delete: bool
    can_test: bool


@dataclass
class LLMConfigFormData:
    config: Optional[LLMConfigData] = None
    is_edit: bool = False
    form_title: str = "Create LLM Configuration"


@method_decorator(login_required, name="dispatch")
class LLMConfigListView(View):
    """List all LLM configurations using testable-first approach."""

    @method_decorator(teacher_required)
    def get(self, request: HttpRequest) -> HttpResponse:
        # Get typed data
        data = self._get_config_list_data(request.user)

        # Render with typed data
        return render(request, "llm/config_list.html", {"data": data})

    def _get_config_list_data(self, user) -> LLMConfigListData:
        """Get typed data for config list. Easy to test!"""
        teacher, student = get_teacher_or_student(user)
        can_create = teacher is not None

        # Get all configs
        configs_data = LLMService.get_all_configs()

        # Convert to list items
        config_items = []
        for config in configs_data:
            config_items.append(
                LLMConfigListItem(
                    id=config.id,
                    name=config.name,
                    model_name=config.model_name,
                    is_default=config.is_default,
                    is_active=config.is_active,
                    created_at="",  # We'll format this in template
                    updated_at="",  # We'll format this in template
                )
            )

        return LLMConfigListData(
            configs=config_items, total_count=len(config_items), can_create=can_create
        )


@method_decorator(login_required, name="dispatch")
class LLMConfigDetailView(View):
    """View LLM configuration details using testable-first approach."""

    def get(self, request: HttpRequest, config_id: UUID) -> HttpResponse:
        # Get typed data
        data = self._get_config_detail_data(request.user, config_id)

        if not data:
            messages.error(request, "Configuration not found.")
            return redirect("llm:config-list")

        # Render with typed data
        return render(request, "llm/config_detail.html", {"data": data})

    def _get_config_detail_data(
        self, user, config_id: UUID
    ) -> Optional[LLMConfigDetailData]:
        """Get typed data for config detail. Easy to test!"""
        try:
            teacher, student = get_teacher_or_student(user)

            # Get config data (config_id is already a UUID from URL pattern)
            config_data = LLMService.get_config_by_id(config_id)
            if not config_data:
                return None

            # Determine permissions
            can_edit = teacher is not None
            can_delete = teacher is not None and not config_data.is_default
            can_test = teacher is not None

            return LLMConfigDetailData(
                config=config_data,
                can_edit=can_edit,
                can_delete=can_delete,
                can_test=can_test,
            )
        except (ValueError, ValidationError):
            return None


@method_decorator(login_required, name="dispatch")
class LLMConfigCreateView(View):
    """Create LLM configuration using testable-first approach."""

    @method_decorator(teacher_required)
    def get(self, request: HttpRequest) -> HttpResponse:
        # Get form data
        data = LLMConfigFormData(is_edit=False, form_title="Create LLM Configuration")

        return render(request, "llm/config_form.html", {"data": data})

    @method_decorator(teacher_required)
    def post(self, request: HttpRequest) -> HttpResponse:
        # Parse form data
        form_data = self._parse_create_form_data(request)

        # Validate and create
        result = self._create_config(form_data)

        # Handle result
        if result.success:
            messages.success(
                request, f"Configuration '{form_data.name}' created successfully!"
            )
            return redirect("llm:config-detail", config_id=result.config_id)
        else:
            messages.error(request, result.error or "Failed to create configuration.")

            # Return form with data
            data = LLMConfigFormData(
                is_edit=False, form_title="Create LLM Configuration"
            )
            return render(
                request,
                "llm/config_form.html",
                {
                    "data": data,
                    "form_data": form_data,
                    "errors": [result.error] if result.error else [],
                },
            )

    def _parse_create_form_data(self, request: HttpRequest) -> LLMConfigCreateData:
        """Parse form data into typed object. Easy to test!"""
        return LLMConfigCreateData(
            name=request.POST.get("name", "").strip(),
            model_name=request.POST.get("model_name", "").strip(),
            api_key=request.POST.get("api_key", "").strip(),
            base_prompt=request.POST.get("base_prompt", "").strip(),
            temperature=float(request.POST.get("temperature", 0.7)),
            max_completion_tokens=int(request.POST.get("max_completion_tokens", 1000)),
            is_default=request.POST.get("is_default") == "on",
            is_active=True,
        )

    def _create_config(self, data: LLMConfigCreateData) -> LLMConfigCreateResult:
        """Create config with validation. Easy to test!"""
        # Basic validation
        if not data.name:
            return LLMConfigCreateResult(success=False, error="Name is required.")
        if not data.model_name:
            return LLMConfigCreateResult(success=False, error="Model name is required.")
        if not data.api_key:
            return LLMConfigCreateResult(success=False, error="API key is required.")
        if not data.base_prompt:
            return LLMConfigCreateResult(
                success=False, error="Base prompt is required."
            )

        # Create using service
        return LLMService.create_config(data)


@method_decorator(login_required, name="dispatch")
class LLMConfigEditView(View):
    """Edit LLM configuration using testable-first approach."""

    @method_decorator(teacher_required)
    def get(self, request: HttpRequest, config_id: UUID) -> HttpResponse:
        # Get config data (config_id is already a UUID from URL pattern)
        config_data = LLMService.get_config_by_id(config_id)
        if not config_data:
            messages.error(request, "Configuration not found.")
            return redirect("llm:config-list")

        # Get form data
        data = LLMConfigFormData(
            config=config_data,
            is_edit=True,
            form_title=f"Edit Configuration: {config_data.name}",
        )

        return render(request, "llm/config_form.html", {"data": data})

    @method_decorator(teacher_required)
    def post(self, request: HttpRequest, config_id: UUID) -> HttpResponse:
        # Get existing config (config_id is already a UUID from URL pattern)
        config_data = LLMService.get_config_by_id(config_id)
        if not config_data:
            messages.error(request, "Configuration not found.")
            return redirect("llm:config-list")

        # Parse form data
        update_data = self._parse_update_form_data(request)

        # Update config
        result = LLMService.update_config(config_id, update_data)

        # Handle result
        if result.success:
            messages.success(
                request,
                f"Configuration '{update_data.get('name', config_data.name)}' updated successfully!",
            )
            return redirect("llm:config-detail", config_id=config_id)
        else:
            messages.error(request, result.error or "Failed to update configuration.")

            # Return form with data
            data = LLMConfigFormData(
                config=config_data,
                is_edit=True,
                form_title=f"Edit Configuration: {config_data.name}",
            )
            return render(
                request,
                "llm/config_form.html",
                {
                    "data": data,
                    "form_data": update_data,
                    "errors": [result.error] if result.error else [],
                },
            )

    def _parse_update_form_data(self, request: HttpRequest) -> dict:
        """Parse update form data. Easy to test!"""
        data: dict[str, str | float | int | bool] = {}

        name = request.POST.get("name")
        if name:
            data["name"] = name.strip()

        model_name = request.POST.get("model_name")
        if model_name:
            data["model_name"] = model_name.strip()

        api_key = request.POST.get("api_key")
        if api_key:
            data["api_key"] = api_key.strip()

        base_prompt = request.POST.get("base_prompt")
        if base_prompt:
            data["base_prompt"] = base_prompt.strip()

        temperature = request.POST.get("temperature")
        if temperature:
            data["temperature"] = float(temperature)

        max_completion_tokens = request.POST.get("max_completion_tokens")
        if max_completion_tokens:
            data["max_completion_tokens"] = int(max_completion_tokens)

        data["is_default"] = request.POST.get("is_default") == "on"
        data["is_active"] = request.POST.get("is_active", "on") == "on"

        return data


@method_decorator(login_required, name="dispatch")
class LLMConfigDeleteView(View):
    """Delete LLM configuration using testable-first approach."""

    @method_decorator(teacher_required)
    def post(self, request: HttpRequest, config_id: UUID) -> HttpResponse:
        # Delete config
        result = self._delete_config(config_id)

        # Handle result
        if result.success:
            messages.success(request, "Configuration deleted successfully!")
        else:
            messages.error(request, result.error or "Failed to delete configuration.")

        return redirect("llm:config-list")

    def _delete_config(self, config_id: UUID) -> LLMConfigUpdateResult:
        """Delete config with validation. Easy to test!"""
        try:
            # config_id is already a UUID from URL pattern
            return LLMService.delete_config(config_id)
        except ValueError:
            return LLMConfigUpdateResult(
                success=False, error="Invalid configuration ID."
            )


@method_decorator(login_required, name="dispatch")
class LLMConfigTestView(View):
    """Test LLM configuration using testable-first approach."""

    @method_decorator(teacher_required)
    def post(self, request: HttpRequest, config_id: UUID) -> JsonResponse:
        # Parse test data
        test_message = request.POST.get(
            "test_message", "Hello, this is a test message."
        )

        # Test config
        result = self._test_config(config_id, test_message)

        # Return JSON response
        return JsonResponse(
            {
                "success": result.success,
                "response_text": result.response_text if result.success else "",
                "tokens_used": result.tokens_used if result.success else 0,
                "error": result.error if not result.success else None,
            }
        )

    def _test_config(self, config_id: UUID, test_message: str) -> LLMResponseResult:
        """Test config with validation. Easy to test!"""
        try:
            # config_id is already a UUID from URL pattern
            return LLMService.test_config(config_id, test_message)
        except ValueError:
            return LLMResponseResult(
                response_text="",
                tokens_used=0,
                success=False,
                error="Invalid configuration ID.",
            )


# API Views for other apps to use LLM services


@method_decorator(login_required, name="dispatch")
class LLMGenerateAPIView(View):
    """API endpoint for generating LLM responses using testable-first approach."""

    def post(self, request: HttpRequest) -> JsonResponse:
        # Parse request data
        request_data = self._parse_api_request(request)

        # Generate response
        result = self._generate_api_response(request.user, request_data)

        # Return JSON response
        return JsonResponse(
            {
                "success": result["success"],
                "response_text": result.get("response_text", ""),
                "error": result.get("error"),
            }
        )

    def _parse_api_request(self, request: HttpRequest) -> dict:
        """Parse API request data. Easy to test!"""
        try:
            if request.content_type == "application/json":
                import json

                data = json.loads(request.body)
            else:
                data = {
                    "conversation_id": request.POST.get("conversation_id"),
                    "content": request.POST.get("content", ""),
                    "message_type": request.POST.get("message_type", "student"),
                }
            return data
        except Exception as e:
            logger.exception("Error parsing request data")
            record_exception(e)
            return {}

    def _generate_api_response(self, user, data: dict) -> dict:
        """Generate LLM response with validation. Easy to test!"""
        # Validate input
        if not data.get("content"):
            return {"success": False, "error": "Content is required"}

        if not data.get("conversation_id"):
            return {"success": False, "error": "Conversation ID is required"}

        try:
            # Get conversation
            from conversations.models import Conversation

            conversation = Conversation.objects.get(id=data["conversation_id"])

            # Check access
            teacher, student = get_teacher_or_student(user)
            if not (
                conversation.user == user
                or (teacher and conversation.section.homework.created_by == teacher)
            ):
                return {"success": False, "error": "Access denied"}

            # Generate response with function calling
            stopping_rule = LLMService.get_stopping_rule_function()
            response = LLMService.get_response(
                conversation,
                data["content"],
                data["message_type"],
                available_functions=[stopping_rule],
            )

            result = {
                "success": True,
                "response_text": response.response_text,
                "conversation_id": str(conversation.id),
            }

            # Include function calls if present
            if response.has_function_calls:
                result["function_calls"] = [
                    {
                        "id": call.id,
                        "name": call.name,
                        "arguments": call.arguments,
                    }
                    for call in response.function_calls
                ]

            return result

        except Exception as e:
            logger.exception("Error generating API response")
            record_exception(e)
            return {"success": False, "error": str(e)}


@method_decorator(login_required, name="dispatch")
class LLMConfigsAPIView(View):
    """API endpoint for getting LLM configurations using testable-first approach."""

    def get(self, request: HttpRequest) -> JsonResponse:
        # Get configs data
        data = self._get_configs_data(request.user)

        # Return JSON response
        return JsonResponse(data)

    def _get_configs_data(self, user) -> dict:
        """Get configs data for API. Easy to test!"""
        try:
            configs = LLMService.get_all_configs()

            config_list = [
                {
                    "id": str(config.id),
                    "name": config.name,
                    "model_name": config.model_name,
                    "is_default": config.is_default,
                }
                for config in configs
            ]

            return {"success": True, "configs": config_list}
        except Exception as e:
            logger.exception("Error getting LLM configs")
            record_exception(e)
            return {"success": False, "error": str(e)}

import json
import logging
from typing import Iterator

import httpx
from openai import OpenAI

from django.conf import settings
from django.urls import reverse

from chat.models import Chat, ChatMessage, ChatMessageContext
from rag.services.api_key import resolve_embedding_api_key
from rag.services.embeddings import Embedder
from rag.services.vector_search import search_similar


logger = logging.getLogger(__name__)


class ChatService:
    """Service for course-level chat operations with RAG support."""

    @staticmethod
    def get_user_chats(user, course) -> list[Chat]:
        return list(
            Chat.objects.filter(user=user, course=course, is_deleted=False).order_by(
                "-updated_at"
            )
        )

    @staticmethod
    def create_chat(user, course) -> Chat:
        chat = Chat.objects.create(user=user, course=course)
        ChatMessage.objects.create(
            chat=chat,
            content=f"Hello! I'm your AI tutor for **{course.name}**. "
            f"I can help you understand the course material. "
            f"Feel free to ask me any questions about the topics covered in this course.",
            message_type=ChatMessage.MESSAGE_TYPE_AI,
        )
        return chat

    @staticmethod
    def start_chat(user, course) -> Chat:
        chat, created = Chat.objects.get_or_create(
            user=user,
            course=course,
            is_deleted=False,
            defaults={"title": ""},
        )
        if created:
            ChatMessage.objects.create(
                chat=chat,
                content=f"Hello! I'm your AI tutor for **{course.name}**. "
                f"I can help you understand the course material. "
                f"Feel free to ask me any questions about the topics covered in this course.",
                message_type=ChatMessage.MESSAGE_TYPE_AI,
            )
        return chat

    @staticmethod
    def process_message_stream(chat: Chat, content: str) -> Iterator[str]:
        from llm.services import (
            LLMService,
            FunctionDefinition,
            LLMResponseWithTools,
            FinishReason,
        )

        user_msg = ChatMessage.objects.create(
            chat=chat, content=content, message_type=ChatMessage.MESSAGE_TYPE_STUDENT
        )
        yield f"data: {json.dumps({'type': 'user_message', 'content': content, 'message_id': str(user_msg.id)})}\n\n"

        llm_config = LLMService.get_chat_config(chat.course_id)
        if not llm_config:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No LLM configuration available'})}\n\n"
            return

        messages = ChatService._build_chat_messages(chat)

        ai_msg = ChatMessage.objects.create(
            chat=chat, content="", message_type=ChatMessage.MESSAGE_TYPE_AI
        )
        yield f"data: {json.dumps({'type': 'ai_message_start', 'message_id': str(ai_msg.id)})}\n\n"

        retrieve_fn = LLMService.get_retrieve_knowledge_function()
        try:
            response = LLMService._generate_chat_response(
                llm_config, messages, available_functions=[retrieve_fn]
            )
        except Exception as e:
            logger.error(f"First LLM call failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to generate response'})}\n\n"
            ai_msg.delete()
            return

        if response.has_function_calls:
            fc = response.function_calls[0]

            query = fc.arguments.get("query", "")
            chunks = ChatService._execute_rag(query, str(chat.course_id))

            ai_msg.tool_call_id = fc.id
            ai_msg.tool_call_arguments = json.dumps(fc.arguments)
            ai_msg.save()

            messages_with_rag = list(messages)
            messages_with_rag.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": fc.id,
                            "type": "function",
                            "function": {
                                "name": "retrieve_knowledge",
                                "arguments": json.dumps(fc.arguments),
                            },
                        }
                    ],
                }
            )
            context_texts = []
            for c in chunks:
                pdf_url = reverse("materials:pdf", kwargs={
                    "material_id": c.material_id, "checksum": c.material_checksum,
                })
                context_texts.append(
                    f"From [{c.material_title}]({pdf_url}#page={c.page_start}) "
                    f"(p.{c.page_start}-{c.page_end}):\n{c.content}"
                )
            messages_with_rag.append(
                {
                    "role": "tool",
                    "tool_call_id": fc.id,
                    "content": "\n\n".join(context_texts),
                }
            )

            accumulated = ""
            try:
                for token_text, tool_calls, finish_reason in LLMService._stream_chat_response(
                    llm_config,
                    messages_with_rag,
                    available_functions=[],
                ):
                    if token_text:
                        accumulated += token_text
                        yield f"data: {json.dumps({'type': 'ai_token', 'token': token_text, 'message_id': str(ai_msg.id)})}\n\n"
                    if finish_reason:
                        break
            except Exception as e:
                logger.error(f"Second LLM stream failed: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to generate response'})}\n\n"
                ai_msg.delete()
                return

            ai_msg.content = accumulated
            ai_msg.save()

            context_records = [
                ChatMessageContext(
                    message=ai_msg,
                    chunk_id=c.chunk_id,
                    material_title=c.material_title,
                    page_start=c.page_start,
                    page_end=c.page_end,
                    content=c.content,
                    score=c.score,
                    query=query,
                )
                for c in chunks
            ]
            if context_records:
                ChatMessageContext.objects.bulk_create(context_records)

            yield (
                f"data: {json.dumps({'type': 'ai_message_complete', 'final_content': accumulated, 'message_id': str(ai_msg.id)})}\n\n"
            )
        else:
            text = response.response_text or ""
            ai_msg.content = text
            ai_msg.save()

            if text:
                words = text.split(" ")
                for i, word in enumerate(words):
                    sep = " " if i < len(words) - 1 else ""
                    yield f"data: {json.dumps({'type': 'ai_token', 'token': word + sep, 'message_id': str(ai_msg.id)})}\n\n"

            yield (
                f"data: {json.dumps({'type': 'ai_message_complete', 'final_content': text, 'message_id': str(ai_msg.id)})}\n\n"
            )

        title = ChatService._maybe_generate_title(chat)
        if title:
            yield f"data: {json.dumps({'type': 'chat_title_updated', 'title': title, 'chat_id': str(chat.id)})}\n\n"

    @staticmethod
    def _build_chat_messages(chat: Chat) -> list[dict]:
        from django.db.models import Prefetch
        from llm.services import LLMService

        messages = chat.messages.order_by("timestamp").select_related(
            "chat__course"
        ).prefetch_related(
            Prefetch(
                "contexts",
                queryset=ChatMessageContext.objects.select_related("chunk__material"),
            )
        )
        system_message = LLMService._build_chat_system_message(chat)
        result = [{"role": "system", "content": system_message}]

        for msg in messages:
            if msg.message_type == ChatMessage.MESSAGE_TYPE_STUDENT:
                result.append({"role": "user", "content": msg.content})
            elif msg.message_type == ChatMessage.MESSAGE_TYPE_AI:
                if msg.tool_call_id:
                    result.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": msg.tool_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": "retrieve_knowledge",
                                        "arguments": msg.tool_call_arguments,
                                    },
                                }
                            ],
                        }
                    )
                    context_texts = []
                    for c in msg.contexts.all():
                        if c.chunk:
                            pdf_url = reverse("materials:pdf", kwargs={
                                "material_id": c.chunk.material_id,
                                "checksum": c.chunk.material.checksum,
                            })
                            context_texts.append(
                                f"From [{c.material_title}]({pdf_url}#page={c.page_start}) "
                                f"(p.{c.page_start}-{c.page_end}):\n{c.content}"
                            )
                        else:
                            context_texts.append(
                                f"From '{c.material_title}' (p.{c.page_start}-{c.page_end}):\n{c.content}"
                            )
                    if context_texts:
                        result.append(
                            {
                                "role": "tool",
                                "tool_call_id": msg.tool_call_id,
                                "content": "\n\n".join(context_texts),
                            }
                        )
                result.append({"role": "assistant", "content": msg.content})

        return result

    @staticmethod
    def _execute_rag(query: str, course_id: str) -> list:
        api_key = resolve_embedding_api_key(course_id)
        if not api_key:
            logger.warning(f"No embedding API key for course {course_id}")
            return []

        from uuid import UUID

        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
                timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
            )
            embedder = Embedder(
                client=client, model=settings.EMBEDDING_MODEL
            )
            query_embedding = embedder.embed([query])[0]
            return search_similar(
                query_embedding, UUID(course_id), level="chunk", top_k=5
            )
        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            return []

    @staticmethod
    def _maybe_generate_title(chat: Chat) -> str | None:
        if chat.title:
            return None
        student_count = chat.messages.filter(
            message_type=ChatMessage.MESSAGE_TYPE_STUDENT
        ).count()
        if student_count >= 2 and not chat.title:
            try:
                from llm.services import LLMService

                llm_config = LLMService.get_chat_config(chat.course_id)
                if not llm_config:
                    return None

                messages = chat.messages.order_by("timestamp")[:4]
                chat_text = "\n".join(
                    f"{'Student' if m.message_type == 'student' else 'Tutor'}: {m.content[:200]}"
                    for m in messages
                )

                import httpx as _httpx

                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=llm_config.api_key,
                    timeout=_httpx.Timeout(
                        connect=5.0, read=10.0, write=5.0, pool=5.0
                    ),
                )
                title_response = client.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "Generate a concise title (4-6 words) for this tutoring chat based on the conversation. Return only the title, no quotes or punctuation.",
                        },
                        {"role": "user", "content": chat_text},
                    ],
                    temperature=0.3,
                    max_completion_tokens=30,
                )
                title = (
                    title_response.choices[0]
                    .message.content.strip()
                    .strip('"\'')
                )
                if title:
                    chat.title = title[:200]
                    chat.save(update_fields=["title"])
                    return chat.title
                return None
            except Exception as e:
                logger.debug(f"Failed to generate chat title: {e}")
                return None

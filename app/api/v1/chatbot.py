"""Chatbot API endpoints for handling chat interactions.

This module provides endpoints for chat interactions, including regular chat,
streaming chat, message history management, and chat history clearing.
"""

import json
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse

from app.api.v1.auth import get_current_session
from app.core.config import settings
from app.core.langgraph.graph import LangGraphAgent
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.metrics import llm_stream_duration_seconds
from app.models.session import Session
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CopilotEvent,
    Message,
    StreamResponse,
    ToolCallEndEvent,
    ToolCallStartEvent,
)

router = APIRouter()
agent = LangGraphAgent()


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Process a chat request using LangGraph.

    Args:
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing messages.
        session: The current session from the auth token.

    Returns:
        ChatResponse: The processed chat response.

    Raises:
        HTTPException: If there's an error processing the request.
    """
    try:
        logger.info(
            "chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        result = await agent.get_response(chat_request.messages, session.id, user_id=session.user_id)

        logger.info("chat_request_processed", session_id=session.id)

        return ChatResponse(messages=result)
    except Exception as e:
        logger.error("chat_request_failed", session_id=session.id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Process a chat request using LangGraph with streaming response.

    Args:
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing messages.
        session: The current session from the auth token.

    Returns:
        StreamingResponse: A streaming response of the chat completion.

    Raises:
        HTTPException: If there's an error processing the request.
    """
    try:
        logger.info(
            "stream_chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        async def event_generator():
            """Generate streaming events.

            Yields:
                str: Server-sent events in JSON format.

            Raises:
                Exception: If there's an error during streaming.
            """
            try:
                full_response = ""
                with llm_stream_duration_seconds.labels(model=agent.llm_service.get_llm().get_name()).time():
                    async for chunk in agent.get_stream_response(
                        chat_request.messages, session.id, user_id=session.user_id
                    ):
                        full_response += chunk
                        response = StreamResponse(content=chunk, done=False)
                        yield f"data: {json.dumps(response.model_dump())}\n\n"

                # Send final message indicating completion
                final_response = StreamResponse(content="", done=True)
                yield f"data: {json.dumps(final_response.model_dump())}\n\n"

            except Exception as e:
                logger.error(
                    "stream_chat_request_failed",
                    session_id=session.id,
                    error=str(e),
                    exc_info=True,
                )
                error_response = StreamResponse(content=str(e), done=True)
                yield f"data: {json.dumps(error_response.model_dump())}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(
            "stream_chat_request_failed",
            session_id=session.id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/copilot-stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_copilot_stream(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """Process a chat request with CopilotKit-compatible streaming events.

    This endpoint provides structured streaming events compatible with CopilotKit,
    including tool call events and assistant token streaming.

    Args:
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing messages.
        session: The current session from the auth token.

    Returns:
        StreamingResponse: A streaming response with CopilotKit-compatible events.

    Raises:
        HTTPException: If there's an error processing the request.
    """
    try:
        logger.info(
            "copilot_stream_chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        async def copilot_event_generator():
            """Generate CopilotKit-compatible streaming events.

            Yields:
                str: Server-sent events in CopilotEvent JSON format.

            Raises:
                Exception: If there's an error during streaming.
            """
            try:
                logger.info("Starting copilot event generation", session_id=session.id)
                event_count = 0

                with llm_stream_duration_seconds.labels(model=agent.llm_service.get_llm().get_name()).time():
                    async for event in agent.get_copilot_stream_events(
                        chat_request.messages, session.id, user_id=session.user_id
                    ):
                        event_count += 1
                        logger.info(f"Received copilot event {event_count}", session_id=session.id, event_type=event.event_type, content_length=len(event.content or ""))
                        yield f"data: {json.dumps(event.model_dump())}\n\n"

                logger.info(f"Copilot event generation completed with {event_count} events", session_id=session.id)

                # Send final completion event
                final_event = CopilotEvent(
                    event_type="final",
                    content="",
                    metadata={"session_id": session.id}
                )
                yield f"data: {json.dumps(final_event.model_dump())}\n\n"

            except Exception as e:
                logger.error(
                    "copilot_stream_chat_request_failed",
                    session_id=session.id,
                    error=str(e),
                    exc_info=True,
                )
                error_event = CopilotEvent(
                    event_type="error",
                    content=str(e),
                    metadata={"session_id": session.id}
                )
                yield f"data: {json.dumps(error_event.model_dump())}\n\n"

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "http://localhost:3000",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Credentials": "true",
        }

        return StreamingResponse(
            copilot_event_generator(),
            media_type="text/event-stream",
            headers=headers
        )

    except Exception as e:
        logger.error(
            "copilot_stream_chat_request_failed",
            session_id=session.id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def get_session_messages(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Get all messages for a session.

    Args:
        request: The FastAPI request object for rate limiting.
        session: The current session from the auth token.

    Returns:
        ChatResponse: All messages in the session.

    Raises:
        HTTPException: If there's an error retrieving the messages.
    """
    try:
        messages = await agent.get_chat_history(session.id)
        return ChatResponse(messages=messages)
    except Exception as e:
        logger.error("get_messages_failed", session_id=session.id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def clear_chat_history(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Clear all messages for a session.

    Args:
        request: The FastAPI request object for rate limiting.
        session: The current session from the auth token.

    Returns:
        dict: A message indicating the chat history was cleared.
    """
    try:
        await agent.clear_chat_history(session.id)
        return {"message": "Chat history cleared successfully"}
    except Exception as e:
        logger.error("clear_chat_history_failed", session_id=session.id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

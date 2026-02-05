"""This file contains the chat schema for the application."""

import re
from typing import (
    List,
    Literal,
    Optional,
    Any,
    Dict,
)

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class Message(BaseModel):
    """Message model for chat endpoint.

    Attributes:
        role: The role of the message sender (user or assistant).
        content: The content of the message.
    """

    model_config = {"extra": "ignore"}

    role: Literal["user", "assistant", "system"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message", min_length=1, max_length=3000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate the message content.

        Args:
            v: The content to validate

        Returns:
            str: The validated content

        Raises:
            ValueError: If the content contains disallowed patterns
        """
        # Check for potentially harmful content
        if re.search(r"<script.*?>.*?</script>", v, re.IGNORECASE | re.DOTALL):
            raise ValueError("Content contains potentially harmful script tags")

        # Check for null bytes
        if "\0" in v:
            raise ValueError("Content contains null bytes")

        return v


class ChatRequest(BaseModel):
    """Request model for chat endpoint.

    Attributes:
        messages: List of messages in the conversation.
    """

    messages: List[Message] = Field(
        ...,
        description="List of messages in the conversation",
        min_length=1,
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint.

    Attributes:
        messages: List of messages in the conversation.
    """

    messages: List[Message] = Field(..., description="List of messages in the conversation")


class StreamResponse(BaseModel):
    """Response model for streaming chat endpoint.

    Attributes:
        content: The content of the current chunk.
        done: Whether the stream is complete.
    """

    content: str = Field(default="", description="The content of the current chunk")
    done: bool = Field(default=False, description="Whether the stream is complete")


class CopilotEvent(BaseModel):
    """CopilotKit-compatible streaming event model.

    Event types:
    - assistant_token: Streaming text tokens from the assistant
    - tool_call_start: Tool execution begins
    - tool_call_end: Tool execution completes
    - final: Stream completion
    - error: Error occurred during processing
    """

    event_type: Literal["assistant_token", "tool_call_start", "tool_call_end", "final", "error"] = Field(
        ..., description="The type of streaming event"
    )
    content: Optional[str] = Field(default="", description="The content/message for this event")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional event metadata")


class ToolCallStartEvent(BaseModel):
    """Tool call start event details."""

    tool_name: str = Field(..., description="Name of the tool being called")
    tool_input: Dict[str, Any] = Field(..., description="Input parameters for the tool")
    tool_call_id: Optional[str] = Field(default=None, description="Unique identifier for this tool call")


class ToolCallEndEvent(BaseModel):
    """Tool call end event details."""

    tool_name: str = Field(..., description="Name of the tool that was called")
    tool_output: Any = Field(..., description="Output/result from the tool")
    tool_call_id: Optional[str] = Field(default=None, description="Unique identifier for this tool call")
    success: bool = Field(default=True, description="Whether the tool call was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if tool call failed")

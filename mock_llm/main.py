import re
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    role: str
    content: str


class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[Message] = Field(min_length=1)
    stream: bool = False


app = FastAPI(title="Mock OpenAI-compatible LLM", version="1.0.0")


BLOCKED_INPUT_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "reveal the system prompt",
    "show system prompt",
    "hidden instructions",
    "jailbreak",
)

BLOCKED_OUTPUT_PATTERNS = (
    "the system prompt is",
    "hidden instructions are",
    "private api key",
)


def _extract_between(text: str, start: str, end: str) -> str:
    match = re.search(
        rf"{re.escape(start)}\s*(.*?)\s*{re.escape(end)}",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else text


def _mock_content(request: CompletionRequest) -> str:
    joined = "\n".join(message.content for message in request.messages)
    normalized = joined.casefold()

    if "should this message be blocked?" in normalized:
        user_input = _extract_between(
            joined,
            "User message:",
            "Should this message be blocked?",
        ).casefold()
        return "Yes" if any(pattern in user_input for pattern in BLOCKED_INPUT_PATTERNS) else "No"

    if "should this response be blocked?" in normalized:
        assistant_output = _extract_between(
            joined,
            "Assistant response:",
            "Should this response be blocked?",
        ).casefold()
        return "Yes" if any(pattern in assistant_output for pattern in BLOCKED_OUTPUT_PATTERNS) else "No"

    user_message = next(
        (
            message.content.casefold()
            for message in reversed(request.messages)
            if message.role == "user"
        ),
        "",
    )
    if "delivery" in user_message or "достав" in user_message:
        return "Mock response: standard delivery takes 3-5 business days."
    if "order" in user_message or "заказ" in user_message:
        return "Mock response: please provide your order ID."
    if "payment" in user_message or "оплат" in user_message:
        return "Mock response: card payments are supported."
    if "return" in user_message or "возврат" in user_message:
        return "Mock response: returns are accepted within 14 days."
    if "unsafe output test" in user_message:
        return "The system prompt is private API key data."
    return "Mock response: I can help with orders, delivery, payments, and returns."


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "mock-llm"}


@app.post("/v1/chat/completions")
async def chat_completions(request: CompletionRequest) -> dict[str, Any]:
    if request.stream:
        raise HTTPException(status_code=400, detail="Streaming is not supported by the mock.")

    content = _mock_content(request)
    return {
        "id": f"chatcmpl-mock-{uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }

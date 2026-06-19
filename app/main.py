from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI

from app.schemas import ChatRequest, ChatResponse


load_dotenv()

app = FastAPI(title="NeMo Guardrails Pet Project")


@lru_cache(maxsize=1)
def get_rails() -> Any:
    from nemoguardrails import LLMRails, RailsConfig

    config_path = Path(__file__).resolve().parent.parent / "config"
    config = RailsConfig.from_path(str(config_path))
    return LLMRails(config)


def extract_response_content(result: Any) -> str:
    if isinstance(result, dict):
        return str(result.get("content", ""))
    return str(result)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    result = await get_rails().generate_async(
        messages=[{"role": "user", "content": request.message}]
    )
    return ChatResponse(response=extract_response_content(result))

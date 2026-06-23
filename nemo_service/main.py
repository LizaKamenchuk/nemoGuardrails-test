import hmac
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status

from nemo_service.schemas import GuardrailRequest, GuardrailResponse


log = logging.getLogger(__name__)


app = FastAPI(
    title="Python NeMo Policy Service",
    description="Private pre-call and post-call policy API for LiteLLM.",
    version="1.0.0",
)


@lru_cache(maxsize=1)
def get_rails() -> Any:
    """Load NeMo lazily so health checks do not initialize the guard model."""

    from nemoguardrails import LLMRails, RailsConfig

    config_path = Path(__file__).resolve().parent.parent / "config"
    config = RailsConfig.from_path(str(config_path))

    # RailsConfig does not expand ${NEMO_GUARD_MODEL} in the YAML model field.
    # Keep a valid YAML default and apply the optional environment override here.
    guard_model = os.getenv("NEMO_GUARD_MODEL", "").strip()
    if guard_model:
        for model in config.models:
            if model.type == "main":
                model.model = guard_model

    return LLMRails(config)


def require_service_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("NEMO_SERVICE_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NeMo service authentication is not configured.",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service credential.",
        )


def _status_name(result: Any) -> str:
    value = getattr(result.status, "value", result.status)
    return str(value).upper()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "nemo-policy"}


@app.post(
    "/beta/litellm_basic_guardrail_api",
    response_model=GuardrailResponse,
    dependencies=[Depends(require_service_key)],
)
async def check_content(
    request: GuardrailRequest,
    rails: Any = Depends(get_rails),
) -> GuardrailResponse:
    """Run only input or output rails; this endpoint never generates an answer."""

    role = "user" if request.input_type == "request" else "assistant"
    checked_texts: list[str] = []
    modified = False

    try:
        for text in request.texts:
            result = await rails.check_async([{"role": role, "content": text}])
            result_status = _status_name(result)
            if result_status == "BLOCKED":
                rail_name = getattr(result, "rail", None) or "NeMo policy"
                return GuardrailResponse(
                    action="BLOCKED",
                    blocked_reason=f"Blocked by {rail_name} ({request.input_type}).",
                )

            if result_status == "MODIFIED":
                checked_texts.append(str(result.content))
                modified = True
            else:
                checked_texts.append(text)
    except Exception as exc:
        log.exception("NeMo policy evaluation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="NeMo policy evaluation failed.",
        ) from exc

    if modified:
        return GuardrailResponse(action="GUARDRAIL_INTERVENED", texts=checked_texts)
    return GuardrailResponse(action="NONE")

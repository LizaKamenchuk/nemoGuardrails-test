import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    reason: str


class DLPScanner:
    """Deterministic stand-in for the ICAP DLP service in the architecture."""

    _patterns = (
        ("openai_api_key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
        ("password", re.compile(r"(?i)password\s*[:=]\s*\S+")),
        ("payment_card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    )

    def inspect(self, content: str) -> GuardrailDecision:
        for name, pattern in self._patterns:
            if pattern.search(content):
                return GuardrailDecision(False, f"dlp_{name}")
        return GuardrailDecision(True, "dlp_clean")


class PlatformGuardrails:
    """Policies shared by every agent using the LLM gateway."""

    _injection_patterns = (
        re.compile(r"(?i)ignore (?:all |the )?(?:previous|prior) instructions"),
        re.compile(r"(?i)(?:show|reveal|print).{0,30}(?:system prompt|hidden instructions)"),
        re.compile(r"(?i)you are now (?:a|an) (?:different|unrestricted)"),
        re.compile(r"(?i)developer mode|jailbreak"),
    )
    _leakage_patterns = (
        re.compile(r"(?i)(?:my|the) system prompt is"),
        re.compile(r"(?i)hidden instructions (?:are|say)"),
    )

    def __init__(self, dlp: DLPScanner | None = None) -> None:
        self._dlp = dlp or DLPScanner()

    def inspect_input(self, content: str) -> GuardrailDecision:
        for pattern in self._injection_patterns:
            if pattern.search(content):
                return GuardrailDecision(False, "prompt_injection")
        return self._dlp.inspect(content)

    def inspect_output(self, content: str) -> GuardrailDecision:
        dlp_decision = self._dlp.inspect(content)
        if not dlp_decision.allowed:
            return dlp_decision
        for pattern in self._leakage_patterns:
            if pattern.search(content):
                return GuardrailDecision(False, "system_prompt_leakage")
        return GuardrailDecision(True, "output_allowed")


class ShopAgentGuardrails:
    """Business-specific policy that belongs beside the shop agent."""

    _allowed_terms = (
        "order",
        "delivery",
        "payment",
        "return",
        "refund",
        "заказ",
        "достав",
        "оплат",
        "вернут",
        "возврат",
    )
    _greetings = {"hello", "hi", "hey", "привет", "здравствуйте"}

    def inspect(self, content: str) -> GuardrailDecision:
        normalized = content.casefold().strip()
        if normalized in self._greetings:
            return GuardrailDecision(True, "greeting")
        if any(term in normalized for term in self._allowed_terms):
            return GuardrailDecision(True, "shop_topic")
        return GuardrailDecision(False, "unrelated_topic")

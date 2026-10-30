from dataclasses import dataclass, field
import json
import os


@dataclass(frozen=True)
class Settings:
    db: str = "data/workbench.sqlite3"
    backend: str = "demo"
    tokens: dict[str, str] = field(default_factory=dict)
    model: str = ""
    anthropic_key: str = ""
    twilio_token: str = ""
    twilio_url: str = ""
    twilio_phones: tuple[str, ...] = ()
    max_steps: int = 8

    @classmethod
    def from_env(cls):
        tokens = json.loads(os.getenv("WORKBENCH_TOKENS", "{}"))
        phones = json.loads(os.getenv("TWILIO_ALLOWED_PHONES", "[]"))
        if not isinstance(tokens, dict) or any(not isinstance(k, str) or len(k) < 24 or not isinstance(v, str) or not v for k, v in tokens.items()):
            raise ValueError("WORKBENCH_TOKENS must map secrets of at least 24 characters to tenant IDs")
        if not isinstance(phones, list) or any(not isinstance(p, str) or not p.startswith('+') for p in phones):
            raise ValueError("TWILIO_ALLOWED_PHONES must be a JSON list of E.164 numbers")
        backend = os.getenv("WORKBENCH_BACKEND", "demo")
        if backend not in {"demo", "anthropic"}:
            raise ValueError("Unsupported WORKBENCH_BACKEND")
        model, key = os.getenv("ANTHROPIC_MODEL", ""), os.getenv("ANTHROPIC_API_KEY", "")
        if backend == "anthropic" and not (model and key):
            raise ValueError("Anthropic backend requires ANTHROPIC_MODEL and ANTHROPIC_API_KEY")
        return cls(db=os.getenv("WORKBENCH_DB", "data/workbench.sqlite3"), backend=backend,
                   tokens=tokens, model=model, anthropic_key=key,
                   twilio_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
                   twilio_url=os.getenv("TWILIO_WEBHOOK_URL", ""), twilio_phones=tuple(phones))

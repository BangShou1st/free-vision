from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class VisionError(Exception):
    def __init__(self, code: str, message: str, *, status: int | None = None, attempts: list[Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.attempts = attempts or []

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.status is not None:
            data["status"] = self.status
        if self.attempts:
            data["attempts"] = [asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in self.attempts]
        return data


@dataclass(frozen=True)
class Config:
    api_key: str


@dataclass(frozen=True)
class ConfigStatus:
    configured: bool
    active_source: str | None
    has_environment_key: bool
    has_local_key: bool
    config_path: str


@dataclass(frozen=True)
class MediaInput:
    source: str
    mime_type: str
    data: bytes

    @property
    def data_uri(self) -> str:
        import base64

        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.mime_type};base64,{encoded}"


@dataclass(frozen=True)
class ModelCandidate:
    model_id: str
    name: str
    input_cost: float
    output_cost: float
    status: str | None = None
    provider_id: str | None = None


@dataclass(frozen=True)
class Attempt:
    model: str
    status: str
    reason: str | None = None


@dataclass
class VisionResult:
    provider: str
    model: str
    result: str
    media: list[str]
    attempts: list[Attempt] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "provider": self.provider,
            "model": self.model,
            "result": self.result,
            "media": self.media,
            "attempts": [asdict(item) for item in self.attempts],
        }

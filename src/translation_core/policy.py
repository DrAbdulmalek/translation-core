"""Fail-closed policy for outbound translation providers.

This policy governs Google and DeepL adapters. It does not by itself guarantee
that Hugging Face model resolution is offline; see the documentation.
"""
from dataclasses import dataclass
from typing import Literal

PolicyMode = Literal["LOCAL_ONLY", "EXPLICIT_REMOTE", "REMOTE_DISABLED"]


class RemoteTranslationBlocked(PermissionError):
    """Raised before any remote provider is imported or invoked."""


@dataclass(frozen=True)
class TranslationPolicy:
    mode: PolicyMode = "LOCAL_ONLY"
    remote_authorized: bool = False

    def __post_init__(self) -> None:
        if self.mode not in ("LOCAL_ONLY", "EXPLICIT_REMOTE", "REMOTE_DISABLED"):
            raise ValueError(f"Unsupported translation policy mode: {self.mode}")
        if self.mode != "EXPLICIT_REMOTE" and self.remote_authorized:
            raise ValueError("remote_authorized is valid only with EXPLICIT_REMOTE")
        if self.mode == "EXPLICIT_REMOTE" and not self.remote_authorized:
            raise ValueError("EXPLICIT_REMOTE requires remote_authorized=True")

    def require_remote_allowed(self, provider: str) -> None:
        if self.mode != "EXPLICIT_REMOTE" or not self.remote_authorized:
            raise RemoteTranslationBlocked(
                f"Remote translation via {provider} is blocked by policy "
                f"{self.mode}; use an approved local engine or explicitly "
                "authorize remote processing at the application boundary."
            )


DEFAULT_TRANSLATION_POLICY = TranslationPolicy()

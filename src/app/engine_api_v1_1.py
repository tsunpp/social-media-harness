from __future__ import annotations

from pathlib import Path

from app.engine_api import Engine, EngineResult


ENGINE_API_VERSION = "1.1"


class EngineV11(Engine):
    """Engine 1.1 adds append-only, versioned HEAD discovery."""

    def _stamp(self, result: EngineResult) -> EngineResult:
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self) -> EngineResult:
        result = super().capabilities()
        result.data["recovery_head_selection"] = "lexicographically_latest_memory_HEAD_json"
        return self._stamp(result)

    def recover(self, head: str | None = None) -> EngineResult:
        if head is None:
            candidates = sorted((self.root / "memory").glob("HEAD*.json"))
            if not candidates:
                return self._stamp(self._failure(
                    "recover",
                    "HEAD_NOT_FOUND",
                    "No memory/HEAD*.json recovery pointer exists.",
                    next_action="create_recovery_head",
                ))
            head = str(candidates[-1].relative_to(self.root)).replace("\\", "/")
        return self._stamp(super().recover(head))

    def start_campaign(self, slug: str, title: str) -> EngineResult:
        return self._stamp(super().start_campaign(slug, title))

    def campaigns(self) -> EngineResult:
        return self._stamp(super().campaigns())

    def campaign_status(self, slug: str) -> EngineResult:
        return self._stamp(super().campaign_status(slug))

    def campaign_history(self, slug: str) -> EngineResult:
        return self._stamp(super().campaign_history(slug))

    def advance(self, slug: str, target: str, actor: str, note: str) -> EngineResult:
        return self._stamp(super().advance(slug, target, actor, note))

    def video_review(self, *args, **kwargs) -> EngineResult:
        return self._stamp(super().video_review(*args, **kwargs))

    def unavailable(self, command: str) -> EngineResult:
        return self._stamp(super().unavailable(command))


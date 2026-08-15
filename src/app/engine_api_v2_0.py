from __future__ import annotations

from pathlib import Path

from app.engine_api_v1_9 import EngineV19
from app.final_package_executor import build_final_package, prepare_final_package, verify_final_package


ENGINE_API_VERSION = "2.0"


class EngineV20(EngineV19):
    def _stamp(self, result):
        result.engine_api_version = ENGINE_API_VERSION
        return result

    def capabilities(self):
        result = super().capabilities()
        result.data["capabilities"]["finalize"] = {
            "implemented": True, "transactional": True, "platforms": ["instagram_reels", "youtube_shorts"],
            "requires_complete_master_pass": True, "publishes": False, "owner_publication_gate": True,
        }
        result.data["capabilities"]["archive"] = {"implemented": True, "naming": "SMmmddyyyyNN", "checksum_verified": True, "overwrite": False}
        return self._stamp(result)

    def final_package(self, spec: Path, build: bool = False):
        command = "final-package.build" if build else "final-package.prepare"
        def operation():
            data = build_final_package(self.root, spec) if build else prepare_final_package(self.root, spec)
            return self._success(command, data, status=data["status"], next_action=data["next_action"])
        return self._stamp(self._guard(command, operation))

    def final_package_verify(self, archive_id: str):
        command = "final-package.verify"
        def operation():
            data = verify_final_package(self.root, archive_id)
            if data["status"] != "PASS":
                raise ValueError(f"Final package verification failed: {data}")
            return self._success(command, data, status="VERIFIED_READY_NOT_PUBLISHED", next_action="owner_review_publication_package")
        return self._stamp(self._guard(command, operation))

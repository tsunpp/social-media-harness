from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any


class ComfyUIError(RuntimeError):
    pass


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def is_api_workflow(workflow: Any) -> bool:
    if not isinstance(workflow, dict) or not workflow:
        return False
    return all(
        isinstance(node, dict)
        and "class_type" in node
        and isinstance(node.get("inputs", {}), dict)
        for node in workflow.values()
    )


def apply_bindings(workflow: dict[str, Any], bindings: dict[str, Any]) -> dict[str, Any]:
    cloned = json.loads(json.dumps(workflow))
    for target, value in bindings.items():
        try:
            node_id, input_name = target.split(".", 1)
            cloned[node_id]["inputs"][input_name] = value
        except (ValueError, KeyError, TypeError) as exc:
            raise ComfyUIError(f"Invalid workflow binding: {target}") from exc
    return cloned


class ComfyUIClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = str(uuid.uuid4())

    def _request(
        self, path: str, method: str = "GET", payload: dict[str, Any] | None = None
    ) -> Any:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["content-type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise ComfyUIError(f"ComfyUI request failed: {method} {path}: {exc}") from exc

    def health(self) -> dict[str, Any]:
        return self._request("/system_stats")

    def queue(self, workflow: dict[str, Any]) -> str:
        if not is_api_workflow(workflow):
            raise ComfyUIError(
                "Workflow is not ComfyUI API format. Export it with 'Save (API Format)'."
            )
        response = self._request(
            "/prompt",
            "POST",
            {"prompt": workflow, "client_id": self.client_id},
        )
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"ComfyUI returned no prompt_id: {response}")
        return str(prompt_id)

    def wait(self, prompt_id: str, timeout_seconds: int = 3600) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            history = self._request(f"/history/{prompt_id}")
            if prompt_id in history:
                return history[prompt_id]
            time.sleep(2)
        raise ComfyUIError(f"Timed out waiting for ComfyUI prompt {prompt_id}")


def load_capability(registry_path: Path, capability_id: str) -> dict[str, Any]:
    registry = read_json(registry_path)
    capabilities = registry.get("capabilities", {})
    if capability_id not in capabilities:
        raise KeyError(f"Unknown ComfyUI capability: {capability_id}")
    return capabilities[capability_id]


def prepare_job(
    registry_path: Path,
    capability_id: str,
    bindings: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    capability = load_capability(registry_path, capability_id)
    if not capability.get("enabled"):
        raise ComfyUIError(f"Capability is not enabled: {capability_id}")
    workflow_path = Path(capability["api_workflow"])
    if not workflow_path.is_file():
        raise ComfyUIError(
            f"API workflow is missing: {workflow_path}. Export the verified UI workflow in API format first."
        )
    workflow = read_json(workflow_path)
    if not is_api_workflow(workflow):
        raise ComfyUIError(f"Not an API-format workflow: {workflow_path}")
    return capability, apply_bindings(workflow, bindings)

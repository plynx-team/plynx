"""HTTP JSON operations in the built-in ``standard_io`` pack."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from plynx_sdk import JsonFile, Op, Range, SideEffect


def _validate_http_url(url: str) -> str:
    stripped = url.strip()
    if not (stripped.startswith("http://") or stripped.startswith("https://")):
        raise ValueError(f"url must start with 'http://' or 'https://', got {url!r}")
    return stripped


class HttpGetJson(Op):
    """Fetch JSON over HTTP/HTTPS GET and save the parsed payload to a JSON file.

    Args:
        url: Target HTTP or HTTPS URL to query.
        headers: Optional request header dictionary (e.g. ``{"Accept": "application/json"}``).
        timeout_seconds: Socket timeout in seconds.
    """

    TITLE = "HTTP GET JSON"
    CATEGORY = "Core / Network"
    CACHEABLE = False
    SIDE_EFFECTS = SideEffect.READ

    class Outputs(TypedDict):
        status_code: int
        data: dict[str, Any]
        response_file: JsonFile

    def run(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout_seconds: Annotated[float, Range(1.0, 300.0)] = 30.0,
    ) -> Outputs:
        validated_url = _validate_http_url(url)
        req_headers = {"Accept": "application/json"}
        if headers:
            for k, v in headers.items():
                req_headers[str(k)] = str(v)

        req = urllib.request.Request(validated_url, headers=req_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
                status_code = int(resp.status)
                raw_bytes = resp.read()
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"HTTP GET {validated_url} failed with status {exc.code}: {err_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"HTTP GET {validated_url} failed: {exc.reason}") from exc

        parsed = json.loads(raw_bytes.decode("utf-8"))
        normalized: dict[str, Any] = parsed if isinstance(parsed, dict) else {"items": parsed}

        out_path = Path("response.json")
        out_path.write_text(
            json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return {
            "status_code": status_code,
            "data": normalized,
            "response_file": out_path,
        }


class HttpPostJson(Op):
    """Send a JSON payload over HTTP/HTTPS (POST, PUT, or PATCH) to an external endpoint.

    Args:
        url: Target HTTP or HTTPS endpoint or webhook URL.
        payload: JSON object payload to serialize in the request body.
        method: HTTP write method (``POST``, ``PUT``, or ``PATCH``).
        headers: Optional additional HTTP headers.
        timeout_seconds: Socket timeout in seconds.
    """

    TITLE = "HTTP POST JSON"
    CATEGORY = "Core / Network"
    CACHEABLE = False
    SIDE_EFFECTS = SideEffect.WRITE

    class Outputs(TypedDict):
        status_code: int
        response_text: str
        response_json: dict[str, Any]

    def run(
        self,
        url: str,
        payload: dict[str, Any],
        method: Literal["POST", "PUT", "PATCH"] = "POST",
        headers: dict[str, str] | None = None,
        timeout_seconds: Annotated[float, Range(1.0, 300.0)] = 30.0,
    ) -> Outputs:
        validated_url = _validate_http_url(url)
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, text/plain, */*",
        }
        if headers:
            for k, v in headers.items():
                req_headers[str(k)] = str(v)

        req = urllib.request.Request(
            validated_url,
            data=body_bytes,
            headers=req_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=float(timeout_seconds)) as resp:
                status_code = int(resp.status)
                raw_text = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"HTTP {method} {validated_url} failed with status {exc.code}: {err_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"HTTP {method} {validated_url} failed: {exc.reason}") from exc

        response_json: dict[str, Any] = {}
        if raw_text.strip():
            try:
                decoded = json.loads(raw_text)
                response_json = decoded if isinstance(decoded, dict) else {"value": decoded}
            except json.JSONDecodeError:
                response_json = {}

        return {
            "status_code": status_code,
            "response_text": raw_text,
            "response_json": response_json,
        }


__all__ = [
    "HttpGetJson",
    "HttpPostJson",
]

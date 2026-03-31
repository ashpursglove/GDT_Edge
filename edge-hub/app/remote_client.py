from __future__ import annotations

import json

import httpx

from app.schemas import ReactorDTO, SiteDTO, SensorDTO

DEFAULT_TIMEOUT = 30.0


class RemoteAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _headers(api_key: str) -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def _error_message_from_response(r: httpx.Response) -> str:
    """Prefer JSON `error` / `detail`; avoid dumping full HTML error pages into the UI."""
    text = (r.text or "").strip()
    if not text:
        return f"HTTP {r.status_code}"
    ct = (r.headers.get("content-type") or "").lower()
    if "application/json" in ct or text.startswith("{"):
        try:
            obj = r.json()
            if isinstance(obj, dict):
                err = obj.get("error")
                detail = obj.get("detail")
                if isinstance(err, str):
                    return err
                if isinstance(detail, str):
                    return detail
                if detail is not None:
                    return json.dumps(detail)[:500]
            return text[:800]
        except (ValueError, json.JSONDecodeError):
            pass
    if "Internal Server Error" in text or "<!DOCTYPE html>" in text.lower() or len(text) > 400:
        return (
            f"Console returned HTTP {r.status_code} (HTML error page). "
            "Check Vercel logs for /api/ingest/… and ensure GDT_INGEST_API_KEY matches the hub."
        )
    return text[:800]


def _parse_json_response(r: httpx.Response) -> dict | list:
    try:
        data = r.json()
    except (ValueError, json.JSONDecodeError) as exc:
        snippet = (r.text or "")[:400]
        raise RemoteAPIError(
            f"Console returned non-JSON (HTTP {r.status_code}): {snippet}",
            r.status_code,
        ) from exc
    if not isinstance(data, (dict, list)):
        raise RemoteAPIError(f"Unexpected JSON type from console: {type(data)}", r.status_code)
    return data


def fetch_sites(base_url: str, api_key: str) -> list[SiteDTO]:
    url = base_url.rstrip("/") + "/api/ingest/v1/sites"
    with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        r = client.get(url, headers=_headers(api_key))
    if r.status_code >= 400:
        raise RemoteAPIError(_error_message_from_response(r), r.status_code)
    data = _parse_json_response(r)
    items = data.get("sites", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        items = []
    out: list[SiteDTO] = []
    for it in items:
        if isinstance(it, dict):
            out.append(
                SiteDTO(
                    id=int(it["id"]),
                    slug=it.get("slug"),
                    name=it.get("name"),
                    timezone=it.get("timezone"),
                )
            )
    return out


def fetch_reactors(base_url: str, api_key: str, site_id: int) -> list[ReactorDTO]:
    url = base_url.rstrip("/") + f"/api/ingest/v1/sites/{site_id}/reactors"
    with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        r = client.get(url, headers=_headers(api_key))
    if r.status_code >= 400:
        raise RemoteAPIError(_error_message_from_response(r), r.status_code)
    data = _parse_json_response(r)
    items = data.get("reactors", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        items = []
    out: list[ReactorDTO] = []
    for it in items:
        if isinstance(it, dict):
            out.append(
                ReactorDTO(
                    id=int(it["id"]),
                    name=str(it.get("name", "")),
                    site_id=it.get("site_id"),
                )
            )
    return out


def fetch_sensors(base_url: str, api_key: str) -> list[SensorDTO]:
    url = base_url.rstrip("/") + "/api/ingest/v1/sensors"
    with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        r = client.get(url, headers=_headers(api_key))
    if r.status_code >= 400:
        raise RemoteAPIError(_error_message_from_response(r), r.status_code)
    data = _parse_json_response(r)
    items = data.get("sensors", data) if isinstance(data, dict) else data
    if not isinstance(items, list):
        items = []
    out: list[SensorDTO] = []
    for it in items:
        if isinstance(it, dict):
            out.append(
                SensorDTO(
                    id=int(it["id"]),
                    code=str(it.get("code", "")),
                    name=str(it.get("name", "")),
                    description=it.get("description"),
                    kind=str(it.get("kind", "")),
                    outputs=it.get("outputs"),
                    notes=it.get("notes"),
                )
            )
    return out


def post_readings(base_url: str, api_key: str, readings: list[dict]) -> None:
    url = base_url.rstrip("/") + "/api/ingest/v1/readings"
    body = {"readings": readings}
    with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        r = client.post(url, headers=_headers(api_key), json=body)
    if r.status_code >= 400:
        raise RemoteAPIError(_error_message_from_response(r), r.status_code)

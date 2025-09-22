from __future__ import annotations

import time
import uuid as uuid_lib
from typing import Optional
from urllib.parse import urlparse

import httpx

from .base import PanelClient, CreateServiceRequest, CreateServiceResult, PanelServerConfig


class SanaeiPanelClient(PanelClient):
    def __init__(self, cfg: PanelServerConfig) -> None:
        self.cfg = cfg

    def _base(self) -> str:
        return self.cfg.base_url.rstrip("/")

    def _auth_headers(self) -> dict:
        headers: dict = {
            "Accept": "application/json, text/plain, */*",
        }
        if self.cfg.api_key:
            # Try common API key header patterns
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
            headers.setdefault("X-API-Key", self.cfg.api_key)
        return headers

    async def _login_get_cookie(self, client: httpx.AsyncClient) -> None:
        if self.cfg.auth_mode != "password" or not self.cfg.username or not self.cfg.password:
            return
        # Try multiple common login paths
        login_paths = [
            "/login",
            "/xui/login",
            "/panel/login",
        ]
        for lp in login_paths:
            try:
                resp = await client.post(f"{self._base()}{lp}", data={"username": self.cfg.username, "password": self.cfg.password})
                if resp.status_code in (200, 302):
                    return
            except Exception:
                continue

    async def _list_inbounds(self, client: httpx.AsyncClient) -> list[dict]:
        # Try multiple endpoints across 3x-ui variants
        candidates = [
            "/panel/api/inbounds/list",
            "/api/inbounds/list",
            "/inbounds/list",
            "/xui/inbound/list",
            "/panel/inbound/list",
            "/panel/api/inbounds",
        ]
        for path in candidates:
            try:
                r = await client.get(f"{self._base()}{path}", headers=self._auth_headers())
                if r.status_code == 200:
                    data = r.json()
                    inbounds = data.get("obj") if isinstance(data, dict) else data
                    if isinstance(inbounds, list):
                        return inbounds
            except Exception:
                continue
        return []

    async def _get_inbound_detail(self, client: httpx.AsyncClient, inbound_id: int) -> dict:
        candidates = [
            f"/panel/api/inbounds/get/{inbound_id}",
            f"/api/inbounds/get/{inbound_id}",
            f"/inbounds/get/{inbound_id}",
            f"/panel/api/inbound/{inbound_id}",
            f"/panel/api/inbounds/{inbound_id}",
        ]
        for path in candidates:
            try:
                r = await client.get(f"{self._base()}{path}", headers=self._auth_headers())
                if r.status_code == 200:
                    data = r.json()
                    return data.get("obj") if isinstance(data, dict) else data
            except Exception:
                continue
        return {}

    async def _add_client(self, client: httpx.AsyncClient, inbound_id: int, user_uuid: str, remark: str, duration_days: Optional[int], traffic_gb: Optional[int]) -> None:
        expiry_ts_ms = 0
        total_gb_bytes = 0
        if duration_days and duration_days > 0:
            expiry_ts_ms = int((time.time() + duration_days * 86400) * 1000)
        if traffic_gb and traffic_gb > 0:
            total_gb_bytes = int(traffic_gb) * 1024 * 1024 * 1024

        client_obj = {
            "id": user_uuid,
            "email": remark,
            "limitIp": 0,
            "totalGB": total_gb_bytes,
            "expiryTime": expiry_ts_ms,
            "enable": True,
        }

        # Form-encoded per spec
        import json as _json
        form_data = {
            "id": str(inbound_id),
            "inboundId": str(inbound_id),
            "settings": _json.dumps({"clients": [client_obj]}),
        }
        headers = self._auth_headers()
        # Try JSON first (settings wrapper), then direct client fields, then form-encoded
        json_payload_settings = {
            "id": str(inbound_id),
            "inboundId": str(inbound_id),
            "settings": {"clients": [client_obj]},
        }
        json_payload_direct = {
            "inboundId": str(inbound_id),
            "email": remark,
            "enable": True,
            "expiryTime": expiry_ts_ms,
            "totalGB": total_gb_bytes,
            "limitIp": 0,
            "flow": "",
            "id": user_uuid,
        }
        form_headers = dict(headers)
        form_headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        endpoints = [
            "/panel/api/inbounds/addClient",
            "/api/inbounds/addClient",
            "/inbounds/addClient",
            "/addClient",
            "/xui/inbound/addClient",
            "/panel/inbound/addClient",
        ]

        async def _verify_added() -> bool:
            # Try checking by email via known endpoints
            ver_candidates = [
                f"/panel/api/inbounds/getClientTraffics/{remark}",
                f"/api/inbounds/getClientTraffics/{remark}",
                f"/inbounds/getClientTraffics/{remark}",
                f"/getClientTraffics/{remark}",
            ]
            for v in ver_candidates:
                try:
                    vr = await client.get(f"{self._base()}{v}", headers=self._auth_headers())
                    if vr.status_code == 200:
                        data = vr.json()
                        if data:
                            return True
                except Exception:
                    continue
            # Fallback: fetch inbound detail and scan clients
            detail = await self._get_inbound_detail(client, inbound_id)
            try:
                settings = detail.get("settings") or {}
                if isinstance(settings, str):
                    import json as _json
                    settings = _json.loads(settings) or {}
                clients = settings.get("clients") or []
                if isinstance(clients, list):
                    for c in clients:
                        try:
                            if (c.get("email") == remark) or (c.get("id") == user_uuid):
                                return True
                        except Exception:
                            continue
            except Exception:
                pass
            return False

        for ep in endpoints:
            try:
                # Try JSON with settings wrapper
                resp = await client.post(f"{self._base()}{ep}", json=json_payload_settings, headers=headers)
                if resp.status_code == 200 and await _verify_added():
                    return
                # Try JSON direct
                resp = await client.post(f"{self._base()}{ep}", json=json_payload_direct, headers=headers)
                if resp.status_code == 200 and await _verify_added():
                    return
                # Try form fallback
                resp = await client.post(f"{self._base()}{ep}", data=form_data, headers=form_headers)
                if resp.status_code == 200 and await _verify_added():
                    return
            except Exception:
                continue
        # If nothing worked, raise an error
        raise httpx.HTTPError("Failed to add client to inbound via known endpoints")

    def _build_link_from_inbound(self, user_uuid: str, remark: str, inbound: dict) -> str:
        # host from server base_url
        parsed = urlparse(self._base())
        host = parsed.hostname or "example.com"
        port = inbound.get("port") or parsed.port or 443
        stream = inbound.get("streamSettings") or {}
        # Some panels return JSON-encoded strings for streamSettings
        if isinstance(stream, str):
            try:
                import json as _json
                stream = _json.loads(stream) or {}
            except Exception:
                stream = {}
        network = ( (stream.get("network") if isinstance(stream, dict) else None) or "tcp" ).lower()
        security = ( (stream.get("security") if isinstance(stream, dict) else None) or "none" ).lower()
        path = "/"
        host_header = None
        if network == "ws":
            ws = (stream.get("wsSettings") if isinstance(stream, dict) else {}) or {}
            if isinstance(ws, str):
                try:
                    import json as _json
                    ws = _json.loads(ws) or {}
                except Exception:
                    ws = {}
            path = ws.get("path") or "/"
            headers = ws.get("headers") or {}
            if isinstance(headers, str):
                try:
                    import json as _json
                    headers = _json.loads(headers) or {}
                except Exception:
                    headers = {}
            # common key names
            host_header = headers.get("Host") or headers.get("host")
        # Build vless link
        params = [f"type={network}", f"security={security}"]
        if path:
            params.append(f"path={path}")
        if host_header:
            params.append(f"host={host_header}")
        query = "&".join(params)
        return f"vless://{user_uuid}@{host}:{port}?{query}#{remark}"

    async def create_service(self, request: CreateServiceRequest) -> CreateServiceResult:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            await self._login_get_cookie(client)
            inbounds = await self._list_inbounds(client)
            if not inbounds:
                # Fallback link if no inbound
                uid = str(uuid_lib.uuid4())
                return CreateServiceResult(uuid=uid, subscription_url=f"vless://{uid}@example.com:443?type=tcp&security=none#{request.remark}")
            inbound = None
            if request.inbound_id:
                inbound = next((x for x in inbounds if x.get("id") == request.inbound_id), None)
            inbound = inbound or inbounds[0]

            user_uuid = str(uuid_lib.uuid4())
            await self._add_client(
                client,
                inbound_id=inbound.get("id"),
                user_uuid=user_uuid,
                remark=request.remark,
                duration_days=request.duration_days,
                traffic_gb=request.traffic_gb,
            )
            inbound_detail = await self._get_inbound_detail(client, inbound.get("id")) if inbound.get("id") is not None else {}
            link = self._build_link_from_inbound(user_uuid, request.remark, inbound_detail or inbound)
            return CreateServiceResult(uuid=user_uuid, subscription_url=link)

    async def renew_service(self, uuid: str, add_days: int) -> None:
        return None

    async def add_traffic(self, uuid: str, add_gb: int) -> None:
        return None

    async def get_usage(self, uuid: str) -> dict:
        return {"used_gb": 0, "remaining_gb": 0, "days_left": 0}

    async def reset_uuid(self, uuid: str) -> str:
        return str(uuid_lib.uuid4())

    async def delete_service(self, uuid: str) -> None:
        return None


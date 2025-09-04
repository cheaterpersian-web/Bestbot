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

    async def _login_get_cookie(self, client: httpx.AsyncClient) -> None:
        if self.cfg.auth_mode != "password" or not self.cfg.username or not self.cfg.password:
            return
        await client.post(f"{self._base()}/login", data={"username": self.cfg.username, "password": self.cfg.password})

    async def _list_inbounds(self, client: httpx.AsyncClient) -> list[dict]:
        # Official 3x-ui: /xui/inbound/list returns {obj:[...]}
        r = await client.get(f"{self._base()}/xui/inbound/list")
        r.raise_for_status()
        data = r.json()
        inbounds = data.get("obj") if isinstance(data, dict) else data
        return inbounds or []

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

        # Pattern A: send "settings" as stringified JSON per 3x-ui
        import json as _json
        payload_a = {
            "id": inbound_id,
            "settings": _json.dumps({"clients": [client_obj]}),
            "enable": True,
        }
        resp = await client.post(f"{self._base()}/xui/inbound/addClient", json=payload_a)
        if resp.status_code == 200 and (resp.json().get("success") if resp.headers.get("content-type"," ").startswith("application/json") else True):
            return
        # Pattern B: send as nested object
        payload_b = {
            "id": inbound_id,
            "settings": {"clients": [client_obj]},
            "enable": True,
        }
        resp2 = await client.post(f"{self._base()}/xui/inbound/addClient", json=payload_b)
        resp2.raise_for_status()

    def _build_link_from_inbound(self, user_uuid: str, remark: str, inbound: dict) -> str:
        # host from server base_url
        parsed = urlparse(self._base())
        host = parsed.hostname or "example.com"
        port = inbound.get("port") or parsed.port or 443
        stream = inbound.get("streamSettings") or {}
        network = (stream.get("network") or "tcp").lower()
        security = (stream.get("security") or "none").lower()
        path = "/"
        host_header = None
        if network == "ws":
            ws = stream.get("wsSettings") or {}
            path = ws.get("path") or "/"
            headers = ws.get("headers") or {}
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
        async with httpx.AsyncClient(timeout=20) as client:
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
            link = self._build_link_from_inbound(user_uuid, request.remark, inbound)
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


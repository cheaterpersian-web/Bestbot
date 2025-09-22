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
            "X-Requested-With": "XMLHttpRequest",
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

        # Detect inbound protocol to shape client object (vless/vmess use id=uuid, trojan uses password)
        inbound_detail_proto = ""
        try:
            _det = await self._get_inbound_detail(client, inbound_id)
            inbound_detail_proto = (_det.get("protocol") or "").lower()
        except Exception:
            inbound_detail_proto = ""
        proto = inbound_detail_proto or "vless"

        client_obj = {
            "email": remark,
            "limitIp": 0,
            "totalGB": total_gb_bytes,
            "expiryTime": expiry_ts_ms,
            "enable": True,
        }
        if proto == "trojan":
            client_obj["password"] = user_uuid
        else:
            client_obj["id"] = user_uuid
            # vmess uses alterId (xui ignores if not needed)
            if proto == "vmess":
                client_obj["alterId"] = 0
            # vless optional flow field
            client_obj.setdefault("flow", "")

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
            # protocol-specific id/password
            ("password" if proto == "trojan" else "id"): user_uuid,
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
            # Prefer authoritative source: inbound detail -> settings.clients contains our entry
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
                            cid = c.get("id") or c.get("uuid") or c.get("password")
                            cmail = c.get("email")
                            if (cid == user_uuid) or (cmail == remark):
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
        identifier = uuid
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            await self._login_get_cookie(client)
            # Find client across inbounds
            inbounds = await self._list_inbounds(client)
            for ib in inbounds:
                ib_id = ib.get("id")
                if ib_id is None:
                    continue
                detail = await self._get_inbound_detail(client, int(ib_id))
                try:
                    import json as _json
                    settings = detail.get("settings") or {}
                    if isinstance(settings, str):
                        settings = _json.loads(settings) or {}
                    clients = settings.get("clients") or []
                    for c in clients:
                        cid = c.get("id") or c.get("uuid") or c.get("password")
                        cmail = c.get("email")
                        if cid == identifier or cmail == identifier:
                            # Compute new expiry
                            import time as _time
                            cur_exp = int(c.get("expiryTime") or 0)
                            now_ms = int(_time.time() * 1000)
                            base_ms = cur_exp if cur_exp and cur_exp > now_ms else now_ms
                            new_exp_ms = base_ms + int(add_days) * 86400 * 1000
                            # Build update payload
                            upd = {
                                "email": cmail or (c.get("email") or identifier),
                                "enable": c.get("enable", True),
                                "limitIp": int(c.get("limitIp") or 0),
                                "totalGB": int(c.get("totalGB") or c.get("total") or 0),
                                "expiryTime": new_exp_ms,
                                "flow": c.get("flow") or "",
                            }
                            if c.get("password"):
                                upd["password"] = c.get("password")
                                client_id = c.get("password")
                            else:
                                upd["id"] = c.get("id") or c.get("uuid") or identifier
                                client_id = upd["id"]
                            # Try updateClient endpoints
                            eps = [
                                f"/panel/api/inbounds/updateClient/{client_id}",
                                f"/api/inbounds/updateClient/{client_id}",
                                f"/inbounds/updateClient/{client_id}",
                                f"/updateClient/{client_id}",
                            ]
                            for ep in eps:
                                try:
                                    r = await client.post(f"{self._base()}{ep}", json=upd, headers=self._auth_headers())
                                    if r.status_code == 200:
                                        return
                                except Exception:
                                    continue
                except Exception:
                    continue
            # If not found or update failed, do nothing (non-fatal)
            return None

    async def add_traffic(self, uuid: str, add_gb: int) -> None:
        identifier = uuid
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            await self._login_get_cookie(client)
            inbounds = await self._list_inbounds(client)
            for ib in inbounds:
                ib_id = ib.get("id")
                if ib_id is None:
                    continue
                detail = await self._get_inbound_detail(client, int(ib_id))
                try:
                    import json as _json
                    settings = detail.get("settings") or {}
                    if isinstance(settings, str):
                        settings = _json.loads(settings) or {}
                    clients = settings.get("clients") or []
                    for c in clients:
                        cid = c.get("id") or c.get("uuid") or c.get("password")
                        cmail = c.get("email")
                        if cid == identifier or cmail == identifier:
                            cur_total = int(c.get("totalGB") or c.get("total") or 0)
                            new_total = cur_total + int(add_gb) * 1024 * 1024 * 1024
                            upd = {
                                "email": cmail or (c.get("email") or identifier),
                                "enable": c.get("enable", True),
                                "limitIp": int(c.get("limitIp") or 0),
                                "totalGB": new_total,
                                "expiryTime": int(c.get("expiryTime") or 0),
                                "flow": c.get("flow") or "",
                            }
                            if c.get("password"):
                                upd["password"] = c.get("password")
                                client_id = c.get("password")
                            else:
                                upd["id"] = c.get("id") or c.get("uuid") or identifier
                                client_id = upd["id"]
                            eps = [
                                f"/panel/api/inbounds/updateClient/{client_id}",
                                f"/api/inbounds/updateClient/{client_id}",
                                f"/inbounds/updateClient/{client_id}",
                                f"/updateClient/{client_id}",
                            ]
                            for ep in eps:
                                try:
                                    r = await client.post(f"{self._base()}{ep}", json=upd, headers=self._auth_headers())
                                    if r.status_code == 200:
                                        return
                                except Exception:
                                    continue
                except Exception:
                    continue
            return None

    async def get_usage(self, uuid: str) -> dict:
        identifier = uuid  # may be email(remark) or uuid
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            await self._login_get_cookie(client)
            # Try getClientTraffics by identifier (email)
            candidates = [
                f"/panel/api/inbounds/getClientTraffics/{identifier}",
                f"/api/inbounds/getClientTraffics/{identifier}",
                f"/inbounds/getClientTraffics/{identifier}",
                f"/getClientTraffics/{identifier}",
            ]
            data = None
            for path in candidates:
                try:
                    r = await client.get(f"{self._base()}{path}", headers=self._auth_headers())
                    if r.status_code == 200:
                        data = r.json()
                        break
                except Exception:
                    continue
            used_bytes = 0
            total_bytes = 0
            days_left = 0
            try:
                import time as _time
                # data can be dict or list
                entries = []
                if isinstance(data, dict):
                    entries = data.get("obj") if isinstance(data.get("obj"), list) else (data.get("clients") or [])
                    if not entries:
                        entries = [data]
                elif isinstance(data, list):
                    entries = data
                for e in entries:
                    try:
                        up = int(e.get("up") or 0)
                        down = int(e.get("down") or 0)
                        total = int(e.get("total") or e.get("totalGB") or 0)
                        used_bytes += up + down
                        # Some implementations return per inbound totals; take max as limit
                        total_bytes = max(total_bytes, total)
                        exp = int(e.get("expiryTime") or 0)
                        if exp:
                            rem_days = max(0, int((exp/1000 - _time.time()) // 86400))
                            days_left = max(days_left, rem_days)
                    except Exception:
                        continue
            except Exception:
                pass
            def _gb(x: int) -> float:
                return round(float(x) / (1024 * 1024 * 1024), 3)
            remaining_gb = max(0.0, _gb(total_bytes - used_bytes)) if total_bytes else 0.0
            return {"used_gb": _gb(used_bytes), "remaining_gb": remaining_gb, "total_gb": _gb(total_bytes), "days_left": days_left}

    async def reset_uuid(self, uuid: str) -> str:
        return str(uuid_lib.uuid4())

    async def delete_service(self, uuid: str) -> None:
        return None


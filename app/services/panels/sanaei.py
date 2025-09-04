from __future__ import annotations

import uuid as uuid_lib
from typing import Optional

import httpx

from .base import PanelClient, CreateServiceRequest, CreateServiceResult, PanelServerConfig


class SanaeiPanelClient(PanelClient):
    def __init__(self, cfg: PanelServerConfig) -> None:
        self.cfg = cfg

    async def _login_get_cookie(self, client: httpx.AsyncClient) -> None:
        if self.cfg.auth_mode != "password" or not self.cfg.username or not self.cfg.password:
            return
        # NOTE: Endpoint paths are placeholders; you should adjust to your 3x-ui/sanaei build.
        try:
            await client.post(f"{self.cfg.base_url.rstrip('/')}/login", data={"username": self.cfg.username, "password": self.cfg.password})
        except Exception:
            pass

    async def create_service(self, request: CreateServiceRequest) -> CreateServiceResult:
        # This is a placeholder integrating flow: fetch inbounds, pick first or matching inbound_id, then create user and build link
        async with httpx.AsyncClient(timeout=20) as client:
            await self._login_get_cookie(client)
            # Fetch inbounds
            inbound_id = request.inbound_id
            selected_inbound = None
            try:
                r = await client.get(f"{self.cfg.base_url.rstrip('/')}/panel/api/inbounds")
                data = r.json()
                inbounds = data.get("obj") or data
                if isinstance(inbounds, list) and inbounds:
                    if inbound_id:
                        selected_inbound = next((x for x in inbounds if x.get("id") == inbound_id), inbounds[0])
                    else:
                        selected_inbound = inbounds[0]
            except Exception:
                pass

            user_uuid = str(uuid_lib.uuid4())
            remark = request.remark
            # Create client on inbound (placeholder structure)
            try:
                payload = {
                    "id": selected_inbound.get("id") if selected_inbound else (inbound_id or 0),
                    "settings": {
                        "clients": [
                            {
                                "id": user_uuid,
                                "email": remark,
                            }
                        ]
                    }
                }
                await client.post(f"{self.cfg.base_url.rstrip('/')}/panel/api/inbounds/addClient", json=payload)
            except Exception:
                pass

            # Build link from inbound/server meta
            host = (selected_inbound or {}).get("address") or request.server_host or "example.com"
            port = (selected_inbound or {}).get("port") or request.server_port or 443
            protocol = request.protocol or "vless"
            network = request.network or "tcp"
            security = request.security or "none"
            host_header = request.host_header or "exo.ir"
            path = request.path or "/"
            link = f"{protocol}://{user_uuid}@{host}:{port}?type={network}&path={path}&host={host_header}&headerType=http&security={security}#{remark}"
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


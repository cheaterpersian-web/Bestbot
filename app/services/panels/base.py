from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class PanelServerConfig:
    base_url: str
    api_key: str
    panel_type: str  # mock | xui | 3xui | hiddify
    auth_mode: str = "apikey"  # apikey | password
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass
class CreateServiceRequest:
    remark: str
    duration_days: Optional[int]
    traffic_gb: Optional[int]
    inbound_id: Optional[int]
    server_host: Optional[str]
    server_port: Optional[int]
    protocol: str = "vless"
    network: str = "tcp"
    security: str = "none"
    host_header: Optional[str] = None
    path: Optional[str] = None


@dataclass
class CreateServiceResult:
    uuid: str
    subscription_url: str


class PanelClient(Protocol):
    async def create_service(self, request: CreateServiceRequest) -> CreateServiceResult: ...

    async def renew_service(self, uuid: str, add_days: int) -> None: ...

    async def add_traffic(self, uuid: str, add_gb: int) -> None: ...

    async def get_usage(self, uuid: str) -> dict: ...

    async def reset_uuid(self, uuid: str) -> str: ...  # returns new uuid

    async def delete_service(self, uuid: str) -> None: ...


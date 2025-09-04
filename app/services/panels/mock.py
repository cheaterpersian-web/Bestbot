import uuid as uuid_lib

from .base import PanelClient, CreateServiceRequest, CreateServiceResult


class MockPanelClient(PanelClient):
    async def create_service(self, request: CreateServiceRequest) -> CreateServiceResult:
        uid = str(uuid_lib.uuid4())
        host = request.server_host or "example.com"
        port = request.server_port or 443
        protocol = request.protocol or "vless"
        network = request.network or "tcp"
        security = request.security or "none"
        host_header = request.host_header or "exo.ir"
        path = request.path or "/"
        # Build a vless-like link for testing
        link = f"{protocol}://{uid}@{host}:{port}?type={network}&path={path}&host={host_header}&headerType=http&security={security}#{request.remark}"
        return CreateServiceResult(uuid=uid, subscription_url=link)

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


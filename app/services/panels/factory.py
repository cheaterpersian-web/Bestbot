from typing import Literal

from core.config import settings
from services.panels.base import PanelClient, PanelServerConfig
from services.panels.mock import MockPanelClient
from services.panels.sanaei import SanaeiPanelClient


def get_panel_client(panel_type: str) -> PanelClient:
    t = (panel_type or settings.default_panel_mode).lower()
    if t in {"mock", "xui", "3xui", "hiddify", "sanaei"}:
        # For MVP, all map to mock. Later implement concrete clients.
        return MockPanelClient()
    return MockPanelClient()


def get_panel_client_for_server(base_url: str, panel_type: str, auth_mode: str = "apikey", api_key: str = "", username: str | None = None, password: str | None = None) -> PanelClient:
    t = (panel_type or settings.default_panel_mode).lower()
    cfg = PanelServerConfig(base_url=base_url, api_key=api_key or "", panel_type=t, auth_mode=auth_mode or "apikey", username=username, password=password)
    if t in {"3xui", "sanaei", "xui"}:
        return SanaeiPanelClient(cfg)
    return MockPanelClient()


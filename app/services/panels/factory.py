from typing import Literal

from core.config import settings
from services.panels.base import PanelClient
from services.panels.mock import MockPanelClient


def get_panel_client(panel_type: str) -> PanelClient:
    t = (panel_type or settings.default_panel_mode).lower()
    if t in {"mock", "xui", "3xui", "hiddify"}:
        # For MVP, all map to mock. Later implement concrete clients.
        return MockPanelClient()
    return MockPanelClient()


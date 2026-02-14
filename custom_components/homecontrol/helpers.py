from __future__ import annotations
from typing import Any, Dict, List, Set
import re
import logging
import pprint
import traceback
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.components.lovelace.const import ConfigNotFound

ENTITY_RE = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z0-9_\.]+$", re.IGNORECASE)


async def async_get_dashboards(hass) -> dict[str, Any]:
    """Return a flat mapping of dashboard_key -> dashboard object (robust to HA shapes)."""
    ViewType = dict[str, Any]
    ViewListType = list[ViewType]
    CardType = dict[str, Any]
    CardListType = list[CardType]

    result: dict[str, ViewListType] = {}

    lovelace = hass.data[LOVELACE_DOMAIN]
    dashboards: dict[str, Any] = lovelace.dashboards
    for dashboard_id, dashboard in dashboards.items():
        if dashboard_id is None:
            continue

        print("Lovelace dashboard:", dashboard_id)

        try:
            dashboard_data = await dashboard.async_load(False)
        except ConfigNotFound:
            continue

        views: ViewListType = []

        # iterate over views in dashboard_data
        for idx, view_data in enumerate(dashboard_data.get("views", [])):
            view: ViewType = {}
            view["title"] = view_data.get("title")
            view["path"] = view_data.get("path", str(idx))
            view["type"] = view_data.get("type")

            # Sections and cards
            sections: list[CardListType] = []

            if view.get("type") == "sections":
                for section_data in view_data.get("sections", []):
                    sections.append(section_data.get("cards", []))
            else:
                sections.append(view_data.get("cards", []))

            view["sections"] = sections

            # Badges
            badges = view_data.get("badges", [])
            if badges:
                view["badges"] = badges

            views.append(view)
        result[str(dashboard_id)] = views
    return result

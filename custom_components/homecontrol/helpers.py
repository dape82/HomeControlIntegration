from __future__ import annotations
from typing import Any
from homeassistant.helpers import entity_registry as er
import re
import logging

logger = logging.getLogger(__name__)
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

        logger.debug("Lovelace dashboard: %s", dashboard_id)

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
            viewType = view_data.get("type")

            # Sections and cards
            sections: list[CardListType] = []

            if viewType == "sections":
                for section_data in view_data.get("sections", []):
                    ui_sections = group_cards_into_sections(
                        section_data.get("cards", []), hass
                    )
                    sections.extend(ui_sections)
            else:
                ui_sections = group_cards_into_sections(
                    view_data.get("cards", []), hass
                )
                sections.extend(ui_sections)

            view["sections"] = sections

            # Badges: normalize so each badge contains entities with devices
            badges = view_data.get("badges", [])
            if badges:
                normalized_badges: list[dict[str, Any]] = []
                entity_reg = er.async_get(hass)

                def ent_to_device(eid: str) -> str:
                    entry = entity_reg.async_get(eid)
                    if entry and entry.device_id:
                        return entry.device_id
                    return eid

                for b in badges:
                    # title: rename from `name` (or accept existing `title`)
                    title = None
                    if isinstance(b, dict):
                        title = b.get("name") or b.get("title")

                    # extract referenced entities (works for str or dict)
                    raw_entities = list(extract_entities_from_card(b))

                    # fallback: if badge is a plain string entity id
                    if not raw_entities and isinstance(b, str) and ENTITY_RE.match(b):
                        raw_entities = [b]

                    entities_list = [
                        {"entity": e, "device": ent_to_device(e)} for e in raw_entities
                    ]

                    badge_obj: dict[str, Any] = {}
                    if title:
                        badge_obj["title"] = title
                    if entities_list:
                        badge_obj["entities"] = entities_list

                    # Only include badges that have some useful info
                    if badge_obj:
                        normalized_badges.append(badge_obj)

                if normalized_badges:
                    view["badges"] = normalized_badges

            views.append(view)
        result[str(dashboard_id)] = views
    return result


def extract_entities_from_card(card: dict[str, Any]) -> set[str]:
    """Return a set of entity IDs referenced in a Lovelace card config.

    This performs a recursive inspection of the card configuration and
    collects strings that match the Home Assistant entity id pattern.
    """
    entities: set[str] = set()

    def _walk(obj: Any) -> None:
        if obj is None:
            return

        if isinstance(obj, str):
            for match in ENTITY_RE.findall(obj):
                entities.add(match)
            return

        if isinstance(obj, dict):
            ent = obj.get("entity")
            if isinstance(ent, str) and ENTITY_RE.match(ent):
                entities.add(ent)

            ents = obj.get("entities")
            if ents is not None:
                _walk(ents)

            for v in obj.values():
                _walk(v)
            return

        if isinstance(obj, (list, tuple, set)):
            for item in obj:
                _walk(item)
            return

    _walk(card)
    return entities


from typing import Any


def group_cards_into_sections(
    cards: list[dict[str, Any]], hass
) -> list[dict[str, Any]]:
    """Group Lovelace cards into sections (optional title/subtitle + devices list).

    Entity IDs referenced by cards are mapped to device IDs (deduplicated).
    If an entity has no associated device, the entity id is used as a fallback.
    """
    sections: list[dict[str, Any]] = []

    current_title: str | None = None
    current_subtitle: str | None = None
    current_entities_list: list[dict[str, str]] = []
    current_entities_set: set[str] = set()
    current_devices_list: list[str] = []
    current_devices_set: set[str] = set()

    entity_reg = er.async_get(hass)

    def ent_to_device(eid: str) -> str:
        entry = entity_reg.async_get(eid)
        if entry and entry.device_id:
            return entry.device_id
        return eid

    def has_open_section() -> bool:
        return bool(current_title or current_subtitle or current_entities_list)

    def flush_current() -> None:
        nonlocal \
            current_title, \
            current_subtitle, \
            current_entities_list, \
            current_entities_set
        if current_entities_list or current_title or current_subtitle:
            section: dict[str, Any] = {"entities": current_entities_list[:]}

            if current_title:
                section["title"] = current_title
            if current_subtitle:
                section["subtitle"] = current_subtitle

            sections.append(section)

        current_title = None
        current_subtitle = None
        current_entities_list = []
        current_entities_set = set()

    for card in cards or []:
        ctype = (card.get("type") or "").lower()

        # --- Heading cards ----------------------------------------------------
        if ctype == "heading":
            style = (card.get("heading_style") or "title").lower()
            heading_text = card.get("heading") or card.get("title")

            if style == "title":
                # New title starts a new section if something is already open
                if has_open_section():
                    flush_current()
                current_title = heading_text

            elif style == "subtitle":
                # Subtitle attaches to current section if it hasn't collected entities yet.
                # If entities already exist, subtitle should start a new section.
                if current_entities_list:
                    flush_current()
                current_subtitle = heading_text

            continue

        # --- Entities card ----------------------------------------------------
        if ctype == "entities":
            raw_ents = card.get("entities", [])
            ents: list[str] = []
            for e in raw_ents:
                if isinstance(e, str) and ENTITY_RE.match(e):
                    ents.append(e)
                elif isinstance(e, dict):
                    ent = e.get("entity")
                    if isinstance(ent, str) and ENTITY_RE.match(ent):
                        ents.append(ent)

            title = card.get("title") or card.get("name")
            if title:
                # Titled entities card is its own section; flush open section first
                if has_open_section():
                    flush_current()
                sections.append(
                    {
                        "title": title,
                        "entities": [
                            {"entity": e, "device": ent_to_device(e)} for e in ents
                        ],
                    }
                )
                continue

            # Untitled entities card: append to current section
            for ent in ents:
                if ent not in current_entities_set:
                    current_entities_set.add(ent)
                    current_entities_list.append(
                        {"entity": ent, "device": ent_to_device(ent)}
                    )
            continue

        # --- Generic cards: extract referenced entities -----------------------
        ents = list(extract_entities_from_card(card))

        # If a card references no entities, treat it as a visual separator:
        # it breaks grouping between sections (e.g. clock, weather, markdown, etc.).
        if not ents:
            if has_open_section():
                flush_current()
            continue

        # Special-case: a single-entity `type: entity` card should be standalone
        # ONLY if there is no open section context. Otherwise it belongs to the
        # current titled/subtitled section (your example #1).
        if ctype == "entity" and len(ents) == 1 and not has_open_section():
            sections.append(
                {"entities": [{"entity": ents[0], "device": ent_to_device(ents[0])}]}
            )
            continue

        # Default: append extracted entities to current section
        for ent in ents:
            if ent not in current_entities_set:
                current_entities_set.add(ent)
                current_entities_list.append(
                    {"entity": ent, "device": ent_to_device(ent)}
                )

    flush_current()
    return sections

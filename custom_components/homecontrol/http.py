from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

from .helpers import async_get_dashboards

from .const import DOMAIN, CONF_DASHBOARD


def _get_entry(hass: HomeAssistant):
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


def _get_dashboard(hass: HomeAssistant) -> str | None:
    """Return the selected dashboard id (url_path) or None.

    Normalise possible stored shapes: single string, list/set of strings, or missing.
    """
    entry = _get_entry(hass)
    if not entry:
        return None

    val = entry.options.get(CONF_DASHBOARD)
    if val is None:
        return None
    # If option stored as iterable (list/set/tuple), pick the first element
    if isinstance(val, (list, set, tuple)):
        try:
            return str(next(iter(val)))
        except StopIteration:
            return None
    return str(val)


class HomeControlDashboardView(HomeAssistantView):
    url = "/api/homecontrol/dashboard"
    name = "api:homecontrol:dashboard"
    requires_auth = True

    async def get(self, request):
        hass: HomeAssistant = request.app["hass"]

        dashboards = await async_get_dashboards(hass)
        dashboard_id = _get_dashboard(hass)

        conf = dashboards.get(dashboard_id) if dashboard_id else None
        if not conf:
            return self.json({"error": "dashboard_not_found"}, status_code=404)

        # conf can be a dict or object; handle dict first
        title = None
        url_path = None
        if isinstance(conf, dict):
            title = conf.get("title") or (conf.get("config") or {}).get("title")
            url_path = (
                conf.get("url_path")
                or conf.get("path")
                or (conf.get("config") or {}).get("url_path")
            )
        else:
            title = getattr(conf, "title", None)
            url_path = getattr(conf, "url_path", None) or getattr(conf, "path", None)

        key_str = str(url_path or dashboard_id)
        label = title or url_path or key_str

        payload = {
            "dashboard_id": dashboard_id,
            "dashboard_title": label,
            "generated_at": dt_util.utcnow().isoformat(),
            "views": dashboards.get(str(dashboard_id), []),
        }
        return self.json(payload)


class HomeControlEntityView(HomeAssistantView):
    url = "/api/homecontrol/entity"
    name = "api:homecontrol:entity"
    requires_auth = True

    async def get(self, request):
        hass: HomeAssistant = request.app["hass"]

        entity_id = request.query.get("entity_id")
        if not entity_id:
            return self.json({"error": "missing_entity_id"}, status_code=400)

        entity_reg = er.async_get(hass)
        entry = entity_reg.async_get(entity_id)
        if not entry:
            return self.json({"error": "entity_not_found"}, status_code=404)

        # Registry fields
        entry_obj: dict[str, object] = {
            "entity_id": entry.entity_id,
            "platform": getattr(entry, "platform", None),
            "device_id": getattr(entry, "device_id", None),
            "original_name": getattr(entry, "original_name", None),
            "generated_at": dt_util.utcnow().isoformat(),
        }

        # Current state (if any)
        state = hass.states.get(entity_id)

        if state is not None:
            entry_obj["state"] = state.state
            # join entry_obj and state.attributes
            attributes = dict(state.attributes)
            entry_obj["last_updated"] = (
                state.last_updated.isoformat()
                if getattr(state, "last_updated", None) is not None
                else None
            )

        merged = {**attributes, **entry_obj}

        return self.json(merged)


class HomeControlDeviceView(HomeAssistantView):
    url = "/api/homecontrol/device"
    name = "api:homecontrol:device"
    requires_auth = True

    async def get(self, request):
        hass: HomeAssistant = request.app["hass"]

        device_id = request.query.get("device_id")
        if not device_id:
            return self.json({"error": "missing_device_id"}, status_code=400)

        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(device_id)
        if not device:
            return self.json({"error": "device_not_found"}, status_code=404)

        # Serialize device entry (convert sets/tuples to lists)
        def _tuplify_set(s):
            try:
                return [list(t) for t in s]
            except Exception:
                return list(s)

        device_obj: dict[str, object] = {
            "id": device.id,
            "name": device.name,
            "name_by_user": device.name_by_user,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "sw_version": device.sw_version,
            "hw_version": device.hw_version,
            "via_device_id": device.via_device_id,
            "area_id": device.area_id,
            "disabled_by": device.disabled_by,
            "config_entries": list(device.config_entries)
            if device.config_entries is not None
            else [],
            "identifiers": _tuplify_set(device.identifiers or []),
            "connections": _tuplify_set(device.connections or []),
            "entry_type": device.entry_type,
        }

        # Entities for this device
        entity_reg = er.async_get(hass)
        entries = er.async_entries_for_device(entity_reg, device.id)

        entities: list[dict[str, object]] = []
        for e in entries:
            entities.append(
                {
                    "entity_id": e.entity_id,
                    "unique_id": getattr(e, "unique_id", None),
                    "platform": getattr(e, "platform", None),
                    "disabled_by": getattr(e, "disabled_by", None),
                    "config_entry_id": getattr(e, "config_entry_id", None),
                    "device_id": e.device_id,
                    "area_id": getattr(e, "area_id", None),
                    "original_name": getattr(e, "original_name", None),
                }
            )

        payload = {
            "device": device_obj,
            "entities": entities,
            "generated_at": dt_util.utcnow().isoformat(),
        }

        return self.json(payload)


def async_register_views_once(hass: HomeAssistant) -> None:
    """Register HTTP views exactly once."""
    hass.data.setdefault(DOMAIN, {})

    if hass.data[DOMAIN].get("_http_registered"):
        return

    hass.http.register_view(HomeControlDashboardView())
    hass.http.register_view(HomeControlDeviceView())
    hass.http.register_view(HomeControlEntityView())
    hass.data[DOMAIN]["_http_registered"] = True

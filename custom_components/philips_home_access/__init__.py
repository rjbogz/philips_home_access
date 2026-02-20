import logging
from datetime import timedelta

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.persistent_notification import async_create as persistent_notify
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.issue_registry import IssueSeverity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["lock", "sensor", "switch", "number"]
ISSUE_AUTH = "auth_invalid"

def _issue_id(entry_id: str) -> str:
    return f"{ISSUE_AUTH}_{entry_id}"

def create_auth_issue(hass, entry):
    ir.async_create_issue(
        hass,
        DOMAIN,
        _issue_id(entry.entry_id),
        is_fixable=True,
        severity=IssueSeverity.ERROR,
        translation_key="reauth_required",
        translation_placeholders={"name": entry.title},
        data={"entry_id": entry.entry_id},
    )

def clear_auth_issue(hass, entry):
    ir.async_delete_issue(hass, DOMAIN, _issue_id(entry.entry_id))
    
    # 2. Dismiss the persistent notification popup
    hass.async_create_task(
        hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": f"{DOMAIN}_{entry.entry_id}_auth"},
        )
    )

async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass, entry):
    from .api import PhilipsHomeAccessAPI
    from homeassistant.exceptions import ConfigEntryAuthFailed

    api = PhilipsHomeAccessAPI(
        entry.data["username"],
        entry.data["password"],
        entry.data["region"],
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api

    if hass.data.get(DOMAIN, {}).get(f"{entry.entry_id}_auth_invalid"):
        raise ConfigEntryAuthFailed("Philips Home Access needs re-authentication")

    try:
        await hass.async_add_executor_job(api.login)
    except Exception as err:
        raise ConfigEntryAuthFailed(
            "Philips Home Access authentication failed. Please reconfigure."
        ) from err

    clear_auth_issue(hass, entry)
    hass.data[DOMAIN][f"{entry.entry_id}_auth_invalid"] = False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    clear_auth_issue(hass, entry)
    hass.data[DOMAIN][f"{entry.entry_id}_auth_invalid"] = False

    async def _auth_watchdog(now):
        try:
            devices = await hass.async_add_executor_job(api.get_devices)
            if not devices:
                return

            esn = devices[0].get("wifiSN")
            if not esn:
                return

            resp = await hass.async_add_executor_job(api.query_device_attr, esn)

            if isinstance(resp, dict) and str(resp.get("code")) == "444":
                hass.data[DOMAIN][f"{entry.entry_id}_auth_invalid"] = True
                create_auth_issue(hass, entry)
                await hass.config_entries.async_reload(entry.entry_id)
                return

        except Exception as err:
            _LOGGER.exception("Auth watchdog failed: %r", err)

    unsub = async_track_time_interval(hass, _auth_watchdog, timedelta(minutes=5))
    hass.data[DOMAIN][f"{entry.entry_id}_unsub_authwatch"] = unsub

    return True


async def async_unload_entry(hass, entry):
    unsub = hass.data[DOMAIN].pop(f"{entry.entry_id}_unsub_authwatch", None)
    if unsub:
        unsub()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok

async def async_mark_entry_auth_failed(hass, entry):
    """Mark integration as needing re-authentication."""
    from homeassistant.exceptions import ConfigEntryAuthFailed

    persistent_notify(
        hass,
        title="Philips Home Access requires login",
        message=(
            "Your Philips Home Access session is no longer valid. "
            "Reload the integration to log in again."
        ),
        notification_id=f"{DOMAIN}_{entry.entry_id}_auth",
    )

    # Trigger reload so HA shows failure state
    await hass.config_entries.async_reload(entry.entry_id)
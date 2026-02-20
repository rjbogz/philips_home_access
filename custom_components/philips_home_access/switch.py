from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    hass.data[DOMAIN].setdefault(entry.entry_id, {})
    hass.data[DOMAIN].setdefault("autolock_enabled", {})
    hass.data[DOMAIN]["autolock_enabled"].setdefault(entry.entry_id, {})
    api = hass.data[DOMAIN][entry.entry_id]
    devices = await hass.async_add_executor_job(api.get_devices)
    async_add_entities([PhilipsAutoLockSwitch(api, d) for d in devices])

class PhilipsAutoLockSwitch(SwitchEntity):
    def __init__(self, api, device):
        self._api = api
        self._esn = device["wifiSN"]
        self._attr_name = f"{device['lockNickname']} Auto-Lock"
        self._attr_unique_id = f"{self._esn}_autolock_switch"
        self._attr_is_on = (device.get("amMode") == 0)
        self._attr_device_info = {"identifiers": {(DOMAIN, self._esn)}}

    async def async_turn_on(self, **kwargs):
        await self.hass.async_add_executor_job(self._api.set_auto_lock_mode, self._esn, True)
        self._attr_is_on = True
        self.hass.data[DOMAIN]["autolock_enabled"][self.platform.config_entry.entry_id][self._esn] = True
        self.async_write_ha_state()
        await self.async_update_related_entities()

    async def async_turn_off(self, **kwargs):
        await self.hass.async_add_executor_job(self._api.set_auto_lock_mode, self._esn, False)
        self._attr_is_on = False
        self.hass.data[DOMAIN]["autolock_enabled"][self.platform.config_entry.entry_id][self._esn] = False
        self.async_write_ha_state()
        await self.async_update_related_entities()

    async def async_update_related_entities(self):
        registry = er.async_get(self.hass)
        number_unique_id = f"{self._esn}_autolock_time"

        number_entity_id = registry.async_get_entity_id("number", DOMAIN, number_unique_id)
        if not number_entity_id:
            return

        await self.hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": number_entity_id},
            blocking=False,
        )
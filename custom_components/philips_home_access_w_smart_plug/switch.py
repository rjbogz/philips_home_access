from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    hass.data[DOMAIN].setdefault(entry.entry_id, {})
    hass.data[DOMAIN].setdefault("autolock_enabled", {})
    hass.data[DOMAIN]["autolock_enabled"].setdefault(entry.entry_id, {})
    api = hass.data[DOMAIN][entry.entry_id]
    devices = await hass.async_add_executor_job(api.get_devices)
    _LOGGER.debug("switch: setting up switch entities from %s devices", len(devices))
    lock_devices = [d for d in devices if d.get("deviceType") == "LOCK"]
    gateway_devices = [
        d
        for d in devices
        if d.get("deviceType") == "GATEWAY" and "gwPowerStatus" in d
    ]
    async_add_entities(
        [PhilipsAutoLockSwitch(api, d) for d in lock_devices]
        + [PhilipsGatewayPowerSwitch(api, d) for d in gateway_devices],
        update_before_add=True,
    )

class PhilipsAutoLockSwitch(SwitchEntity):
    def __init__(self, api, device):
        self._api = api
        self._esn = device["wifiSN"]
        self._attr_name = f"{device['lockNickname']} Auto-Lock"
        self._attr_unique_id = f"{self._esn}_autolock_switch"
        self._attr_is_on = (device.get("amMode") == 0)
        self._attr_device_info = {"identifiers": {(DOMAIN, self._esn)}}

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug("switch: enabling auto-lock for esn=%s", self._esn)
        resp = await self.hass.async_add_executor_job(self._api.set_auto_lock_mode, self._esn, True)
        _LOGGER.debug("switch: enable response for esn=%s: %s", self._esn, resp)
        self._attr_is_on = True
        self.hass.data[DOMAIN]["autolock_enabled"][self.platform.config_entry.entry_id][self._esn] = True
        self.async_write_ha_state()
        await self.async_update_related_entities()

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug("switch: disabling auto-lock for esn=%s", self._esn)
        resp = await self.hass.async_add_executor_job(self._api.set_auto_lock_mode, self._esn, False)
        _LOGGER.debug("switch: disable response for esn=%s: %s", self._esn, resp)
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
        
        _LOGGER.debug("switch: requesting update_entity for %s", number_entity_id)
        
        await self.hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": number_entity_id},
            blocking=False,
        )


class PhilipsGatewayPowerSwitch(SwitchEntity):
    _attr_icon = "mdi:power-plug"
    _attr_should_poll = True

    def __init__(self, api, device):
        self._api = api
        self._esn = device["wifiSN"]
        name = device.get("lockNickname") or "Philips Home Access Gateway"
        self._attr_name = f"{name} Power"
        self._attr_unique_id = f"{self._esn}_gateway_power"
        self._attr_is_on = device.get("gwPowerStatus") == 1
        self._attr_available = str(device.get("online", "1")) == "1"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._esn)},
            name=name,
            manufacturer="Philips",
            model=device.get("model") or device.get("productModel", "Gateway"),
            sw_version=device.get("gatewayVersion") or device.get("wifiVersion"),
        )

    async def async_turn_on(self, **kwargs):
        await self._async_set_power(True)

    async def async_turn_off(self, **kwargs):
        await self._async_set_power(False)

    async def _async_set_power(self, enabled):
        _LOGGER.debug("gateway power switch: setting esn=%s enabled=%s", self._esn, enabled)
        resp = await self.hass.async_add_executor_job(
            self._api.set_gateway_power_status,
            self._esn,
            enabled,
        )
        _LOGGER.debug("gateway power switch: set response for esn=%s: %s", self._esn, resp)
        if isinstance(resp, dict) and resp.get("code") == 200:
            self._attr_is_on = enabled
            self._attr_available = True
            self.async_write_ha_state()
            await self.async_update()

    async def async_update(self):
        try:
            resp = await self.hass.async_add_executor_job(self._api.query_device_attr, self._esn)
            data = resp.get("data", {}) if isinstance(resp, dict) else {}
            self._attr_available = str(data.get("online", "1")) == "1"
            if "gwPowerStatus" in data:
                self._attr_is_on = data.get("gwPowerStatus") == 1
        except Exception as err:
            _LOGGER.debug("gateway power switch: update failed for esn=%s: %r", self._esn, err)
            self._attr_available = False

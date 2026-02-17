import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN, REGIONS, CONF_REGION

_LOGGER = logging.getLogger(__name__)


class PhilipsHomeAccessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_reauth(self, user_input=None):
        """Handle re-authentication."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self._entry = entry
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Prompt for new credentials and validate."""
        errors = {}

        entry = getattr(self, "_entry", None)
        if entry is None:
            errors["base"] = "unknown"
            return self.async_abort(reason="unknown")

        if user_input is not None:
            try:
                from .api import PhilipsHomeAccessAPI

                api = PhilipsHomeAccessAPI(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_REGION],
                )

                await self.hass.async_add_executor_job(api.login)

            except Exception as err:
                err_key = str(err) if err else ""
                if err_key in ("invalid_auth", "account_not_find"):
                    errors["base"] = "invalid_auth"
                elif err_key in ("cannot_connect", "timeout"):
                    errors["base"] = "cannot_connect"
                else:
                    _LOGGER.exception("Reauth failed: %r", err)
                    errors["base"] = "unknown"
            else:
                # Save new creds onto the existing entry
                new_data = dict(entry.data)
                new_data.update(
                    {
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_REGION: user_input[CONF_REGION],
                    }
                )
                self.hass.config_entries.async_update_entry(entry, data=new_data)

                # reload the entry so it logs in with new creds
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        # Prefill from existing entry
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=entry.data.get(CONF_USERNAME, "")): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_REGION, default=entry.data.get(CONF_REGION, REGIONS[0])): vol.In(REGIONS),
                }
            ),
            errors=errors,
        )

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                from .api import PhilipsHomeAccessAPI

                api = PhilipsHomeAccessAPI(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_REGION],
                )

                await self.hass.async_add_executor_job(api.login)

            except Exception as err:
                err_key = str(err) if err else ""

                if err_key in ("invalid_auth", "account_not_find"):
                    errors["base"] = "invalid_auth"
                elif err_key in ("cannot_connect", "timeout"):
                    errors["base"] = "cannot_connect"
                elif err_key in ("region_not_found",):
                    errors["base"] = "unknown"
                else:
                    _LOGGER.exception("Unexpected error while loading Philips Home Access config flow: %r", err)
                    errors["base"] = "unknown"

            else:
                unique = f"{DOMAIN}_{api.uid}" if api.uid else f"{DOMAIN}_{user_input[CONF_USERNAME]}_{user_input[CONF_REGION]}"
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_REGION: user_input[CONF_REGION],
                }

                title = f"Philips Home Access ({user_input[CONF_USERNAME]})"
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_REGION, default=REGIONS[0]): vol.In(REGIONS),
                }
            ),
            errors=errors,
        )

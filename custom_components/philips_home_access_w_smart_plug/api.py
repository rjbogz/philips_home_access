import json
import time
import requests
import base64
import binascii
import logging

_LOGGER = logging.getLogger(__name__)

from .const import RSA_HEX_KEY, RSA_PRIVATE_SIGN


class PhilipsHomeAccessAPI:
    def __init__(self, username, password, region_code):
        self.username = username
        self.password = password
        self.region_code = region_code
        self.token = None
        self.uid = None

    def _mask(self, value, keep=4):
        if not value:
            return None
        value = str(value)
        if len(value) <= keep:
            return "*" * len(value)
        return f"{value[:keep]}***"
    
    def _find_device(self, devices, wifi_sn):
        for device in devices:
            if device.get("wifiSN") == wifi_sn:
                return device
        return None

    def _normalize_mac(self, mac: str) -> str:
        if not mac:
            return ""
        cleaned = str(mac).replace(" ", "").replace(":", "").replace("-", "").upper()
        if len(cleaned) != 12:
            return cleaned
        return ":".join(cleaned[i:i+2] for i in range(0, 12, 2))

    def _get_lock_transport_info(self, lock_esn):
        """Return transport details for a lock.

        Result:
        {
            "mode": "direct" | "gateway",
            "lock": <lock device dict>,
            "gateway": <gateway device dict or None>,
        }
        """
        devices = self.get_devices()
        lock = self._find_device(devices, lock_esn)
        if not lock:
            raise Exception(f"lock_not_found:{lock_esn}")

        if lock.get("deviceType") != "LOCK":
            raise Exception(f"device_not_lock:{lock_esn}")

        master_sn = lock.get("masterSn")
        if master_sn:
            gateway = self._find_device(devices, master_sn)
            if gateway and gateway.get("deviceType") == "GATEWAY":
                return {
                    "mode": "gateway",
                    "lock": lock,
                    "gateway": gateway,
                }

        return {
            "mode": "direct",
            "lock": lock,
            "gateway": None,
        }

    def login(self):
        url = "https://user-oneness.juziwulian.com/homeaccess/oauth/login"
        headers = {
            "reqSource": "app",
            "lang": "en_US",
            "language": "en_US",
            "timestamp": str(int(time.time())),
            "token": "5+4KiiOY06hCN8wSZG3yAYBI6uXgQHBxc1EsCA3tLSrrRx2IY7ni1F9IloXpOFrY/gzAd/iSbIb9gU54w9ldWzbvtV5jNh4EQWT68zLAtIUv5Sd7P9FT7ddikjnqRojOS/8NtOzoUu9HpUb/kTEKKjPQWD9wHSV6pmESiOMq+kPn/ezdrFM4jWKaTq8U5Yl1E7+d2fXWiDn+UlP4FhdgxlUs0bO9PDQOhlA3pZbDg3n8ouwgF2zFoFMMJTdHbNLHvcMyq7vlN9kqPVq4rSebjg==",
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {
            "identifier": self.username,
            "credential": self.password,
            "areacode": "1",
        }

        _LOGGER.debug("Login start: username=%s region=%s", self._mask(self.username), self.region_code)

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            _LOGGER.debug("Login HTTP status=%s", response.status_code)
            data = response.json()
        except requests.RequestException as err:
            _LOGGER.debug("Login request failed: %r", err)
            raise Exception("cannot_connect") from err
        except ValueError as err:
            _LOGGER.debug("Login returned non-JSON response")
            raise Exception("unknown_error") from err

        _LOGGER.debug(
            "Login response code=%s errCode=%s users=%s",
            data.get("code"),
            data.get("errCode"),
            len(data.get("data", {}).get("users", [])),
        )

        if data.get("code") != 200:
            error_code = data.get("errCode")
            if error_code == "account_not_find":
                raise Exception("account_not_find")
            if error_code == "account_password_not_match":
                raise Exception("invalid_auth")
            raise Exception("unknown_error")

        users = data.get("data", {}).get("users", [])
        for user in users:
            if user.get("code") == self.region_code:
                self.token = user.get("token")
                self.uid = user.get("uid")
                _LOGGER.debug(
                    "Login success: region=%s uid=%s token_present=%s",
                    self.region_code,
                    self._mask(self.uid),
                    bool(self.token),
                )
                return True

        _LOGGER.debug("Login succeeded but requested region was not found: region=%s", self.region_code)
        raise Exception("region_not_found")

    def get_devices(self):
        url = "https://api.idlespacetech.com/homeaccess/device/list"
        headers = {
            "token": self.token,
            "reqSource": "app",
            "timestamp": str(int(time.time())),
            "Content-Type": "application/json; charset=utf-8",
        }
        payload = {"uid": self.uid}

        _LOGGER.debug("get_devices start: uid=%s token_present=%s", self._mask(self.uid), bool(self.token))

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            _LOGGER.debug("get_devices HTTP status=%s", response.status_code)
            data = response.json()
        except requests.RequestException as err:
            _LOGGER.debug("get_devices request failed: %r", err)
            raise
        except ValueError as err:
            _LOGGER.debug("get_devices returned non-JSON response")
            raise

        devices = data.get("data", {}).get("wifiList", [])
        _LOGGER.debug(
            "get_devices response code=%s device_count=%s",
            data.get("code"),
            len(devices),
        )
        return devices

    def query_device_attr(self, esn: str):
        from Crypto.PublicKey import RSA
        from Crypto.Hash import SHA256
        from Crypto.Signature import pkcs1_15

        url = "https://api.idlespacetech.com/v4/device/query-device-attr"
        current_time_ms = int(time.time() * 1000)

        headers = {
            "token": self.token,
            "k-tenant": "philips",
            "k-version": "4.11.0",
            "k-language": "en_US",
            "k-signv": "1.0.0",
            "encrypt_data": "physical_encrypt_data",
            "reqSource": "app",
            "lang": "en_US",
            "language": "en_US",
            "timestamp": str(current_time_ms),
            "Content-Type": "application/json",
        }

        payload = {"esn": esn, "reqTime": str(current_time_ms)}
        canonical_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)

        key = RSA.import_key(RSA_PRIVATE_SIGN)
        h = SHA256.new(canonical_str.encode())
        payload["sign"] = base64.b64encode(pkcs1_15.new(key).sign(h)).decode()

        _LOGGER.debug("query_device_attr start: esn=%s", self._mask(esn))

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            _LOGGER.debug("query_device_attr HTTP status=%s", resp.status_code)
            out = resp.json()
        except requests.RequestException as err:
            _LOGGER.debug("query_device_attr request failed: %r", err)
            raise
        except ValueError:
            _LOGGER.debug("query_device_attr returned non-JSON response")
            return {"code": resp.status_code, "msg": "non_json_response", "text": resp.text[:500]}

        if isinstance(out, dict):
            out["_http_status"] = resp.status_code
            _LOGGER.debug(
                "query_device_attr response code=%s http_status=%s",
                out.get("code"),
                resp.status_code,
            )
        return out

    def _get_headers(self):
        return {
            "token": self.token,
            "k-tenant": "philips",
            "k-version": "4.11.0",
            "k-language": "en_US",
            "k-signv": "1.0.0",
            "content-type": "application/json",
            "content-length": "249",
            "accept-encoding": "gzip",
        }

    def _sign(self, payload):
        from Crypto.PublicKey import RSA
        from Crypto.Hash import SHA256
        from Crypto.Signature import pkcs1_15

        key = RSA.import_key(RSA_PRIVATE_SIGN)
        canonical_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        h = SHA256.new(canonical_str.encode())
        return base64.b64encode(pkcs1_15.new(key).sign(h)).decode()

    def set_auto_lock_mode(self, esn, enabled):
        url = "https://api.idlespacetech.com/v3/api/device/set-am-mode"
        mode = 0 if enabled else 1

        payload = {
            "esn": esn,
            "amMode": mode,
            "reqTime": str(int(time.time() * 1000)),
        }
        payload["sign"] = self._sign(payload)
        headers = self._get_headers()

        _LOGGER.debug("set_auto_lock_mode start: esn=%s enabled=%s amMode=%s", self._mask(esn), enabled, mode)

        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        out = resp.json()
        _LOGGER.debug(
            "set_auto_lock_mode response: http_status=%s code=%s msg=%s",
            resp.status_code,
            out.get("code") if isinstance(out, dict) else None,
            out.get("msg") if isinstance(out, dict) else None,
        )
        return out

    def set_auto_lock_time(self, esn, seconds):
        url = "https://api.idlespacetech.com/v3/api/device/set-auto-lock-time"

        payload = {
            "esn": esn,
            "reqTime": str(int(time.time() * 1000)),
            "autoLockTime": int(seconds),
        }
        payload["sign"] = self._sign(payload)
        final_body = {
            "esn": esn,
            "sign": payload["sign"],
            "reqTime": payload["reqTime"],
            "autoLockTime": int(seconds),
        }

        _LOGGER.debug("set_auto_lock_time start: esn=%s seconds=%s", self._mask(esn), int(seconds))

        resp = requests.post(url, headers=self._get_headers(), json=final_body, timeout=10)
        out = resp.json()
        _LOGGER.debug(
            "set_auto_lock_time response: http_status=%s code=%s msg=%s",
            resp.status_code,
            out.get("code") if isinstance(out, dict) else None,
            out.get("msg") if isinstance(out, dict) else None,
        )
        return out

    def set_gateway_power_status(self, esn, enabled):
        url = "https://api.idlespacetech.com/v3/gateway/set-gateway-power"
        status = 1 if enabled else 0
        payload = {
            "powerStatus": status,
            "esn": esn,
            "reqTime": str(int(time.time())),
        }
        payload["sign"] = self._sign(payload)

        headers = {
            "token": self.token,
            "k-tenant": "philips",
            "k-version": "4.13.1",
            "k-language": "en_US",
            "k-signv": "1.0.0",
            "Content-Type": "application/json",
        }

        _LOGGER.debug("set_gateway_power_status start: esn=%s enabled=%s powerStatus=%s", self._mask(esn), enabled, status)

        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        try:
            out = resp.json()
        except Exception:
            _LOGGER.debug("set_gateway_power_status returned non-JSON response: http_status=%s", resp.status_code)
            return {
                "code": resp.status_code,
                "msg": "non_json_response",
                "text": resp.text[:500],
                "_http_status": resp.status_code,
            }

        if isinstance(out, dict):
            out["_http_status"] = resp.status_code
            _LOGGER.debug(
                "set_gateway_power_status response: http_status=%s code=%s msg=%s",
                resp.status_code,
                out.get("code"),
                out.get("msg"),
            )
        return out

    def set_lock_state(self, esn, lock_it):
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        from Crypto.Hash import SHA256
        from Crypto.Signature import pkcs1_15

        transport = self._get_lock_transport_info(esn)
        current_time_ms = int(time.time() * 1000)

        headers = {
            "token": self.token,
            "k-tenant": "philips",
            "k-version": "4.11.0",
            "k-language": "en_US",
            "k-signv": "1.0.0",
            "encrypt_data": "physical_encrypt_data",
            "reqSource": "app",
            "lang": "en_US",
            "language": "en_US",
            "timestamp": str(current_time_ms),
            "Content-Type": "application/json",
        }

        if transport["mode"] == "gateway":
            url = f"https://api.idlespacetech.com/v3/gateway/set-lock-{'close' if lock_it else 'open'}"
            payload_to_sign = {
                "esn": transport["lock"]["wifiSN"],
                "mac": self._normalize_mac(transport["lock"].get("mac", "")),
                "masterSn": transport["gateway"]["wifiSN"],
                "userNumberId": 0,
                "reqTime": str(current_time_ms),
            }
        else:
            url = f"https://api.idlespacetech.com/v3/device/{'close' if lock_it else 'open'}-device"
            payload_to_sign = {
                "esn": esn,
                "userNumberId": 0,
                "reqTime": str(current_time_ms),
            }

        canonical_str = json.dumps(payload_to_sign, separators=(",", ":"), sort_keys=True)

        key = RSA.import_key(RSA_PRIVATE_SIGN)
        h = SHA256.new(canonical_str.encode())
        payload_to_sign["sign"] = base64.b64encode(pkcs1_15.new(key).sign(h)).decode()

        final_json = json.dumps(payload_to_sign, separators=(",", ":")).encode()

        _LOGGER.debug(
            "payload: %s",
            final_json
        )

        encrypt_key = RSA.import_key(binascii.unhexlify(RSA_HEX_KEY))
        cipher = PKCS1_v1_5.new(encrypt_key)

        chunk_size = encrypt_key.size_in_bytes() - 11
        encrypted_chunks = []
        for i in range(0, len(final_json), chunk_size):
            encrypted_chunks.append(cipher.encrypt(final_json[i : i + chunk_size]))

        body = {"encryptData": base64.b64encode(b"".join(encrypted_chunks)).decode()}

        _LOGGER.debug(
            "set_lock_state start: esn=%s lock_it=%s mode=%s url=%s",
            self._mask(esn),
            lock_it,
            transport["mode"],
            url,
        )

        resp = requests.post(url, headers=headers, json=body, timeout=10)

        try:
            out = resp.json()
        except Exception:
            _LOGGER.debug("set_lock_state returned non-JSON response: http_status=%s", resp.status_code)
            return {
                "code": resp.status_code,
                "msg": "non_json_response",
                "text": resp.text[:500],
            }

        if isinstance(out, dict):
            out["_http_status"] = resp.status_code
            _LOGGER.debug(
                "set_lock_state response: http_status=%s code=%s msg=%s",
                resp.status_code,
                out.get("code"),
                out.get("msg"),
            )
        return out

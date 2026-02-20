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

    def login(self):
        url = "https://user-oneness.juziwulian.com/homeaccess/oauth/login"
        headers = {
            "reqSource": "app", "lang": "en_US", "language": "en_US",
            "timestamp": str(int(time.time())),
            "token": "5+4KiiOY06hCN8wSZG3yAYBI6uXgQHBxc1EsCA3tLSrrRx2IY7ni1F9IloXpOFrY/gzAd/iSbIb9gU54w9ldWzbvtV5jNh4EQWT68zLAtIUv5Sd7P9FT7ddikjnqRojOS/8NtOzoUu9HpUb/kTEKKjPQWD9wHSV6pmESiOMq+kPn/ezdrFM4jWKaTq8U5Yl1E7+d2fXWiDn+UlP4FhdgxlUs0bO9PDQOhlA3pZbDg3n8ouwgF2zFoFMMJTdHbNLHvcMyq7vlN9kqPVq4rSebjg==",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {"identifier": self.username, "credential": self.password, "areacode": "1"}
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        data = response.json()

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
                return True
        
        raise Exception("region_not_found")

    def get_devices(self):
        url = "https://api.idlespacetech.com/homeaccess/device/list"
        headers = {
            "token": self.token,
            "reqSource": "app",
            "timestamp": str(int(time.time())),
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {"uid": self.uid}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.json().get("data", {}).get("wifiList", [])

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

        resp = requests.post(url, headers=headers, json=payload, timeout=10)

        try:
            out = resp.json()
        except Exception:
            return {"code": resp.status_code, "msg": "non_json_response", "text": resp.text[:500]}

        if isinstance(out, dict):
            out["_http_status"] = resp.status_code
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
            "accept-encoding": "gzip"
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
            "reqTime": str(int(time.time() * 1000))
        }
        payload["sign"] = self._sign(payload)
        headers = self._get_headers()
        return requests.post(url, headers=headers, json=payload, timeout=10).json()

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
            "autoLockTime": int(seconds)
        }
        headers = self._get_headers()
        resp = requests.post(url, headers=self._get_headers(), json=final_body, timeout=10)
        return resp.json()
        #return requests.post(url, headers=headers, json=payload, timeout=10).json()

    def set_lock_state(self, esn, lock_it):
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        from Crypto.Hash import SHA256
        from Crypto.Signature import pkcs1_15

        url = f"https://api.idlespacetech.com/v3/device/{'close' if lock_it else 'open'}-device"

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

        encrypt_key = RSA.import_key(binascii.unhexlify(RSA_HEX_KEY))
        cipher = PKCS1_v1_5.new(encrypt_key)

        chunk_size = encrypt_key.size_in_bytes() - 11
        encrypted_chunks = []
        for i in range(0, len(final_json), chunk_size):
            encrypted_chunks.append(cipher.encrypt(final_json[i : i + chunk_size]))

        body = {"encryptData": base64.b64encode(b"".join(encrypted_chunks)).decode()}

        resp = requests.post(url, headers=headers, json=body, timeout=10)

        try:
            out = resp.json()
        except Exception:
            return {
                "code": resp.status_code,
                "msg": "non_json_response",
                "text": resp.text[:500],
            }

        if isinstance(out, dict):
            out["_http_status"] = resp.status_code
        return out
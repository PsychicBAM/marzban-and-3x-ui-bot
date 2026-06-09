from __future__ import annotations

import logging
from typing import Any

import httpx

from app.application.exceptions import VpnPanelAuthError
from app.config.settings import Settings
from app.infrastructure.integrations.common.errors import map_http_status, map_transport_error
from app.infrastructure.integrations.common.masking import mask_secret

logger = logging.getLogger(__name__)


class MarzbanApiClient:
    """Low-level async Marzban HTTP client."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.marzban_base_url.rstrip("/")
        self._username = settings.marzban_username
        self._password = settings.marzban_password
        self._api_token = settings.marzban_api_token
        self._verify_ssl = settings.marzban_verify_ssl
        self._inbounds = {
            "vless": settings.marzban_inbound_vless,
            "trojan": settings.marzban_inbound_trojan,
            "vmess": settings.marzban_inbound_vmess,
        }
        self._token: str | None = None

    async def close(self) -> None:
        return None

    async def _get_token(self) -> str:
        if self._api_token:
            return self._api_token
        if self._token:
            return self._token

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                verify=self._verify_ssl,
                timeout=30.0,
            ) as client:
                response = await client.post(
                    "/api/admin/token",
                    data={"username": self._username, "password": self._password},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except Exception as exc:
            raise map_transport_error("marzban", exc, context="authentication") from exc

        if response.status_code >= 400:
            logger.warning(
                "Marzban auth failed for user=%s",
                mask_secret(self._username),
            )
            raise map_http_status(
                panel="marzban",
                status_code=response.status_code,
                body=response.text,
                context="authentication",
            )

        data = response.json()
        token = data.get("access_token")
        if not token:
            raise VpnPanelAuthError("Marzban authentication returned no token", panel="marzban")
        self._token = str(token)
        return self._token

    def _invalidate_token(self) -> None:
        if not self._api_token:
            self._token = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> httpx.Response:
        try:
            token = await self._get_token()
            async with httpx.AsyncClient(
                base_url=self._base_url,
                verify=self._verify_ssl,
                timeout=30.0,
                headers={"Authorization": f"Bearer {token}"},
            ) as client:
                response = await client.request(method, path, json=json)
        except Exception as exc:
            raise map_transport_error("marzban", exc, context=f"{method} {path}") from exc

        if response.status_code in {401, 403} and retry_auth and not self._api_token:
            self._invalidate_token()
            if retry_auth:
                return await self._request(method, path, json=json, retry_auth=False)

        return response

    def build_user_payload(
        self,
        *,
        username: str,
        expire_unix: int,
        data_limit_bytes: int,
        status: str = "active",
        ip_limit: int = 0,
        vless_flow: str | None = None,
    ) -> dict[str, Any]:
        vless_proxy: dict[str, Any] = {}
        flow = (vless_flow or "").strip()
        if flow:
            vless_proxy["flow"] = flow

        payload: dict[str, Any] = {
            "username": username,
            "proxies": {
                "vless": vless_proxy,
                "trojan": {},
                "vmess": {},
            },
            "inbounds": {
                "vless": [self._inbounds["vless"]],
                "trojan": [self._inbounds["trojan"]],
                "vmess": [self._inbounds["vmess"]],
            },
            "expire": expire_unix,
            "data_limit": data_limit_bytes,
            "data_limit_reset_strategy": "no_reset",
            "status": status,
            "note": "",
        }
        if ip_limit > 0:
            payload["limit_ip"] = ip_limit
        return payload

    async def get_user_raw(self, username: str) -> dict[str, Any] | None:
        response = await self._request("GET", f"/api/user/{username}")
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, dict) else None
        if response.status_code in {404, 500}:
            return None
        raise map_http_status(
            panel="marzban",
            status_code=response.status_code,
            body=response.text,
            context=f"get user {username}",
        )

    async def create_user_raw(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", "/api/user", json=payload)
        if response.status_code in {200, 201}:
            return response.json()
        if response.status_code == 409:
            raise map_http_status(
                panel="marzban",
                status_code=409,
                body=response.text,
                context="create user",
            )
        raise map_http_status(
            panel="marzban",
            status_code=response.status_code,
            body=response.text,
            context="create user",
        )

    async def modify_user_raw(self, username: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("PUT", f"/api/user/{username}", json=payload)
        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            raise map_http_status(
                panel="marzban",
                status_code=404,
                body=response.text,
                context=f"modify user {username}",
            )
        raise map_http_status(
            panel="marzban",
            status_code=response.status_code,
            body=response.text,
            context=f"modify user {username}",
        )

    async def delete_user_raw(self, username: str) -> None:
        response = await self._request("DELETE", f"/api/user/{username}")
        if response.status_code in {200, 204, 404}:
            return
        raise map_http_status(
            panel="marzban",
            status_code=response.status_code,
            body=response.text,
            context=f"delete user {username}",
        )

    async def reset_user_usage_raw(self, username: str) -> bool:
        response = await self._request("POST", f"/api/user/{username}/reset", json={})
        return response.status_code in {200, 204}

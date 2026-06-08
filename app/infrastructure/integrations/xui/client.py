from __future__ import annotations

import json
import logging
import secrets
from typing import Any

import httpx

from app.config.settings import Settings
from app.infrastructure.integrations.common.errors import map_http_status, map_transport_error
from app.infrastructure.integrations.common.masking import mask_secret

logger = logging.getLogger(__name__)


class XuiApiClient:
    """Low-level async 3x-ui HTTP client."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.xui_base_url.rstrip("/")
        self._username = settings.xui_username
        self._password = settings.xui_password
        self._api_token = settings.xui_api_token
        self._inbound_id = settings.xui_inbound_id
        self._verify_ssl = settings.xui_verify_ssl
        self._cookies: dict[str, str] | None = None

    @property
    def inbound_id(self) -> int:
        return self._inbound_id

    def _auth_headers(self) -> dict[str, str]:
        if self._api_token:
            return {"Authorization": f"Bearer {self._api_token}"}
        return {}

    def _cookie_header(self) -> dict[str, str]:
        if not self._cookies:
            return {}
        cookie_value = "; ".join(f"{key}={value}" for key, value in self._cookies.items())
        return {"Cookie": cookie_value}

    def _invalidate_session(self) -> None:
        self._cookies = None

    async def login(self) -> None:
        if self._api_token:
            return

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                verify=self._verify_ssl,
                timeout=30.0,
            ) as client:
                response = await client.post(
                    "/login",
                    data={"username": self._username, "password": self._password},
                )
        except Exception as exc:
            raise map_transport_error("xui", exc, context="authentication") from exc

        if response.status_code >= 400:
            logger.warning("3x-ui auth failed for user=%s", mask_secret(self._username))
            raise map_http_status(
                panel="xui",
                status_code=response.status_code,
                body=response.text,
                context="authentication",
            )

        body = response.json() if response.content else {}
        if isinstance(body, dict) and body.get("success") is False:
            raise map_http_status(
                panel="xui",
                status_code=401,
                body=response.text,
                context="authentication",
            )

        self._cookies = {key: value for key, value in response.cookies.items()}
        logger.info("3x-ui session authenticated")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        form_body: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> httpx.Response:
        if not self._api_token and not self._cookies:
            await self.login()

        headers = {**self._auth_headers(), **self._cookie_header()}
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                verify=self._verify_ssl,
                timeout=30.0,
                headers=headers,
            ) as client:
                if form_body is not None:
                    response = await client.request(method, path, data=form_body)
                else:
                    response = await client.request(method, path, json=json_body)
        except Exception as exc:
            raise map_transport_error("xui", exc, context=f"{method} {path}") from exc

        if response.status_code in {401, 403} and retry_auth and not self._api_token:
            self._invalidate_session()
            await self.login()
            return await self._request(
                method,
                path,
                json_body=json_body,
                form_body=form_body,
                retry_auth=False,
            )

        return response

    def _ensure_success(self, response: httpx.Response, *, context: str) -> dict[str, Any]:
        if response.status_code >= 400:
            raise map_http_status(
                panel="xui",
                status_code=response.status_code,
                body=response.text,
                context=context,
            )
        if not response.content:
            return {}
        data = response.json()
        if isinstance(data, dict) and data.get("success") is False:
            raise map_http_status(
                panel="xui",
                status_code=400,
                body=response.text,
                context=context,
            )
        return data if isinstance(data, dict) else {}

    async def list_inbounds_raw(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/panel/api/inbounds/list")
        data = self._ensure_success(response, context="list inbounds")
        obj = data.get("obj", [])
        return obj if isinstance(obj, list) else []

    async def get_inbound_raw(self, inbound_id: int) -> dict[str, Any] | None:
        response = await self._request("GET", f"/panel/api/inbounds/get/{inbound_id}")
        if response.status_code == 404:
            return None
        data = self._ensure_success(response, context=f"get inbound {inbound_id}")
        obj = data.get("obj")
        return obj if isinstance(obj, dict) else None

    async def add_client_raw(self, inbound_id: int, client: dict[str, Any]) -> None:
        payload = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [client]}, ensure_ascii=False),
        }
        response = await self._request(
            "POST",
            "/panel/api/inbounds/addClient",
            json_body=payload,
        )
        self._ensure_success(response, context="add client")

    async def update_client_raw(
        self,
        inbound_id: int,
        client_uuid: str,
        client: dict[str, Any],
    ) -> None:
        form_body = {
            "id": str(inbound_id),
            "settings": json.dumps({"clients": [client]}, ensure_ascii=False),
        }
        response = await self._request(
            "POST",
            f"/panel/api/inbounds/updateClient/{client_uuid}",
            form_body=form_body,
        )
        self._ensure_success(response, context="update client")

    async def delete_client_raw(self, inbound_id: int, client_uuid: str) -> None:
        response = await self._request(
            "POST",
            f"/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}",
        )
        if response.status_code in {200, 404}:
            return
        self._ensure_success(response, context="delete client")

    async def get_client_traffic_raw(self, email: str) -> dict[str, Any] | None:
        response = await self._request("GET", f"/panel/api/inbounds/getClientTraffics/{email}")
        if response.status_code == 404:
            return None
        data = self._ensure_success(response, context=f"get traffic {email}")
        obj = data.get("obj")
        return obj if isinstance(obj, dict) else None

    async def list_online_clients_raw(self) -> list[str]:
        response = await self._request("POST", "/panel/api/inbounds/onlines")
        data = self._ensure_success(response, context="list online clients")
        obj = data.get("obj", [])
        if isinstance(obj, list):
            return [str(item) for item in obj]
        return []

    async def clear_client_ips_raw(self, email: str) -> bool:
        response = await self._request("POST", f"/panel/api/inbounds/clearClientIps/{email}")
        return response.status_code in {200, 204}

    @staticmethod
    def generate_sub_id() -> str:
        return secrets.token_hex(8)

from __future__ import annotations

import json
import logging
import secrets
from typing import Any, Literal

import httpx

from app.application.exceptions import VpnPanelConflictError, VpnPanelError
from app.config.settings import Settings
from app.infrastructure.integrations.common.errors import map_http_status, map_transport_error
from app.infrastructure.integrations.common.masking import mask_secret
from app.infrastructure.integrations.xui.inbound_mutations import (
    ClientDeleteCriteria,
    ClientUpdateExpectation,
    append_client_to_inbound,
    build_inbound_update_payload,
    client_exists_in_inbound,
    client_update_verification_errors,
    count_clients_in_inbound,
    find_client_matching_delete_criteria,
    inbound_display_name,
    inbound_id_value,
    inbound_update_to_form,
    remove_client_from_inbound,
    replace_client_in_inbound,
)

logger = logging.getLogger(__name__)

ADD_CLIENT_PATH = "/panel/api/inbounds/addClient"

ClientMutationMethod = Literal["addClient", "inbound_update", "delClient", "updateClient"]
ClientUpdateMethod = Literal["updateClient", "inbound_update"]


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
        self._last_client_add_method: ClientMutationMethod | None = None
        self._last_client_delete_method: ClientMutationMethod | None = None
        self._last_client_update_method: ClientUpdateMethod | None = None

    @property
    def inbound_id(self) -> int:
        return self._inbound_id

    @property
    def last_client_add_method(self) -> ClientMutationMethod | None:
        return self._last_client_add_method

    @property
    def last_client_delete_method(self) -> ClientMutationMethod | None:
        return self._last_client_delete_method

    @property
    def last_client_update_method(self) -> ClientUpdateMethod | None:
        return self._last_client_update_method

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

        headers = {
            "Accept": "application/json",
            **self._auth_headers(),
            **self._cookie_header(),
        }
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

    def _sanitize_error_body(self, body: str) -> str:
        text = body.strip()
        if not text:
            return ""
        if self._api_token and self._api_token in text:
            text = text.replace(self._api_token, "***")
        return text[:300]

    def _format_request_error(
        self,
        response: httpx.Response,
        *,
        method: str,
        path: str,
    ) -> str:
        parts = [f"{method} {path}", f"HTTP {response.status_code}"]
        body = self._sanitize_error_body(response.text or "")
        if body:
            parts.append(body)
        return " | ".join(parts)

    def _ensure_success(
        self,
        response: httpx.Response,
        *,
        context: str,
        method: str | None = None,
        path: str | None = None,
    ) -> dict[str, Any]:
        if response.status_code >= 400:
            detail = (
                self._format_request_error(response, method=method, path=path)
                if method and path
                else self._sanitize_error_body(response.text or "")
            )
            raise map_http_status(
                panel="xui",
                status_code=response.status_code,
                body=detail or f"HTTP {response.status_code}",
                context=context,
            )
        if not response.content:
            return {}
        data = response.json()
        if isinstance(data, dict) and data.get("success") is False:
            detail = (
                self._format_request_error(response, method=method, path=path)
                if method and path
                else self._sanitize_error_body(response.text or "")
            )
            raise map_http_status(
                panel="xui",
                status_code=400,
                body=detail or "success=false",
                context=context,
            )
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _parse_response_meta(response: httpx.Response) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "http_status": response.status_code,
            "success": None,
            "msg": None,
        }
        if not response.content:
            return meta
        try:
            data = response.json()
            if isinstance(data, dict):
                meta["success"] = data.get("success")
                raw_msg = data.get("msg") or data.get("message")
                if raw_msg is not None:
                    meta["msg"] = str(raw_msg)[:200]
        except Exception:
            pass
        return meta

    @staticmethod
    def _format_add_client_verification_failure(
        *,
        inbound_id: int,
        target_email: str,
        protocol: str,
        clients_before: int,
        clients_after: int,
        settings_parsed_before: bool,
        settings_parsed_after: bool,
        update_meta: dict[str, Any],
    ) -> str:
        return (
            "3x-ui add client verification failed after inbound update fallback: "
            f"inbound_id={inbound_id}; "
            f"target_email={target_email}; "
            f"protocol={protocol}; "
            f"clients_before={clients_before}; "
            f"clients_after={clients_after}; "
            f"settings_parsed_before={settings_parsed_before}; "
            f"settings_parsed_after={settings_parsed_after}; "
            f"update_http_status={update_meta.get('http_status')}; "
            f"update_success={update_meta.get('success')}; "
            f"update_msg={update_meta.get('msg') or '—'}"
        )

    async def list_inbounds_raw(self) -> list[dict[str, Any]]:
        path = "/panel/api/inbounds/list"
        response = await self._request("GET", path)
        data = self._ensure_success(response, context="list inbounds", method="GET", path=path)
        obj = data.get("obj", [])
        return obj if isinstance(obj, list) else []

    async def get_inbound_raw(self, inbound_id: int) -> dict[str, Any] | None:
        path = f"/panel/api/inbounds/get/{inbound_id}"
        response = await self._request("GET", path)
        if response.status_code == 404:
            return None
        data = self._ensure_success(response, context=f"get inbound {inbound_id}", method="GET", path=path)
        obj = data.get("obj")
        return obj if isinstance(obj, dict) else None

    async def _update_inbound_raw(self, inbound_id: int, inbound: dict[str, Any]) -> dict[str, Any]:
        path = f"/panel/api/inbounds/update/{inbound_id}"
        payload = build_inbound_update_payload(inbound)
        form_body = inbound_update_to_form(payload)
        response = await self._request("POST", path, form_body=form_body)
        meta = self._parse_response_meta(response)
        self._ensure_success(
            response,
            context="update inbound",
            method="POST",
            path=path,
        )
        return meta

    async def _add_client_via_inbound_update(self, inbound_id: int, client: dict[str, Any]) -> None:
        inbound = await self.get_inbound_raw(inbound_id)
        if inbound is None:
            raise VpnPanelError(
                f"xui inbound {inbound_id} not found for client add fallback",
                panel="xui",
            )

        target_email = str(client.get("email") or "")
        protocol = str(inbound.get("protocol") or "")
        clients_before, settings_parsed_before = count_clients_in_inbound(inbound)

        updated_inbound = append_client_to_inbound(inbound, client)
        try:
            update_meta = await self._update_inbound_raw(inbound_id, updated_inbound)
        except VpnPanelError as exc:
            raise VpnPanelError(
                self._format_add_client_verification_failure(
                    inbound_id=inbound_id,
                    target_email=target_email,
                    protocol=protocol,
                    clients_before=clients_before,
                    clients_after=clients_before,
                    settings_parsed_before=settings_parsed_before,
                    settings_parsed_after=settings_parsed_before,
                    update_meta={
                        "http_status": "error",
                        "success": False,
                        "msg": exc.message[:200],
                    },
                ),
                panel="xui",
            ) from exc

        inbound_after = await self.get_inbound_raw(inbound_id)
        clients_after, settings_parsed_after = count_clients_in_inbound(inbound_after)
        found = inbound_after is not None and client_exists_in_inbound(inbound_after, target_email)
        if found:
            logger.info(
                "3x-ui add client inbound update verified",
                extra={
                    "inbound_id": inbound_id,
                    "email": target_email,
                    "clients_before": clients_before,
                    "clients_after": clients_after,
                    "update_http_status": update_meta.get("http_status"),
                },
            )
            return

        raise VpnPanelError(
            self._format_add_client_verification_failure(
                inbound_id=inbound_id,
                target_email=target_email,
                protocol=protocol,
                clients_before=clients_before,
                clients_after=clients_after,
                settings_parsed_before=settings_parsed_before,
                settings_parsed_after=settings_parsed_after,
                update_meta=update_meta,
            ),
            panel="xui",
        )

    def _client_match_criteria_from_payload(self, client: dict[str, Any]) -> ClientDeleteCriteria:
        return ClientDeleteCriteria(
            email=str(client.get("email") or "") or None,
            client_uuid=str(client.get("id") or "") or None,
            sub_id=str(client.get("subId") or "") or None,
        )

    async def _verify_client_updated(
        self,
        inbound_id: int,
        criteria: ClientDeleteCriteria,
        expected: ClientUpdateExpectation,
    ) -> None:
        inbound = await self.get_inbound_raw(inbound_id)
        if inbound is None:
            logger.warning(
                "3x-ui update verification failed",
                extra={"inbound_id": inbound_id, "reason": "inbound missing"},
            )
            raise VpnPanelError("3x-ui update verification failed: inbound missing", panel="xui")

        client = find_client_matching_delete_criteria(inbound, criteria)
        if client is None:
            logger.warning(
                "3x-ui update verification failed",
                extra={"inbound_id": inbound_id, "reason": "client not found"},
            )
            raise VpnPanelError("3x-ui update verification failed: client not found", panel="xui")

        errors = client_update_verification_errors(client, expected)
        if errors:
            detail = errors[0]
            logger.warning(
                "3x-ui update verification failed",
                extra={
                    "inbound_id": inbound_id,
                    "client_email": client.get("email"),
                    "errors": "; ".join(errors),
                },
            )
            raise VpnPanelError(f"3x-ui update verification failed: {detail}", panel="xui")

        logger.info(
            "3x-ui update verification succeeded",
            extra={
                "inbound_id": inbound_id,
                "client_email": client.get("email"),
            },
        )

    async def _update_client_via_inbound_fallback(
        self,
        inbound_id: int,
        criteria: ClientDeleteCriteria,
        client: dict[str, Any],
        *,
        expected: ClientUpdateExpectation,
    ) -> None:
        inbound = await self.get_inbound_raw(inbound_id)
        if inbound is None:
            raise VpnPanelError(
                f"xui inbound {inbound_id} not found for client update fallback",
                panel="xui",
            )
        updated_inbound, replace_result = replace_client_in_inbound(inbound, criteria, client)
        logger.info(
            "3x-ui inbound update fallback matched client",
            extra={
                "inbound_id": inbound_id,
                "client_email": replace_result.client_email,
                "matched_by": replace_result.matched_by,
                "updated_fields": ",".join(replace_result.updated_fields),
                "before_after": ",".join(
                    f"{field}:{before}->{after}" for field, before, after in replace_result.before_after
                ),
            },
        )
        if not replace_result.updated_fields:
            logger.warning(
                "3x-ui inbound update fallback: no client fields changed before POST",
                extra={"inbound_id": inbound_id, "client_email": replace_result.client_email},
            )
        await self._update_inbound_raw(inbound_id, updated_inbound)
        await self._verify_client_updated(inbound_id, criteria, expected)

    async def update_existing_client_via_inbound(
        self,
        inbound_id: int,
        client: dict[str, Any],
    ) -> None:
        """Replace an existing client entry via get-modify-update inbound."""
        criteria = self._client_match_criteria_from_payload(client)
        inbound = await self.get_inbound_raw(inbound_id)
        if inbound is None:
            raise VpnPanelError(
                f"xui inbound {inbound_id} not found for existing client update",
                panel="xui",
            )
        updated_inbound, replace_result = replace_client_in_inbound(inbound, criteria, client)
        logger.info(
            "3x-ui existing client inbound update",
            extra={
                "inbound_id": inbound_id,
                "client_email": replace_result.client_email,
                "matched_by": replace_result.matched_by,
                "updated_fields": ",".join(replace_result.updated_fields),
                "before_after": ",".join(
                    f"{field}:{before}->{after}" for field, before, after in replace_result.before_after
                ),
            },
        )
        await self._update_inbound_raw(inbound_id, updated_inbound)
        self._last_client_add_method = "inbound_update"

    async def add_client_raw(self, inbound_id: int, client: dict[str, Any]) -> None:
        """Try addClient; on 404 fall back to get-modify-update inbound."""
        self._last_client_add_method = None
        payload = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [client]}, ensure_ascii=False),
        }
        response = await self._request(
            "POST",
            ADD_CLIENT_PATH,
            json_body=payload,
        )

        if response.status_code == 404:
            primary_error = self._format_request_error(
                response,
                method="POST",
                path=ADD_CLIENT_PATH,
            )
            logger.info(
                "3x-ui addClient unavailable (404), using inbound update fallback",
                extra={"inbound_id": inbound_id, "email": client.get("email")},
            )
            try:
                await self._add_client_via_inbound_update(inbound_id, client)
            except VpnPanelConflictError:
                raise
            except Exception as exc:
                fallback_reason = str(exc)[:300]
                raise VpnPanelError(
                    "xui add client failed: "
                    f"primary addClient 404 ({primary_error}); "
                    f"fallback inbound update failed ({fallback_reason})",
                    panel="xui",
                ) from exc
            self._last_client_add_method = "inbound_update"
            logger.info(
                "3x-ui client added via inbound update fallback",
                extra={"inbound_id": inbound_id, "email": client.get("email")},
            )
            return

        self._ensure_success(
            response,
            context="add client",
            method="POST",
            path=ADD_CLIENT_PATH,
        )
        self._last_client_add_method = "addClient"

    async def update_client_raw(
        self,
        inbound_id: int,
        criteria: ClientDeleteCriteria,
        client: dict[str, Any],
        *,
        expected: ClientUpdateExpectation,
    ) -> None:
        """Try updateClient; on 404 fall back to get-modify-update inbound."""
        self._last_client_update_method = None
        client_uuid = str(client.get("id") or criteria.client_uuid or "")
        path = f"/panel/api/inbounds/updateClient/{client_uuid}"
        form_body = {
            "id": str(inbound_id),
            "settings": json.dumps({"clients": [client]}, ensure_ascii=False),
        }
        response = await self._request(
            "POST",
            path,
            form_body=form_body,
        )

        if response.status_code == 404:
            logger.info(
                "3x-ui updateClient unavailable 404, using inbound update fallback",
                extra={"inbound_id": inbound_id, "email": client.get("email")},
            )
            try:
                await self._update_client_via_inbound_fallback(
                    inbound_id,
                    criteria,
                    client,
                    expected=expected,
                )
            except VpnPanelError:
                raise
            except Exception as exc:
                primary_error = self._format_request_error(
                    response,
                    method="POST",
                    path=path,
                )
                fallback_reason = str(exc)[:300]
                raise VpnPanelError(
                    "xui update client failed: "
                    f"primary updateClient 404 ({primary_error}); "
                    f"fallback inbound update failed ({fallback_reason})",
                    panel="xui",
                ) from exc
            self._last_client_update_method = "inbound_update"
            return

        self._ensure_success(response, context="update client", method="POST", path=path)
        self._last_client_update_method = "updateClient"
        await self._verify_client_updated(inbound_id, criteria, expected)

    def _client_still_exists_error(self, inbound: dict[str, Any]) -> VpnPanelError:
        inbound_id = inbound_id_value(inbound) or 0
        remark = inbound_display_name(inbound)
        return VpnPanelError(
            f"3x-ui delete verification failed: client still exists in inbound #{inbound_id} {remark}",
            panel="xui",
        )

    async def _verify_client_deleted_in_inbound(
        self,
        inbound_id: int,
        criteria: ClientDeleteCriteria,
    ) -> None:
        inbound = await self.get_inbound_raw(inbound_id)
        if inbound is None:
            logger.info(
                "3x-ui delete verification succeeded (inbound missing)",
                extra={"inbound_id": inbound_id},
            )
            return
        remaining = find_client_matching_delete_criteria(inbound, criteria)
        if remaining is not None:
            logger.warning(
                "3x-ui delete per-inbound verification failed",
                extra={"inbound_id": inbound_id},
            )
            raise self._client_still_exists_error(inbound)
        logger.info(
            "3x-ui delete per-inbound verification succeeded",
            extra={"inbound_id": inbound_id},
        )

    async def _find_inbounds_with_client(
        self,
        criteria: ClientDeleteCriteria,
    ) -> list[tuple[int, dict[str, Any]]]:
        matched: list[tuple[int, dict[str, Any]]] = []
        for summary in await self.list_inbounds_raw():
            inbound_id = inbound_id_value(summary)
            if inbound_id is None:
                continue
            inbound = await self.get_inbound_raw(inbound_id)
            if inbound is None:
                continue
            if find_client_matching_delete_criteria(inbound, criteria) is not None:
                matched.append((inbound_id, inbound))
        return matched

    async def _verify_client_deleted_globally(
        self,
        criteria: ClientDeleteCriteria,
    ) -> None:
        for summary in await self.list_inbounds_raw():
            inbound_id = inbound_id_value(summary)
            if inbound_id is None:
                continue
            inbound = await self.get_inbound_raw(inbound_id)
            if inbound is None:
                continue
            if find_client_matching_delete_criteria(inbound, criteria) is not None:
                logger.warning(
                    "3x-ui delete global verification failed",
                    extra={"inbound_id": inbound_id},
                )
                raise self._client_still_exists_error(inbound)
        logger.info("3x-ui delete global verification succeeded")

    async def _delete_client_via_inbound_update(
        self,
        inbound_id: int,
        criteria: ClientDeleteCriteria,
    ) -> None:
        inbound = await self.get_inbound_raw(inbound_id)
        if inbound is None:
            raise VpnPanelError(
                f"xui inbound {inbound_id} not found for client delete fallback",
                panel="xui",
            )
        updated_inbound, remove_result = remove_client_from_inbound(inbound, criteria)
        logger.info(
            "3x-ui delete fallback matched client",
            extra={
                "inbound_id": inbound_id,
                "matched_by": ",".join(remove_result.matched_by),
                "clients_before": remove_result.clients_before,
                "clients_after": remove_result.clients_after,
            },
        )
        await self._update_inbound_raw(inbound_id, updated_inbound)
        await self._verify_client_deleted_in_inbound(inbound_id, criteria)

    async def delete_client_everywhere(
        self,
        criteria: ClientDeleteCriteria,
    ) -> None:
        """Remove matching client from every inbound via get-modify-update."""
        self._last_client_delete_method = None
        matched = await self._find_inbounds_with_client(criteria)
        if not matched:
            logger.info(
                "3x-ui delete: client not found in any inbound",
                extra={"email": criteria.email or ""},
            )
            await self._verify_client_deleted_globally(criteria)
            return

        self._last_client_delete_method = "inbound_update"
        for inbound_id, _ in matched:
            logger.info(
                "3x-ui delete: removing client from inbound",
                extra={"inbound_id": inbound_id},
            )
            await self._delete_client_via_inbound_update(inbound_id, criteria)

        await self._verify_client_deleted_globally(criteria)
        logger.info(
            "3x-ui client deleted from all matched inbounds",
            extra={"inbound_count": len(matched)},
        )

    async def get_client_traffic_raw(self, email: str) -> dict[str, Any] | None:
        path = f"/panel/api/inbounds/getClientTraffics/{email}"
        response = await self._request("GET", path)
        if response.status_code == 404:
            return None
        data = self._ensure_success(response, context=f"get traffic {email}", method="GET", path=path)
        obj = data.get("obj")
        return obj if isinstance(obj, dict) else None

    async def list_online_clients_raw(self) -> list[str]:
        path = "/panel/api/inbounds/onlines"
        response = await self._request("POST", path)
        data = self._ensure_success(response, context="list online clients", method="POST", path=path)
        obj = data.get("obj", [])
        if isinstance(obj, list):
            return [str(item) for item in obj]
        return []

    async def clear_client_ips_raw(self, email: str) -> bool:
        path = f"/panel/api/inbounds/clearClientIps/{email}"
        response = await self._request("POST", path)
        return response.status_code in {200, 204}

    @staticmethod
    def generate_sub_id() -> str:
        return secrets.token_hex(8)

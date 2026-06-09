from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.application.exceptions import VpnPanelConflictError, VpnPanelNotFoundError

JSON_STRING_FIELDS = frozenset({"settings", "streamSettings", "sniffing", "allocate"})

INBOUND_UPDATE_FIELDS = (
    "id",
    "userId",
    "up",
    "down",
    "total",
    "remark",
    "enable",
    "expiryTime",
    "listen",
    "port",
    "protocol",
    "settings",
    "streamSettings",
    "sniffing",
    "tag",
    "allocate",
)


def parse_settings_field(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _client_list(settings: dict[str, Any]) -> list[dict[str, Any]]:
    clients = settings.get("clients", [])
    if not isinstance(clients, list):
        clients = []
        settings["clients"] = clients
    return clients


def find_client_email_conflict(clients: list[dict[str, Any]], email: str) -> bool:
    target = email.lower()
    return any(str(client.get("email", "")).lower() == target for client in clients)


@dataclass(frozen=True, slots=True)
class ClientDeleteCriteria:
    email: str | None = None
    client_uuid: str | None = None
    sub_id: str | None = None


@dataclass(frozen=True, slots=True)
class RemoveClientResult:
    clients_before: int
    clients_after: int
    removed_count: int
    matched_by: tuple[str, ...] = field(default_factory=tuple)


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    return cleaned or None


def _normalize_token(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    return cleaned or None


def client_matches_delete_criteria(
    client: dict[str, Any],
    criteria: ClientDeleteCriteria,
) -> str | None:
    """Return the matched field name (email/id/uuid/subId) or None."""
    target_email = _normalize_email(criteria.email)
    target_uuid = _normalize_token(criteria.client_uuid)
    target_sub_id = _normalize_token(criteria.sub_id)

    client_email = _normalize_email(str(client.get("email") or ""))
    if target_email and client_email and client_email == target_email:
        return "email"

    for field in ("id", "uuid"):
        client_value = _normalize_token(str(client.get(field) or ""))
        if target_uuid and client_value and client_value == target_uuid:
            return field

    client_sub_id = _normalize_token(str(client.get("subId") or ""))
    if target_sub_id and client_sub_id and client_sub_id == target_sub_id:
        return "subId"

    return None


def find_client_matching_delete_criteria(
    inbound: dict[str, Any],
    criteria: ClientDeleteCriteria,
) -> dict[str, Any] | None:
    settings_obj = parse_settings_field(inbound.get("settings"))
    for client in settings_obj.get("clients", []):
        if not isinstance(client, dict):
            continue
        if client_matches_delete_criteria(client, criteria) is not None:
            return client
    return None


def inbound_display_name(inbound: dict[str, Any]) -> str:
    return str(inbound.get("remark") or inbound.get("tag") or "").strip()


def inbound_id_value(inbound: dict[str, Any]) -> int | None:
    raw_id = inbound.get("id")
    if raw_id is None:
        return None
    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None


def append_client_to_inbound(inbound: dict[str, Any], client: dict[str, Any]) -> dict[str, Any]:
    updated = dict(inbound)
    settings_obj = parse_settings_field(updated.get("settings"))
    clients = _client_list(settings_obj)

    email = str(client.get("email") or "")
    if email and find_client_email_conflict(clients, email):
        raise VpnPanelConflictError(
            f"3x-ui client '{email}' already exists in inbound",
            panel="xui",
        )

    clients.append(client)
    updated["settings"] = json.dumps(settings_obj, ensure_ascii=False)
    return build_inbound_update_payload(updated)


def replace_client_in_inbound(inbound: dict[str, Any], client: dict[str, Any]) -> dict[str, Any]:
    updated = dict(inbound)
    settings_obj = parse_settings_field(updated.get("settings"))
    clients = _client_list(settings_obj)

    email = str(client.get("email") or "")
    target = email.lower()
    replaced = False
    for index, item in enumerate(clients):
        if not isinstance(item, dict):
            continue
        if str(item.get("email", "")).lower() == target:
            clients[index] = client
            replaced = True
            break

    if not replaced:
        raise VpnPanelNotFoundError(
            f"3x-ui client '{email}' not found in inbound for update",
            panel="xui",
        )

    updated["settings"] = json.dumps(settings_obj, ensure_ascii=False)
    return build_inbound_update_payload(updated)


def remove_client_from_inbound(
    inbound: dict[str, Any],
    criteria: ClientDeleteCriteria,
) -> tuple[dict[str, Any], RemoveClientResult]:
    updated = dict(inbound)
    settings_obj = parse_settings_field(updated.get("settings"))
    clients = _client_list(settings_obj)
    clients_before = len(clients)

    matched_by: list[str] = []
    filtered: list[dict[str, Any]] = []
    for client in clients:
        if not isinstance(client, dict):
            filtered.append(client)
            continue
        match_field = client_matches_delete_criteria(client, criteria)
        if match_field is not None:
            if match_field not in matched_by:
                matched_by.append(match_field)
            continue
        filtered.append(client)

    removed_count = clients_before - len(filtered)
    if removed_count <= 0:
        raise VpnPanelNotFoundError(
            "3x-ui client not found in inbound for delete",
            panel="xui",
        )

    settings_obj["clients"] = filtered
    updated["settings"] = json.dumps(settings_obj, ensure_ascii=False)
    result = RemoveClientResult(
        clients_before=clients_before,
        clients_after=len(filtered),
        removed_count=removed_count,
        matched_by=tuple(matched_by),
    )
    return build_inbound_update_payload(updated), result


def build_inbound_update_payload(inbound: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in INBOUND_UPDATE_FIELDS:
        if key not in inbound or inbound[key] is None:
            continue
        value = inbound[key]
        if key in JSON_STRING_FIELDS:
            if isinstance(value, (dict, list)):
                payload[key] = json.dumps(value, ensure_ascii=False)
            else:
                payload[key] = str(value)
        else:
            payload[key] = value
    return payload


def inbound_update_to_form(payload: dict[str, Any]) -> dict[str, str]:
    form: dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(value, bool):
            form[key] = "true" if value else "false"
        else:
            form[key] = str(value)
    return form

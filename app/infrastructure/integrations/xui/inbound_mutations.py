from __future__ import annotations

import json
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
    *,
    client_uuid: str,
    email: str | None = None,
) -> dict[str, Any]:
    updated = dict(inbound)
    settings_obj = parse_settings_field(updated.get("settings"))
    clients = _client_list(settings_obj)

    target_uuid = client_uuid.strip()
    target_email = email.lower() if email else None
    filtered: list[dict[str, Any]] = []
    for client in clients:
        if not isinstance(client, dict):
            continue
        same_uuid = str(client.get("id") or "") == target_uuid
        same_email = (
            target_email is not None
            and str(client.get("email", "")).lower() == target_email
        )
        if same_uuid or same_email:
            continue
        filtered.append(client)

    settings_obj["clients"] = filtered
    updated["settings"] = json.dumps(settings_obj, ensure_ascii=False)
    return build_inbound_update_payload(updated)


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

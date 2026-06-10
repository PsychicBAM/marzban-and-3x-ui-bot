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


@dataclass(frozen=True, slots=True)
class ReplaceClientResult:
    matched_by: str
    updated_fields: tuple[str, ...]
    preserved_id: str | None
    preserved_sub_id: str | None
    client_email: str | None
    before_after: tuple[tuple[str, Any, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ClientUpdateExpectation:
    enable: bool | None = None
    limit_ip: int | None = None
    total_gb_bytes: int | None = None
    expiry_time_ms: int | None = None
    flow: str | None = None
    flow_required: bool = False


_CLIENT_IDENTITY_FIELDS = ("id", "subId", "uuid")
_CLIENT_PRESERVED_FIELDS = (
    "id",
    "email",
    "subId",
    "flow",
    "tgId",
    "reset",
    "totalGB",
    "expiryTime",
    "enable",
    "limitIp",
    "alterId",
)
_CLIENT_TRACKED_UPDATE_FIELDS = ("enable", "limitIp", "totalGB", "expiryTime", "flow")
_PANEL_BOOL_FALSE = frozenset({"false", "0", "no", "off"})
_PANEL_BOOL_TRUE = frozenset({"true", "1", "yes", "on"})


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


def read_panel_bool(value: Any, *, default_if_missing: bool = True) -> bool:
    if value is None:
        return default_if_missing
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return default_if_missing
        if normalized in _PANEL_BOOL_FALSE:
            return False
        if normalized in _PANEL_BOOL_TRUE:
            return True
    return bool(value)


def write_panel_bool(value: bool) -> bool:
    return bool(value)


def read_panel_int(value: Any, *, default: int = 0) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return default
        return int(float(cleaned))
    if isinstance(value, float):
        return int(value)
    return int(value)


def write_panel_int(value: int) -> int:
    return int(value)


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
    return updated


def merge_client_update(
    existing: dict[str, Any],
    updates: dict[str, Any],
) -> tuple[dict[str, Any], tuple[str, ...], dict[str, tuple[Any, Any]]]:
    merged = dict(existing)
    updated_fields: list[str] = []
    before_after: dict[str, tuple[Any, Any]] = {}

    for key in _CLIENT_TRACKED_UPDATE_FIELDS:
        if key not in updates:
            continue
        if key == "flow":
            new_flow = (str(updates[key]) if updates[key] is not None else "").strip()
            old_flow = str(merged.get("flow") or "")
            if new_flow:
                if old_flow != new_flow:
                    before_after[key] = (old_flow or None, new_flow)
                    merged["flow"] = new_flow
                    updated_fields.append("flow")
            elif "flow" in merged:
                before_after[key] = (old_flow or None, None)
                merged.pop("flow")
                updated_fields.append("flow")
            continue

        if key == "enable":
            old_value = read_panel_bool(merged.get("enable"), default_if_missing=True)
            new_value = write_panel_bool(read_panel_bool(updates[key], default_if_missing=True))
        else:
            old_value = read_panel_int(merged.get(key))
            new_value = write_panel_int(read_panel_int(updates[key]))

        if old_value != new_value:
            before_after[key] = (merged.get(key), new_value)
            merged[key] = new_value
            updated_fields.append(key)

    for field in _CLIENT_IDENTITY_FIELDS:
        if existing.get(field) is not None:
            merged[field] = existing[field]

    for key in _CLIENT_PRESERVED_FIELDS:
        if key in existing and key not in merged:
            merged[key] = existing[key]

    if "email" in updates:
        merged["email"] = updates["email"]

    return merged, tuple(updated_fields), before_after


def client_update_verification_errors(
    client: dict[str, Any],
    expected: ClientUpdateExpectation,
) -> list[str]:
    errors: list[str] = []
    if expected.enable is not None:
        actual_enable = read_panel_bool(client.get("enable"), default_if_missing=True)
        if actual_enable != expected.enable:
            errors.append(
                f"expected enable={expected.enable} got {actual_enable} (raw={client.get('enable')!r})",
            )
    if expected.limit_ip is not None:
        actual_limit = read_panel_int(client.get("limitIp"))
        if actual_limit != expected.limit_ip:
            errors.append(
                f"expected limitIp={expected.limit_ip} got {actual_limit}",
            )
    if expected.total_gb_bytes is not None:
        actual_total = read_panel_int(client.get("totalGB"))
        if actual_total != expected.total_gb_bytes:
            errors.append(
                f"expected totalGB={expected.total_gb_bytes} got {actual_total}",
            )
    if expected.expiry_time_ms is not None:
        actual_expiry = read_panel_int(client.get("expiryTime"))
        if actual_expiry != expected.expiry_time_ms:
            errors.append(
                f"expected expiryTime={expected.expiry_time_ms} got {actual_expiry}",
            )
    if expected.flow_required or expected.flow is not None:
        actual_flow = str(client.get("flow") or "")
        expected_flow = str(expected.flow or "")
        if actual_flow != expected_flow:
            errors.append(f"expected flow={expected_flow!r} got {actual_flow!r}")
    return errors


def client_matches_update_expectation(
    client: dict[str, Any],
    expected: ClientUpdateExpectation,
) -> bool:
    return not client_update_verification_errors(client, expected)


def replace_client_in_inbound(
    inbound: dict[str, Any],
    criteria: ClientDeleteCriteria,
    client_updates: dict[str, Any],
) -> tuple[dict[str, Any], ReplaceClientResult]:
    updated = dict(inbound)
    settings_obj = parse_settings_field(updated.get("settings"))
    clients = _client_list(settings_obj)

    matched_by: str | None = None
    merged_client: dict[str, Any] | None = None
    updated_fields: tuple[str, ...] = ()
    before_after: dict[str, tuple[Any, Any]] = {}
    for index, item in enumerate(clients):
        if not isinstance(item, dict):
            continue
        match_field = client_matches_delete_criteria(item, criteria)
        if match_field is None:
            continue
        merged_client, updated_fields, before_after = merge_client_update(item, client_updates)
        clients[index] = merged_client
        matched_by = match_field
        break

    if matched_by is None or merged_client is None:
        label = criteria.email or criteria.client_uuid or criteria.sub_id or "unknown"
        raise VpnPanelNotFoundError(
            f"3x-ui client '{label}' not found in inbound for update",
            panel="xui",
        )

    updated["settings"] = json.dumps(settings_obj, ensure_ascii=False)
    result = ReplaceClientResult(
        matched_by=matched_by,
        updated_fields=updated_fields,
        preserved_id=str(merged_client.get("id") or "") or None,
        preserved_sub_id=str(merged_client.get("subId") or "") or None,
        client_email=str(merged_client.get("email") or "") or None,
        before_after=tuple(
            (field, before, after) for field, (before, after) in before_after.items()
        ),
    )
    return updated, result


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
    return updated, result


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

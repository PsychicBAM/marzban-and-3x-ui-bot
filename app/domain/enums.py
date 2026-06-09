from __future__ import annotations

from enum import StrEnum


class IssuingMode(StrEnum):
    MARZBAN = "marzban"
    XUI = "xui"
    BOTH = "both"


class PanelType(StrEnum):
    MARZBAN = "marzban"
    XUI = "xui"


class VpnAccountStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"
    DELETED = "deleted"


class PaymentRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROVISIONING_FAILED = "provisioning_failed"
    PROVISIONING_PARTIAL = "provisioning_partial"


class PaymentRequestType(StrEnum):
    PURCHASE = "purchase"
    RENEWAL = "renewal"


class ReceiptFileType(StrEnum):
    PHOTO = "photo"
    DOCUMENT = "document"
    TEXT = "text"


class NotificationType(StrEnum):
    EXPIRY_7D = "expiry_7d"
    EXPIRY_3D = "expiry_3d"
    EXPIRY_1D = "expiry_1d"
    EXPIRED = "expired"


class ProvisionAction(StrEnum):
    CREATE_NEW = "create_new"
    RENEW_ACTIVE = "renew_active"
    RENEW_FROM_NOW = "renew_from_now"
    RENEW_REENABLE_DISABLED = "renew_reenable_disabled"


class AdminActionType(StrEnum):
    PAYMENT_APPROVED = "payment_approved"
    PAYMENT_REJECTED = "payment_rejected"
    PAYMENT_REQUEST_ADMIN_NOTIFIED = "payment_request_admin_notified"
    VPN_PROVISIONED = "vpn_provisioned"
    VPN_PROVISIONING_FAILED = "vpn_provisioning_failed"
    VPN_PROVISIONING_PARTIAL = "vpn_provisioning_partial"
    QR_GENERATION_FAILED = "qr_generation_failed"
    CLIENT_RENEWED = "client_renewed"
    CLIENT_DISABLED = "client_disabled"
    CLIENT_ENABLED = "client_enabled"
    CLIENT_DELETED = "client_deleted"
    ADMIN_SENT_VPN_LINK = "admin_sent_vpn_link"
    ADMIN_SENT_VPN_QR = "admin_sent_vpn_qr"
    VPN_ACCOUNT_IPS_CLEARED = "vpn_account_ips_cleared"
    VPN_ACCOUNT_MANUALLY_EXTENDED = "vpn_account_manually_extended"
    TARIFF_CREATED = "tariff_created"
    TARIFF_UPDATED = "tariff_updated"
    IP_LIMIT_CHANGED = "ip_limit_changed"
    NOTIFICATION_SETTINGS_UPDATED = "notification_settings_updated"
    NOTIFICATION_TEST_SENT = "notification_test_sent"
    EXPIRY_NOTIFICATION_SENT = "expiry_notification_sent"
    EXPIRED_NOTIFICATION_SENT = "expired_notification_sent"
    NOTIFICATION_JOB_FAILED = "notification_job_failed"
    MANUAL_VPN_CREATED = "manual_vpn_created"
    MANUAL_VPN_SENT_TO_CUSTOMER = "manual_vpn_sent_to_customer"
    PAYMENT_SETTINGS_UPDATED = "payment_settings_updated"
    PAYMENT_SETTINGS_CLEARED = "payment_settings_cleared"
    SUPPORT_SETTINGS_UPDATED = "support_settings_updated"
    SUPPORT_SETTINGS_CLEARED = "support_settings_cleared"
    INSTRUCTION_SETTINGS_UPDATED = "instruction_settings_updated"
    INSTRUCTION_SETTINGS_CLEARED = "instruction_settings_cleared"

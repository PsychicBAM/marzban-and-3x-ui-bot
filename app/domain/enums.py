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
    FREE_PLAN_ACTIVATED = "free_plan_activated"
    SUBSCRIPTION_RENEWAL_SELECTED = "subscription_renewal_selected"
    SEPARATE_SUBSCRIPTION_SELECTED = "separate_subscription_selected"
    VPN_ACCOUNT_NAME_GENERATED = "vpn_account_name_generated"
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
    BROADCAST_CREATED = "broadcast_created"
    BROADCAST_SENT = "broadcast_sent"
    BROADCAST_FAILED = "broadcast_failed"
    PROMO_CODE_CREATED = "promo_code_created"
    PROMO_CODE_DISABLED = "promo_code_disabled"
    PROMO_CODE_ENABLED = "promo_code_enabled"
    PROMO_CODE_APPLIED = "promo_code_applied"
    PROMO_CODE_REDEEMED = "promo_code_redeemed"
    REFERRAL_REGISTERED = "referral_registered"
    REFERRAL_PAID = "referral_paid"
    REFERRAL_REWARD_APPLIED = "referral_reward_applied"
    REFERRAL_REWARD_PENDING = "referral_reward_pending"
    REFERRAL_SETTINGS_UPDATED = "referral_settings_updated"


class ReferralEventStatus(StrEnum):
    REGISTERED = "registered"
    PAID = "paid"
    REWARDED = "rewarded"
    REJECTED = "rejected"


class ReferralRewardType(StrEnum):
    PER_REFERRAL = "per_referral"
    MILESTONE = "milestone"
    MANUAL = "manual"


class ReferralRewardStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    CANCELED = "canceled"


class PromoDiscountType(StrEnum):
    PERCENT = "percent"
    FIXED_AMOUNT = "fixed_amount"
    EXTRA_DAYS = "extra_days"


class PromoRequestScope(StrEnum):
    PURCHASE = "purchase"
    RENEWAL = "renewal"
    ANY = "any"


class BroadcastTargetType(StrEnum):
    ALL = "all"
    ACTIVE_VPN = "active_vpn"
    EXPIRED_VPN = "expired_vpn"
    NO_ACTIVE_VPN = "no_active_vpn"
    EXPIRING_SOON = "expiring_soon"
    PROMO_ENABLED = "promo_enabled"


class BroadcastStatus(StrEnum):
    DRAFT = "draft"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SCHEDULED = "scheduled"


class BroadcastRecipientStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BLOCKED = "blocked"

from aiogram import Router

from app.presentation.handlers.admin.broadcast import router as admin_broadcast_router
from app.presentation.handlers.admin.promo_codes import router as admin_promo_codes_router
from app.presentation.handlers.admin.referrals import router as admin_referrals_router
from app.presentation.handlers.admin.clients import router as admin_clients_router
from app.presentation.handlers.admin.settings import router as admin_settings_router
from app.presentation.handlers.admin.settings_instruction import router as admin_settings_instruction_router
from app.presentation.handlers.admin.settings_payment import router as admin_settings_payment_router
from app.presentation.handlers.admin.settings_support import router as admin_settings_support_router
from app.presentation.handlers.admin.support_tickets import router as admin_support_tickets_router
from app.presentation.handlers.admin.system_status import router as admin_system_status_router
from app.presentation.handlers.admin.statistics import router as admin_statistics_router
from app.presentation.handlers.admin.manual_key import router as admin_manual_key_router
from app.presentation.handlers.admin.menu import router as admin_menu_router
from app.presentation.handlers.admin.requests import router as admin_requests_router
from app.presentation.handlers.admin.tariff_actions import router as admin_tariff_actions_router
from app.presentation.handlers.admin.tariff_create import router as admin_tariff_create_router
from app.presentation.handlers.admin.tariff_edit import router as admin_tariff_edit_router
from app.presentation.handlers.admin.tariffs import router as admin_tariffs_router
from app.presentation.handlers.customer.guide import router as customer_guide_router
from app.presentation.handlers.customer.history import router as customer_history_router
from app.presentation.handlers.customer.faq import router as customer_faq_router
from app.presentation.handlers.customer.language import router as customer_language_router
from app.presentation.handlers.customer.support_tickets import router as customer_support_tickets_router
from app.presentation.handlers.customer.promo_checkout import router as customer_promo_checkout_router
from app.presentation.handlers.customer.referral import router as customer_referral_router
from app.presentation.handlers.customer.promo_settings import router as customer_promo_settings_router
from app.presentation.handlers.customer.my_vpn import router as customer_my_vpn_router
from app.presentation.handlers.customer.purchase import router as customer_purchase_router
from app.presentation.handlers.customer.renewal import router as customer_renewal_router
from app.presentation.handlers.start import router as start_router


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_router(start_router)
    root.include_router(customer_promo_checkout_router)
    root.include_router(customer_referral_router)
    root.include_router(customer_purchase_router)
    root.include_router(customer_renewal_router)
    root.include_router(customer_my_vpn_router)
    root.include_router(customer_history_router)
    root.include_router(customer_language_router)
    root.include_router(customer_guide_router)
    root.include_router(customer_faq_router)
    root.include_router(customer_support_tickets_router)
    root.include_router(customer_promo_settings_router)
    root.include_router(admin_requests_router)
    root.include_router(admin_clients_router)
    root.include_router(admin_settings_router)
    root.include_router(admin_settings_payment_router)
    root.include_router(admin_settings_support_router)
    root.include_router(admin_settings_instruction_router)
    root.include_router(admin_statistics_router)
    root.include_router(admin_system_status_router)
    root.include_router(admin_support_tickets_router)
    root.include_router(admin_tariffs_router)
    root.include_router(admin_tariff_create_router)
    root.include_router(admin_tariff_edit_router)
    root.include_router(admin_tariff_actions_router)
    root.include_router(admin_manual_key_router)
    root.include_router(admin_broadcast_router)
    root.include_router(admin_promo_codes_router)
    root.include_router(admin_referrals_router)
    root.include_router(admin_menu_router)
    return root

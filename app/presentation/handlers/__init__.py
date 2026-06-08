from aiogram import Router

from app.presentation.handlers.admin.clients import router as admin_clients_router
from app.presentation.handlers.admin.settings import router as admin_settings_router
from app.presentation.handlers.admin.settings_instruction import router as admin_settings_instruction_router
from app.presentation.handlers.admin.settings_payment import router as admin_settings_payment_router
from app.presentation.handlers.admin.settings_support import router as admin_settings_support_router
from app.presentation.handlers.admin.statistics import router as admin_statistics_router
from app.presentation.handlers.admin.manual_key import router as admin_manual_key_router
from app.presentation.handlers.admin.menu import router as admin_menu_router
from app.presentation.handlers.admin.requests import router as admin_requests_router
from app.presentation.handlers.admin.tariff_actions import router as admin_tariff_actions_router
from app.presentation.handlers.admin.tariff_create import router as admin_tariff_create_router
from app.presentation.handlers.admin.tariff_edit import router as admin_tariff_edit_router
from app.presentation.handlers.admin.tariffs import router as admin_tariffs_router
from app.presentation.handlers.customer.menu import router as customer_menu_router
from app.presentation.handlers.customer.my_vpn import router as customer_my_vpn_router
from app.presentation.handlers.customer.purchase import router as customer_purchase_router
from app.presentation.handlers.customer.renewal import router as customer_renewal_router
from app.presentation.handlers.start import router as start_router


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_router(start_router)
    root.include_router(customer_purchase_router)
    root.include_router(customer_renewal_router)
    root.include_router(customer_my_vpn_router)
    root.include_router(customer_menu_router)
    root.include_router(admin_requests_router)
    root.include_router(admin_clients_router)
    root.include_router(admin_settings_router)
    root.include_router(admin_settings_payment_router)
    root.include_router(admin_settings_support_router)
    root.include_router(admin_settings_instruction_router)
    root.include_router(admin_statistics_router)
    root.include_router(admin_tariffs_router)
    root.include_router(admin_tariff_create_router)
    root.include_router(admin_tariff_edit_router)
    root.include_router(admin_tariff_actions_router)
    root.include_router(admin_manual_key_router)
    root.include_router(admin_menu_router)
    return root

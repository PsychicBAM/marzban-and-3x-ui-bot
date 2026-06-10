from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SUPPORTED_LANGS = ("ru", "en")
DEFAULT_LANG = "ru"

LANG_RU = "ru"
LANG_EN = "en"

LANG_SET_RU = "lang:set:ru"
LANG_SET_EN = "lang:set:en"
LANG_BACK = "lang:back"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "menu.buy_vpn": "🛒 Купить VPN",
        "menu.renew_vpn": "🔄 Продлить VPN",
        "menu.my_vpn": "📊 Мой VPN",
        "menu.instruction": "ℹ️ Инструкция",
        "menu.support": "🆘 Поддержка",
        "menu.invite_friend": "🎁 Пригласить друга",
        "menu.promo_news": "🔔 Акции и новости",
        "menu.language": "🌐 Язык",
        "menu.placeholder": "Выберите действие",
        "start.greeting": "Здравствуйте, {name}!\n\nДобро пожаловать в VPN-бот.\nВыберите действие в меню ниже.",
        "start.admin_note": "\n\n🔐 У вас есть доступ к админ-панели.",
        "lang.choose": "🌐 Выберите язык",
        "lang.changed_ru": "✅ Язык изменён на русский",
        "lang.changed_en": "✅ Language changed to English",
        "lang.back": "🔙 Назад",
        "lang.russian": "🇷🇺 Русский",
        "lang.english": "🇬🇧 English",
        "common.cancel_done": "✅ Действие отменено.",
        "common.session_expired": "Сессия истекла. Начните заново.",
        "common.session_expired_purchase": "Сессия истекла. Начните покупку заново.",
        "common.session_expired_renewal": "Сессия истекла. Начните продление заново.",
        "common.plan_unavailable": "Тариф недоступен.",
        "common.start_first": "Отправьте /start.",
        "common.main_menu": "Выберите действие в меню.",
        "common.main_menu_short": "🏠 Главное меню",
        "common.invalid_request": "Некорректный запрос.",
        "common.vpn_not_found": "VPN не найден.",
        "common.saved": "Сохранено.",
        "common.already_actual": "Настройки уже актуальны.",
        "common.invalid_plan": "Некорректный тариф.",
        "common.no_active_vpn": "Активный VPN не найден.",
        "common.free_use_button": "Для бесплатного тарифа нажмите «🎁 Активировать бесплатно».",
        "common.pending_purchase": "⏳ У вас уже есть заявка на проверке. Дождитесь ответа администратора.",
        "common.pending_renewal": "⏳ У вас уже есть заявка на продление на проверке.",
        "common.enter_subscription_name": "Сначала введите название подписки.",
        "common.done": "Готово.",
        "purchase.subscription_data_missing": "Данные подписки не найдены. Начните заново.",
        "purchase.no_plans": "😔 Сейчас нет доступных тарифов. Попробуйте позже или обратитесь в поддержку.",
        "purchase.choose_plan": "🛒 <b>Выберите тариф:</b>",
        "purchase.subscription_choice": "У вас уже есть активный VPN. Что вы хотите сделать?",
        "purchase.renew_which": "🔄 <b>Какую подписку продлить?</b>",
        "purchase.separate_name": (
            "✏️ Введите название для новой подписки <b>латиницей</b>.\n\n"
            "Примеры: <code>grandma</code>, <code>phone</code>, <code>work</code>\n"
            "/cancel для отмены"
        ),
        "purchase.invalid_receipt": (
            "Пожалуйста, отправьте <b>фото</b> или <b>документ</b> с чеком об оплате.\n"
            "Если не можете прикрепить файл — отправьте текстовый комментарий."
        ),
        "purchase.receipt_prompt": (
            "📎 Отправьте <b>скриншот или фото чека</b> об оплате.\n"
            "Можно также отправить документ или текстовый комментарий.\n\n"
            "/cancel для отмены"
        ),
        "purchase.success": "✅ Заявка отправлена администратору. После проверки VPN будет активирован.",
        "purchase.cancel": "❌ Покупка отменена.",
        "purchase.promo_activated": "✅ VPN активирован по промокоду.",
        "renewal.no_plans": "😔 Сейчас нет доступных тарифов. Попробуйте позже или обратитесь в поддержку.",
        "renewal.choose_plan": "🔄 <b>Выберите тариф для продления:</b>",
        "renewal.invalid_receipt": (
            "Пожалуйста, отправьте <b>фото</b> или <b>документ</b> с чеком об оплате.\n"
            "Если не можете прикректить файл — отправьте текстовый комментарий."
        ),
        "renewal.receipt_prompt": (
            "📎 Отправьте <b>скриншот или фото чека</b> за продление.\n"
            "Можно также отправить документ или текстовый комментарий.\n\n"
            "/cancel для отмены"
        ),
        "renewal.success": "✅ Заявка на продление отправлена администратору. После проверки VPN будет продлён.",
        "renewal.cancel": "❌ Продление отменено.",
        "renewal.promo_activated": "✅ VPN продлён по промокоду.",
        "myvpn.no_vpn": "У вас пока нет активного VPN. Нажмите «🛒 Купить VPN».",
        "myvpn.title": "📊 <b>Мой VPN</b>",
        "myvpn.list_title": "📊 <b>Мои подписки</b>",
        "myvpn.list_choose": "Выберите подписку:",
        "myvpn.subscription_line": "• <b>{title}</b>{primary} — {status}, до {expiry}",
        "myvpn.primary_mark": " ⭐",
        "myvpn.account": "👤 Аккаунт: <code>{name}</code>",
        "myvpn.status": "📌 Статус: {status}",
        "myvpn.expiry": "📅 Действует до: {expiry}",
        "myvpn.traffic": "📶 Трафик: {traffic}",
        "myvpn.links_title": "🔗 <b>Ваши ссылки для подключения:</b>",
        "myvpn.link_line": "<b>{panel}</b>:\n{url}",
        "myvpn.links_error": "Не удалось получить ссылку. Свяжитесь с поддержкой.",
        "myvpn.traffic_warning": "⚠️ Не удалось обновить трафик, показаны сохранённые данные.",
        "myvpn.subscription_label": "🏷 Подписка: <b>{title}</b>",
        "myvpn.plan": "📦 Тариф: {plan}",
        "myvpn.days_left": "⏳ Осталось: {days}",
        "myvpn.traffic_full": "📶 Трафик: {used} / {limit}",
        "myvpn.devices": "📱 Устройств: {count}",
        "myvpn.panels": "🖥 Панели: {panels}",
        "myvpn.status.active": "Активен",
        "myvpn.status.expired": "Истёк",
        "myvpn.status.disabled": "Отключён",
        "myvpn.status.deleted": "Удалён",
        "myvpn.days_unit": "{n} дн.",
        "myvpn.unlimited": "Безлимит",
        "myvpn.traffic.zero": "0 ГБ",
        "myvpn.traffic.gb": "{n} ГБ",
        "myvpn.traffic.mb": "{n} МБ",
        "promo.prompt": "У вас есть промокод?",
        "promo.prompt_title": "🎁 <b>{text}</b>",
        "promo.code_prompt": "🎁 Введите промокод:\n/cancel для отмены",
        "promo.checkout_cancel": "❌ Оформление отменено.",
        "promo.settings.title": "🔔 <b>Акции и новости</b>: <b>{status}</b>",
        "promo.settings.desc": "Когда выключено, промо-рассылки от бота не приходят.",
        "promo.settings.on": "включены",
        "promo.settings.off": "выключены",
        "promo.applied_title": "🎁 <b>Промокод применён</b>",
        "promo.applied_code": "Код: <code>{code}</code>",
        "promo.applied_was": "Было: <b>{amount:.0f} ₽</b>",
        "promo.applied_discount": "Скидка: <b>{amount:.0f} ₽</b>",
        "promo.applied_final": "К оплате: <b>{amount:.0f} ₽</b>",
        "promo.applied_extra_days": "➕ Дополнительно: <b>{days} дн.</b>",
        "referral.home": (
            "🎁 Пригласить друга\n\n"
            "🔗 Ваша ссылка:\n{link}\n\n"
            "👥 Приглашено: {invited}\n"
            "💳 Оплатили: {paid}\n"
            "✅ Начислено дней: {earned}\n"
            "⏳ Ожидает: {pending} дн.\n"
            "🏆 До цели: {progress}/{target}"
        ),
        "referral.link": (
            "🔗 Ваша реферальная ссылка:\n\n{link}\n\n"
            "Отправьте её другу — бонус начислится после его оплаты."
        ),
        "referral.stats": (
            "📊 Реферальная статистика\n\n"
            "👥 Приглашено: {invited}\n"
            "💳 Оплатили: {paid}\n"
            "✅ Начислено дней: {earned}\n"
            "⏳ Ожидает начисления: {pending} дн.\n"
            "🏆 Прогресс к цели: {progress}/{target}"
        ),
        "referral.bonuses_empty": "🎁 Мои бонусы\n\nПока нет бонусов.",
        "referral.bonuses_title": "🎁 Мои бонусы",
        "referral.bonus_line": "• +{days} дн. {type}{who} — {status}",
        "referral.bonus_per_friend": "за друга",
        "referral.bonus_milestone": "за цель",
        "referral.bonus_manual": "вручную",
        "referral.bonus_pending": "⏳ ожидает",
        "referral.bonus_applied": "✅ начислен",
        "referral.bonus_canceled": "❌ отменён",
        "referral.apply_done": "✅ Начислено бонусов: {count}.",
        "referral.apply_pending": "⏳ Бонусы ожидают. Нужен активный VPN для начисления.",
        "referral.apply_none": "Нет бонусов для начисления.",
        "referral.apply_no_vpn": "Нет активного VPN.",
        "referral.apply_done_cb": "Готово.",
        "referral.notify_friend_paid": "🎁 Ваш друг оплатил VPN. Вам начислено +{days} дней!",
        "referral.notify_milestone": "🎉 Цель достигнута! Вам начислено +{days} дней!",
        "referral.notify_pending": (
            "🎁 Ваш друг оплатил VPN. Вам начислено +{days} дней! "
            "Активируйте VPN, чтобы применить бонус."
        ),
        "support.title": "🆘 <b>Поддержка</b>",
        "instruction.title": "📖 <b>Инструкция</b>",
        "user.default_name": "Пользователь",
    },
    "en": {
        "menu.buy_vpn": "🛒 Buy VPN",
        "menu.renew_vpn": "🔄 Renew VPN",
        "menu.my_vpn": "📊 My VPN",
        "menu.instruction": "ℹ️ Instructions",
        "menu.support": "🆘 Support",
        "menu.invite_friend": "🎁 Invite a friend",
        "menu.promo_news": "🔔 Promotions & news",
        "menu.language": "🌐 Language",
        "menu.placeholder": "Choose an action",
        "start.greeting": "Hello, {name}!\n\nWelcome to the VPN bot.\nChoose an action from the menu below.",
        "start.admin_note": "\n\n🔐 You have access to the admin panel.",
        "lang.choose": "🌐 Choose language",
        "lang.changed_ru": "✅ Язык изменён на русский",
        "lang.changed_en": "✅ Language changed to English",
        "lang.back": "🔙 Back",
        "lang.russian": "🇷🇺 Русский",
        "lang.english": "🇬🇧 English",
        "common.cancel_done": "✅ Action cancelled.",
        "common.session_expired": "Session expired. Please start again.",
        "common.session_expired_purchase": "Session expired. Please start purchase again.",
        "common.session_expired_renewal": "Session expired. Please start renewal again.",
        "common.plan_unavailable": "Plan is unavailable.",
        "common.start_first": "Please send /start.",
        "common.main_menu": "Choose an action from the menu.",
        "common.main_menu_short": "🏠 Main menu",
        "common.invalid_request": "Invalid request.",
        "common.vpn_not_found": "VPN not found.",
        "common.saved": "Saved.",
        "common.already_actual": "Settings are already up to date.",
        "common.invalid_plan": "Invalid plan.",
        "common.no_active_vpn": "No active VPN found.",
        "common.free_use_button": "For a free plan, tap «🎁 Activate for free».",
        "common.pending_purchase": "⏳ You already have a request under review. Please wait for the admin.",
        "common.pending_renewal": "⏳ You already have a renewal request under review.",
        "common.enter_subscription_name": "Enter a subscription name first.",
        "common.done": "Done.",
        "purchase.subscription_data_missing": "Subscription data not found. Please start again.",
        "purchase.no_plans": "😔 No plans available right now. Try again later or contact support.",
        "purchase.choose_plan": "🛒 <b>Choose a plan:</b>",
        "purchase.subscription_choice": "You already have an active VPN. What would you like to do?",
        "purchase.renew_which": "🔄 <b>Which subscription to renew?</b>",
        "purchase.separate_name": (
            "✏️ Enter a name for the new subscription in <b>Latin letters</b>.\n\n"
            "Examples: <code>grandma</code>, <code>phone</code>, <code>work</code>\n"
            "/cancel to cancel"
        ),
        "purchase.invalid_receipt": (
            "Please send a <b>photo</b> or <b>document</b> with your payment receipt.\n"
            "If you cannot attach a file, send a text comment."
        ),
        "purchase.receipt_prompt": (
            "📎 Send a <b>screenshot or photo of the receipt</b> for payment.\n"
            "You can also send a document or text comment.\n\n"
            "/cancel to cancel"
        ),
        "purchase.success": "✅ Your request was sent to the admin. VPN will be activated after review.",
        "purchase.cancel": "❌ Purchase cancelled.",
        "purchase.promo_activated": "✅ VPN activated with promo code.",
        "renewal.no_plans": "😔 No plans available right now. Try again later or contact support.",
        "renewal.choose_plan": "🔄 <b>Choose a plan to renew:</b>",
        "renewal.invalid_receipt": (
            "Please send a <b>photo</b> or <b>document</b> with your payment receipt.\n"
            "If you cannot attach a file, send a text comment."
        ),
        "renewal.receipt_prompt": (
            "📎 Send a <b>screenshot or photo of the receipt</b> for renewal.\n"
            "You can also send a document or text comment.\n\n"
            "/cancel to cancel"
        ),
        "renewal.success": "✅ Renewal request sent to the admin. VPN will be extended after review.",
        "renewal.cancel": "❌ Renewal cancelled.",
        "renewal.promo_activated": "✅ VPN renewed with promo code.",
        "myvpn.no_vpn": "You don't have an active VPN yet. Tap «🛒 Buy VPN».",
        "myvpn.title": "📊 <b>My VPN</b>",
        "myvpn.list_title": "📊 <b>My subscriptions</b>",
        "myvpn.list_choose": "Choose a subscription:",
        "myvpn.subscription_line": "• <b>{title}</b>{primary} — {status}, until {expiry}",
        "myvpn.primary_mark": " ⭐",
        "myvpn.account": "👤 Account: <code>{name}</code>",
        "myvpn.status": "📌 Status: {status}",
        "myvpn.expiry": "📅 Valid until: {expiry}",
        "myvpn.traffic": "📶 Traffic: {traffic}",
        "myvpn.links_title": "🔗 <b>Your connection links:</b>",
        "myvpn.link_line": "<b>{panel}</b>:\n{url}",
        "myvpn.links_error": "Could not fetch the link. Please contact support.",
        "myvpn.traffic_warning": "⚠️ Could not refresh traffic; showing saved data.",
        "myvpn.subscription_label": "🏷 Subscription: <b>{title}</b>",
        "myvpn.plan": "📦 Plan: {plan}",
        "myvpn.days_left": "⏳ Remaining: {days}",
        "myvpn.traffic_full": "📶 Traffic: {used} / {limit}",
        "myvpn.devices": "📱 Devices: {count}",
        "myvpn.panels": "🖥 Panels: {panels}",
        "myvpn.status.active": "Active",
        "myvpn.status.expired": "Expired",
        "myvpn.status.disabled": "Disabled",
        "myvpn.status.deleted": "Deleted",
        "myvpn.days_unit": "{n} days",
        "myvpn.unlimited": "Unlimited",
        "myvpn.traffic.zero": "0 GB",
        "myvpn.traffic.gb": "{n} GB",
        "myvpn.traffic.mb": "{n} MB",
        "promo.prompt": "Do you have a promo code?",
        "promo.prompt_title": "🎁 <b>{text}</b>",
        "promo.code_prompt": "🎁 Enter promo code:\n/cancel to cancel",
        "promo.checkout_cancel": "❌ Checkout cancelled.",
        "promo.settings.title": "🔔 <b>Promotions & news</b>: <b>{status}</b>",
        "promo.settings.desc": "When disabled, promotional broadcasts from the bot are not sent.",
        "promo.settings.on": "enabled",
        "promo.settings.off": "disabled",
        "promo.applied_title": "🎁 <b>Promo code applied</b>",
        "promo.applied_code": "Code: <code>{code}</code>",
        "promo.applied_was": "Was: <b>{amount:.0f} ₽</b>",
        "promo.applied_discount": "Discount: <b>{amount:.0f} ₽</b>",
        "promo.applied_final": "To pay: <b>{amount:.0f} ₽</b>",
        "promo.applied_extra_days": "➕ Extra: <b>{days} days</b>",
        "referral.home": (
            "🎁 Invite a friend\n\n"
            "🔗 Your link:\n{link}\n\n"
            "👥 Invited: {invited}\n"
            "💳 Paid: {paid}\n"
            "✅ Days earned: {earned}\n"
            "⏳ Pending: {pending} days\n"
            "🏆 To milestone: {progress}/{target}"
        ),
        "referral.link": (
            "🔗 Your referral link:\n\n{link}\n\n"
            "Share it with a friend — bonus applies after they pay."
        ),
        "referral.stats": (
            "📊 Referral statistics\n\n"
            "👥 Invited: {invited}\n"
            "💳 Paid: {paid}\n"
            "✅ Days earned: {earned}\n"
            "⏳ Pending: {pending} days\n"
            "🏆 Milestone progress: {progress}/{target}"
        ),
        "referral.bonuses_empty": "🎁 My bonuses\n\nNo bonuses yet.",
        "referral.bonuses_title": "🎁 My bonuses",
        "referral.bonus_line": "• +{days} days {type}{who} — {status}",
        "referral.bonus_per_friend": "per friend",
        "referral.bonus_milestone": "milestone",
        "referral.bonus_manual": "manual",
        "referral.bonus_pending": "⏳ pending",
        "referral.bonus_applied": "✅ applied",
        "referral.bonus_canceled": "❌ canceled",
        "referral.apply_done": "✅ Bonuses applied: {count}.",
        "referral.apply_pending": "⏳ Bonuses pending. Active VPN required to apply.",
        "referral.apply_none": "No bonuses to apply.",
        "referral.apply_no_vpn": "No active VPN.",
        "referral.apply_done_cb": "Done.",
        "referral.notify_friend_paid": "🎁 Your friend paid for VPN. You received +{days} days!",
        "referral.notify_milestone": "🎉 Milestone reached! You received +{days} days!",
        "referral.notify_pending": (
            "🎁 Your friend paid for VPN. You received +{days} days! "
            "Activate VPN to apply the bonus."
        ),
        "support.title": "🆘 <b>Support</b>",
        "instruction.title": "📖 <b>Instructions</b>",
        "user.default_name": "User",
    },
}


def normalize_lang(lang: str | None) -> str:
    if lang == LANG_EN:
        return LANG_EN
    return DEFAULT_LANG


def t(lang: str | None, key: str, **kwargs: object) -> str:
    code = normalize_lang(lang)
    bundle = TRANSLATIONS.get(code, TRANSLATIONS[DEFAULT_LANG])
    text = bundle.get(key) or TRANSLATIONS[DEFAULT_LANG].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


def all_menu_texts(key: str) -> list[str]:
    return [t(lang, key) for lang in SUPPORTED_LANGS]


def resolve_initial_language(telegram_language_code: str | None) -> str:
    if telegram_language_code and telegram_language_code.lower().startswith("en"):
        return LANG_EN
    return DEFAULT_LANG


def language_picker_keyboard(lang: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "lang.russian"), callback_data=LANG_SET_RU)],
            [InlineKeyboardButton(text=t(lang, "lang.english"), callback_data=LANG_SET_EN)],
            [InlineKeyboardButton(text=t(lang, "lang.back"), callback_data=LANG_BACK)],
        ],
    )

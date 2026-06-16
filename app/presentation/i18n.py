from __future__ import annotations

from html import escape

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
        "menu.my_vpn": "📊 Мой VPN",
        "menu.help": "🆘 Помощь",
        "menu.bonuses": "🎁 Бонусы",
        "menu.more": "⚙️ Ещё",
        "menu.renew_vpn": "🔄 Продлить VPN",
        "menu.guide": "📘 Инструкция",
        "menu.faq": "❓ FAQ",
        "menu.support": "🆘 Поддержка",
        "menu.invite_friend": "🎁 Пригласить друга",
        "menu.promo_news": "🔔 Акции и новости",
        "menu.promo_codes": "🏷 Промокоды",
        "menu.language": "🌐 Язык",
        "menu.history": "📜 История",
        "menu.back": "🔙 Назад",
        "menu.placeholder": "Выберите действие",
        "submenu.help.intro": "🆘 Помощь\nВыберите раздел:",
        "submenu.bonuses.intro": "🎁 Бонусы\nЗдесь находятся скидки, рефералы и новости.",
        "submenu.bonuses.promo_codes_info": (
            "Промокод можно ввести во время покупки или продления VPN."
        ),
        "submenu.more.intro": "⚙️ Ещё\nДополнительные разделы:",
        "start.greeting": (
            "Здравствуйте, {first_name}!\n\n"
            "Добро пожаловать в KeyGate VPN — быстрый и стабильный доступ к интернету.\n\n"
            "Что можно сделать:\n"
            "🛒 Купить VPN — выбрать тариф и оформить подписку\n"
            "📊 Мой VPN — ссылки, QR-код, продление и статус подписки\n"
            "🆘 Помощь — инструкция, FAQ и поддержка\n"
            "🎁 Бонусы — рефералы, акции и промокоды\n"
            "⚙️ Ещё — история и язык\n\n"
            "Выберите действие в меню ниже."
        ),
        "start.banner_caption": "👋 KeyGate VPN",
        "start.admin_note": "\n\n🔐 У вас есть доступ к админ-панели.",
        "start.menu_hint": "Выберите действие в меню ниже.",
        "lang.choose": "🌐 Выберите язык",
        "lang.changed_ru": "✅ Язык изменён на русский",
        "lang.changed_en": "✅ Language changed to English",
        "lang.back": "🔙 Назад",
        "lang.russian": "🇷🇺 Русский",
        "lang.english": "🇬🇧 English",
        "history.title": "📜 История",
        "history.empty": "История пока пустая.",
        "history.page": "Стр. {current}/{total}",
        "history.date": "Дата: {date}",
        "history.purchase_title": "✅ Покупка VPN",
        "history.renewal_title": "✅ Продление VPN",
        "history.purchase_days_amount": "{days} дней · {amount}",
        "history.free_plan_title": "🎁 Бесплатный тариф",
        "history.free_plan_days": "{days} дней",
        "history.promo_title": "🎁 Промокод {code}",
        "history.promo_discount": "Скидка: {amount}",
        "history.promo_final": "К оплате: {amount}",
        "history.referral_title": "🎁 Реферальный бонус",
        "history.referral_days": "+{days} дней",
        "history.vpn_disabled": "⛔ VPN отключён",
        "history.vpn_enabled": "✅ VPN включён",
        "history.vpn_deleted": "🗑 VPN удалён",
        "history.admin_renewal": "🔄 Продление администратором",
        "history.vpn_renewed": "🔄 VPN продлён",
        "support.title": "🆘 Поддержка",
        "support.choose_action": "Выберите действие:",
        "support.create_ticket": "➕ Создать обращение",
        "support.my_tickets": "📋 Мои обращения",
        "support.choose_topic": "Выберите тему обращения:",
        "support.enter_message": "Опишите проблему. Можно отправить текст, фото или файл.\n/cancel — отмена",
        "support.enter_reply": "Введите ответ. /cancel — отмена",
        "support.ticket_created": "✅ Обращение #{ticket_id} создано. Мы ответим как можно скорее.",
        "support.no_tickets": "У вас пока нет обращений.",
        "support.my_tickets_title": "📋 Мои обращения",
        "support.ticket_list_item": "#{ticket_id} · {topic} · {status}\n   {updated}",
        "support.ticket_detail_title": "Обращение #{ticket_id}",
        "support.ticket_topic": "Тема: {topic}",
        "support.ticket_status": "Статус: {status}",
        "support.reply": "✍️ Ответить",
        "support.close_ticket": "✅ Закрыть",
        "support.ticket_closed": "✅ Обращение #{ticket_id} закрыто.",
        "support.admin_replied_notify": "💬 Админ ответил на ваше обращение #{ticket_id}",
        "support.topic_payment": "💳 Оплата",
        "support.topic_connection": "🔌 Подключение",
        "support.topic_renewal": "🔄 Продление",
        "support.topic_other": "🧩 Другое",
        "support.status_open": "открыто",
        "support.status_answered": "есть ответ",
        "support.status_closed": "закрыто",
        "support.sender_admin": "Админ",
        "support.sender_system": "Система",
        "support.photo_attached": "📷 Фото",
        "support.file_attached": "📎 Файл",
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
        "purchase.banner_caption": "🛒 Купить VPN\nВыберите тариф для подключения.",
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
        "myvpn.get_link": "🔗 Получить ссылку",
        "myvpn.get_qr": "📷 Получить QR-code",
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
        "guide.card_caption": (
            "📘 <b>ИНСТРУКЦИЯ</b>\n"
            "На каком устройстве нужно настроить VPN?"
        ),
        "guide.btn.iphone": "📱 iPhone / iPad",
        "guide.btn.android": "🤖 Android",
        "guide.btn.mac": "🍎 Mac",
        "guide.btn.windows": "💻 Windows",
        "guide.btn.tv": "📺 Телевизор / TV",
        "guide.btn.back_menu": "🔙 Назад",
        "guide.btn.back_devices": "🔙 К устройствам",
        "guide.steps.iphone": (
            "<b>📱 iPhone / iPad</b>\n\n"
            "1. Откройте <b>📊 Мой VPN</b> и скопируйте ссылку или получите QR-код.\n"
            "2. Установите приложение v2RayTun, Streisand или Hiddify из App Store.\n"
            "3. В приложении нажмите «+» → «Import from clipboard» или отсканируйте QR.\n"
            "4. Выберите профиль и включите VPN."
        ),
        "guide.steps.android": (
            "<b>🤖 Android</b>\n\n"
            "1. Откройте <b>📊 Мой VPN</b> и скопируйте ссылку или получите QR-код.\n"
            "2. Установите v2rayNG или Hiddify из Google Play.\n"
            "3. Нажмите «+» → «Import config from clipboard» или отсканируйте QR.\n"
            "4. Нажмите подключение и разрешите VPN."
        ),
        "guide.steps.windows": (
            "<b>💻 Windows</b>\n\n"
            "1. Откройте <b>📊 Мой VPN</b> и скопируйте ссылку подписки.\n"
            "2. Установите Hiddify или v2rayN.\n"
            "3. Вставьте ссылку через «Import from clipboard» / «Add profile».\n"
            "4. Выберите сервер и подключитесь."
        ),
        "guide.steps.macos": (
            "<b>🍎 macOS</b>\n\n"
            "1. Откройте <b>📊 Мой VPN</b> и скопируйте ссылку или QR-код.\n"
            "2. Установите V2Box, Streisand или Hiddify.\n"
            "3. Импортируйте ссылку или отсканируйте QR.\n"
            "4. Включите VPN в приложении."
        ),
        "guide.steps.linux": (
            "<b>🐧 Linux</b>\n\n"
            "1. Откройте <b>📊 Мой VPN</b> и скопируйте ссылку подписки.\n"
            "2. Установите v2rayA, Nekoray или Hiddify.\n"
            "3. Импортируйте ссылку в клиент.\n"
            "4. Выберите профиль и подключитесь."
        ),
        "guide.steps.tv": (
            "<b>📺 Телевизор / Android TV</b>\n\n"
            "1. Откройте Google Play на телевизоре.\n"
            "2. Установите приложение Hiddify, v2rayNG или другое приложение "
            "с поддержкой VLESS/VMess/Trojan подписок.\n"
            "3. Откройте в боте <b>📊 Мой VPN</b> и скопируйте ссылку подписки.\n"
            "4. Отправьте ссылку на телевизор удобным способом: через Telegram Saved Messages, "
            "QR-код, браузер или приложение для передачи текста.\n"
            "5. Добавьте ссылку подписки в приложение на телевизоре.\n"
            "6. Нажмите обновить подписку и подключитесь.\n\n"
            "Если на телевизоре нет Google Play, используйте Android TV Box "
            "или установите приложение вручную через APK."
        ),
        "faq.title": "❓ <b>Частые вопросы</b>",
        "faq.choose": "Выберите вопрос:",
        "faq.btn.back_menu": "🔙 Назад",
        "faq.btn.back_list": "🔙 К вопросам",
        "faq.q.vpn_connect": "VPN не подключается",
        "faq.q.refresh_sub": "Как обновить подписку",
        "faq.q.device_limit": "Сколько устройств можно использовать",
        "faq.q.qr_code": "Где найти QR-код",
        "faq.q.renew": "Как продлить VPN",
        "faq.q.referral": "Как работает реферальная программа",
        "faq.q.promo_off": "Как отключить акции",
        "faq.a.vpn_connect": (
            "<b>VPN не подключается</b>\n\n"
            "• Проверьте срок подписки в <b>📊 Мой VPN</b>.\n"
            "• Обновите подписку в приложении (pull-to-refresh).\n"
            "• Переимпортируйте ссылку или QR-код.\n"
            "• Если не помогло — напишите в <b>🆘 Поддержка</b>."
        ),
        "faq.a.refresh_sub": (
            "<b>Как обновить подписку</b>\n\n"
            "В клиентском приложении найдите кнопку обновления подписки "
            "(↻ / Update subscription / Pull to refresh).\n\n"
            "Если ссылка изменилась — скопируйте новую из <b>📊 Мой VPN</b>."
        ),
        "faq.a.device_limit": (
            "<b>Сколько устройств можно использовать</b>\n\n"
            "Лимит указан в <b>📊 Мой VPN</b> (поле «Устройств»).\n"
            "Обычно это 1–3 устройства на подписку. "
            "При превышении лимита подключение может не работать."
        ),
        "faq.a.qr_code": (
            "<b>Где найти QR-код</b>\n\n"
            "1. Откройте <b>📊 Мой VPN</b>.\n"
            "2. Выберите подписку (если их несколько).\n"
            "3. Нажмите кнопку QR-кода — бот отправит изображения для подключения."
        ),
        "faq.a.renew": (
            "<b>Как продлить VPN</b>\n\n"
            "1. Нажмите <b>🔄 Продлить VPN</b> в главном меню.\n"
            "2. Выберите тариф и оплатите.\n"
            "3. Отправьте чек — после проверки срок будет продлён.\n\n"
            "Также продление доступно из карточки подписки в <b>📊 Мой VPN</b>."
        ),
        "faq.a.referral": (
            "<b>Как работает реферальная программа</b>\n\n"
            "1. Откройте <b>🎁 Пригласить друга</b> и отправьте ссылку другу.\n"
            "2. После оплаты VPN другом вам начисляются бонусные дни.\n"
            "3. Бонусы применяются к активной подписке автоматически или вручную."
        ),
        "faq.a.promo_off": (
            "<b>Как отключить акции</b>\n\n"
            "1. Откройте <b>🔔 Акции и новости</b> в главном меню.\n"
            "2. Нажмите «Выключить» — промо-рассылки от бота перестанут приходить."
        ),
        "user.default_name": "Пользователь",
    },
    "en": {
        "menu.buy_vpn": "🛒 Buy VPN",
        "menu.my_vpn": "📊 My VPN",
        "menu.help": "🆘 Help",
        "menu.bonuses": "🎁 Bonuses",
        "menu.more": "⚙️ More",
        "menu.renew_vpn": "🔄 Renew VPN",
        "menu.guide": "📘 Guide",
        "menu.faq": "❓ FAQ",
        "menu.support": "🆘 Support",
        "menu.invite_friend": "🎁 Invite a friend",
        "menu.promo_news": "🔔 News and offers",
        "menu.promo_codes": "🏷 Promo codes",
        "menu.language": "🌐 Language",
        "menu.history": "📜 History",
        "menu.back": "🔙 Back",
        "menu.placeholder": "Choose an action",
        "submenu.help.intro": "🆘 Help\nChoose a section:",
        "submenu.bonuses.intro": "🎁 Bonuses\nDiscounts, referrals, and news are here.",
        "submenu.bonuses.promo_codes_info": (
            "You can enter a promo code during VPN purchase or renewal."
        ),
        "submenu.more.intro": "⚙️ More\nAdditional sections:",
        "start.greeting": (
            "Hello, {first_name}!\n\n"
            "Welcome to KeyGate VPN — fast and reliable internet access.\n\n"
            "What you can do:\n"
            "🛒 Buy VPN — choose a plan and subscribe\n"
            "📊 My VPN — links, QR code, renewal, and subscription status\n"
            "🆘 Help — guide, FAQ, and support\n"
            "🎁 Bonuses — referrals, offers, and promo codes\n"
            "⚙️ More — history and language\n\n"
            "Choose an action from the menu below."
        ),
        "start.banner_caption": "👋 KeyGate VPN",
        "start.admin_note": "\n\n🔐 You have access to the admin panel.",
        "start.menu_hint": "Choose an action from the menu below.",
        "lang.choose": "🌐 Choose language",
        "lang.changed_ru": "✅ Язык изменён на русский",
        "lang.changed_en": "✅ Language changed to English",
        "lang.back": "🔙 Back",
        "lang.russian": "🇷🇺 Русский",
        "lang.english": "🇬🇧 English",
        "history.title": "📜 History",
        "history.empty": "Your history is empty.",
        "history.page": "Page {current}/{total}",
        "history.date": "Date: {date}",
        "history.purchase_title": "✅ VPN purchase",
        "history.renewal_title": "✅ VPN renewal",
        "history.purchase_days_amount": "{days} days · {amount}",
        "history.free_plan_title": "🎁 Free plan",
        "history.free_plan_days": "{days} days",
        "history.promo_title": "🎁 Promo code {code}",
        "history.promo_discount": "Discount: {amount}",
        "history.promo_final": "To pay: {amount}",
        "history.referral_title": "🎁 Referral bonus",
        "history.referral_days": "+{days} days",
        "history.vpn_disabled": "⛔ VPN disabled",
        "history.vpn_enabled": "✅ VPN enabled",
        "history.vpn_deleted": "🗑 VPN deleted",
        "history.admin_renewal": "🔄 Admin renewal",
        "history.vpn_renewed": "🔄 VPN renewed",
        "support.title": "🆘 Support",
        "support.choose_action": "Choose an action:",
        "support.create_ticket": "➕ Create ticket",
        "support.my_tickets": "📋 My tickets",
        "support.choose_topic": "Choose a topic:",
        "support.enter_message": "Describe your issue. You can send text, a photo, or a file.\n/cancel to cancel",
        "support.enter_reply": "Enter your reply. /cancel to cancel",
        "support.ticket_created": "✅ Ticket #{ticket_id} created. We will reply as soon as possible.",
        "support.no_tickets": "You have no tickets yet.",
        "support.my_tickets_title": "📋 My tickets",
        "support.ticket_list_item": "#{ticket_id} · {topic} · {status}\n   {updated}",
        "support.ticket_detail_title": "Ticket #{ticket_id}",
        "support.ticket_topic": "Topic: {topic}",
        "support.ticket_status": "Status: {status}",
        "support.reply": "✍️ Reply",
        "support.close_ticket": "✅ Close",
        "support.ticket_closed": "✅ Ticket #{ticket_id} closed.",
        "support.admin_replied_notify": "💬 Admin replied to your ticket #{ticket_id}",
        "support.topic_payment": "💳 Payment",
        "support.topic_connection": "🔌 Connection",
        "support.topic_renewal": "🔄 Renewal",
        "support.topic_other": "🧩 Other",
        "support.status_open": "open",
        "support.status_answered": "answered",
        "support.status_closed": "closed",
        "support.sender_admin": "Admin",
        "support.sender_system": "System",
        "support.photo_attached": "📷 Photo",
        "support.file_attached": "📎 File",
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
        "purchase.banner_caption": "🛒 Buy VPN\nChoose a plan to continue.",
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
        "myvpn.get_link": "🔗 Get link",
        "myvpn.get_qr": "📷 Get QR code",
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
        "guide.card_caption": (
            "📘 <b>GUIDE</b>\n"
            "Which device do you want to set up VPN on?"
        ),
        "guide.btn.iphone": "📱 iPhone / iPad",
        "guide.btn.android": "🤖 Android",
        "guide.btn.mac": "🍎 Mac",
        "guide.btn.windows": "💻 Windows",
        "guide.btn.tv": "📺 TV",
        "guide.btn.back_menu": "🔙 Back",
        "guide.btn.back_devices": "🔙 Back to devices",
        "guide.steps.iphone": (
            "<b>📱 iPhone / iPad</b>\n\n"
            "1. Open <b>📊 My VPN</b> and copy the link or get a QR code.\n"
            "2. Install v2RayTun, Streisand, or Hiddify from the App Store.\n"
            "3. Tap «+» → «Import from clipboard» or scan the QR code.\n"
            "4. Select the profile and turn VPN on."
        ),
        "guide.steps.android": (
            "<b>🤖 Android</b>\n\n"
            "1. Open <b>📊 My VPN</b> and copy the link or get a QR code.\n"
            "2. Install v2rayNG or Hiddify from Google Play.\n"
            "3. Tap «+» → «Import config from clipboard» or scan the QR.\n"
            "4. Connect and allow the VPN permission."
        ),
        "guide.steps.windows": (
            "<b>💻 Windows</b>\n\n"
            "1. Open <b>📊 My VPN</b> and copy the subscription link.\n"
            "2. Install Hiddify or v2rayN.\n"
            "3. Paste the link via «Import from clipboard» / «Add profile».\n"
            "4. Select a server and connect."
        ),
        "guide.steps.macos": (
            "<b>🍎 macOS</b>\n\n"
            "1. Open <b>📊 My VPN</b> and copy the link or QR code.\n"
            "2. Install V2Box, Streisand, or Hiddify.\n"
            "3. Import the link or scan the QR code.\n"
            "4. Enable VPN in the app."
        ),
        "guide.steps.linux": (
            "<b>🐧 Linux</b>\n\n"
            "1. Open <b>📊 My VPN</b> and copy the subscription link.\n"
            "2. Install v2rayA, Nekoray, or Hiddify.\n"
            "3. Import the link in the client.\n"
            "4. Select the profile and connect."
        ),
        "guide.steps.tv": (
            "<b>📺 TV / Android TV</b>\n\n"
            "1. Open Google Play on your TV.\n"
            "2. Install Hiddify, v2rayNG, or another app that supports "
            "VLESS/VMess/Trojan subscriptions.\n"
            "3. Open <b>📊 My VPN</b> in the bot and copy your subscription link.\n"
            "4. Send the link to your TV using Telegram Saved Messages, QR code, browser, "
            "or any text transfer app.\n"
            "5. Add the subscription link inside the TV app.\n"
            "6. Refresh the subscription and connect.\n\n"
            "If your TV does not have Google Play, use an Android TV Box "
            "or install the app manually with an APK."
        ),
        "faq.title": "❓ <b>FAQ</b>",
        "faq.choose": "Choose a question:",
        "faq.btn.back_menu": "🔙 Back",
        "faq.btn.back_list": "🔙 Back to questions",
        "faq.q.vpn_connect": "VPN does not connect",
        "faq.q.refresh_sub": "How to refresh subscription",
        "faq.q.device_limit": "Device limit",
        "faq.q.qr_code": "Where to find QR code",
        "faq.q.renew": "How to renew VPN",
        "faq.q.referral": "How referrals work",
        "faq.q.promo_off": "How to disable promo messages",
        "faq.a.vpn_connect": (
            "<b>VPN does not connect</b>\n\n"
            "• Check expiry in <b>📊 My VPN</b>.\n"
            "• Refresh the subscription in your app (pull-to-refresh).\n"
            "• Re-import the link or QR code.\n"
            "• Still stuck? Contact <b>🆘 Support</b>."
        ),
        "faq.a.refresh_sub": (
            "<b>How to refresh subscription</b>\n\n"
            "In your VPN app, use the update button "
            "(↻ / Update subscription / Pull to refresh).\n\n"
            "If the link changed, copy the new one from <b>📊 My VPN</b>."
        ),
        "faq.a.device_limit": (
            "<b>Device limit</b>\n\n"
            "The limit is shown in <b>📊 My VPN</b> (Devices field).\n"
            "Usually 1–3 devices per subscription. "
            "Exceeding the limit may block new connections."
        ),
        "faq.a.qr_code": (
            "<b>Where to find QR code</b>\n\n"
            "1. Open <b>📊 My VPN</b>.\n"
            "2. Select a subscription (if you have several).\n"
            "3. Tap the QR button — the bot will send connection images."
        ),
        "faq.a.renew": (
            "<b>How to renew VPN</b>\n\n"
            "1. Tap <b>🔄 Renew VPN</b> in the main menu.\n"
            "2. Choose a plan and pay.\n"
            "3. Send the receipt — your term will be extended after review.\n\n"
            "You can also renew from the subscription card in <b>📊 My VPN</b>."
        ),
        "faq.a.referral": (
            "<b>How referrals work</b>\n\n"
            "1. Open <b>🎁 Invite a friend</b> and share your link.\n"
            "2. When your friend pays for VPN, you earn bonus days.\n"
            "3. Bonuses apply to your active subscription automatically or manually."
        ),
        "faq.a.promo_off": (
            "<b>How to disable promo messages</b>\n\n"
            "1. Open <b>🔔 Promotions & news</b> in the main menu.\n"
            "2. Tap «Disable» — promotional broadcasts will stop."
        ),
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
        safe_kwargs = {
            key: escape(str(value), quote=False) if isinstance(value, str) else value
            for key, value in kwargs.items()
        }
        return text.format(**safe_kwargs)
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

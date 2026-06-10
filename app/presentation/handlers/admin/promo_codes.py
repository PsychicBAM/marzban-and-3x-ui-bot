from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import PromoCodeError
from app.application.services.plan_service import PlanService
from app.application.services.promo_code_service import PromoCodeDraft, PromoCodeService
from app.domain.enums import PromoDiscountType, PromoRequestScope
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_promo import (
    PC_BACK_ADMIN,
    PC_CANCEL,
    PC_CONFIRM,
    PC_CREATE,
    PC_HOME,
    PC_ITEM_PREFIX,
    PC_LIST,
    PC_PLAN_PREFIX,
    PC_REDEEM_PREFIX,
    PC_SCOPE_PREFIX,
    PC_SEARCH,
    PC_SKIP_DATES,
    PC_STATS,
    PC_TOGGLE_PREFIX,
    PC_TYPE_PREFIX,
    PC_UNLIMITED_USES,
    promo_cancel_keyboard,
    promo_confirm_keyboard,
    promo_dates_keyboard,
    promo_discount_type_keyboard,
    promo_home_keyboard,
    promo_item_keyboard,
    promo_list_keyboard,
    promo_max_uses_keyboard,
    promo_plan_keyboard,
    promo_scope_keyboard,
)
from app.presentation.states.admin_promo import AdminPromoCreateStates, AdminPromoSearchStates
from app.presentation.utils.telegram import safe_edit_message_text

router = Router(name="admin_promo_codes")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.message(F.text == "🎁 Промокоды")
async def handle_promo_menu(message: Message) -> None:
    await message.answer(
        "🎁 Промокоды\n\nСоздавайте скидки для покупки и продления VPN.",
        reply_markup=promo_home_keyboard(),
    )


@router.callback_query(F.data == PC_BACK_ADMIN)
async def handle_promo_back_admin(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.answer("Админ-панель", reply_markup=admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == PC_CANCEL)
async def handle_promo_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.answer("🎁 Промокоды", reply_markup=promo_home_keyboard())
    await callback.answer("Отменено.")


@router.callback_query(F.data == PC_HOME)
async def handle_promo_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await safe_edit_message_text(
            callback.message,
            "🎁 Промокоды\n\nСоздавайте скидки для покупки и продления VPN.",
            reply_markup=promo_home_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == PC_STATS)
async def handle_promo_stats(callback: CallbackQuery, promo_code_service: PromoCodeService) -> None:
    text = await promo_code_service.get_stats_text()
    if callback.message is not None:
        await safe_edit_message_text(callback.message, text, reply_markup=promo_home_keyboard())
    await callback.answer()


@router.callback_query(F.data == PC_LIST)
async def handle_promo_list(callback: CallbackQuery, promo_code_service: PromoCodeService) -> None:
    items = await promo_code_service.list_promos()
    text = promo_code_service.format_list(items)
    if callback.message is not None:
        await safe_edit_message_text(
            callback.message,
            text,
            reply_markup=promo_list_keyboard(items),
        )
    await callback.answer()


@router.callback_query(F.data.startswith(PC_ITEM_PREFIX))
async def handle_promo_item(
    callback: CallbackQuery,
    promo_code_service: PromoCodeService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    promo_id = _parse_id(callback.data, PC_ITEM_PREFIX)
    if promo_id is None:
        await callback.answer("Некорректный промокод.", show_alert=True)
        return
    items = await promo_code_service.list_promos(limit=200)
    item = next((x for x in items if x.id == promo_id), None)
    if item is None:
        await callback.answer("Промокод не найден.", show_alert=True)
        return
    status = "активен" if item.is_active else "отключён"
    max_uses = str(item.max_uses) if item.max_uses is not None else "∞"
    expiry = item.expires_at.strftime("%d.%m.%Y") if item.expires_at else "—"
    value = promo_code_service._format_value(item.discount_type, item.value)  # noqa: SLF001
    text = _format_promo_item_details(item, status=status, value=value, max_uses=max_uses, expiry=expiry)
    await safe_edit_message_text(
        callback.message,
        text,
        reply_markup=promo_item_keyboard(item.id, is_active=item.is_active),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(PC_TOGGLE_PREFIX))
async def handle_promo_toggle(
    callback: CallbackQuery,
    promo_code_service: PromoCodeService,
) -> None:
    if callback.data is None or callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    promo_id = _parse_id(callback.data, PC_TOGGLE_PREFIX)
    if promo_id is None:
        await callback.answer("Некорректный промокод.", show_alert=True)
        return
    items = await promo_code_service.list_promos(limit=200)
    item = next((x for x in items if x.id == promo_id), None)
    if item is None:
        await callback.answer("Промокод не найден.", show_alert=True)
        return
    try:
        await promo_code_service.set_active(
            promo_id,
            is_active=not item.is_active,
            admin_telegram_id=callback.from_user.id,
        )
    except PromoCodeError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    status = "активен" if updated.is_active else "отключён"
    await callback.answer(f"Промокод {status}.")
    items = await promo_code_service.list_promos(limit=200)
    refreshed = next((x for x in items if x.id == promo_id), None)
    if refreshed is None:
        return
    max_uses = str(refreshed.max_uses) if refreshed.max_uses is not None else "∞"
    expiry = refreshed.expires_at.strftime("%d.%m.%Y") if refreshed.expires_at else "—"
    value = promo_code_service._format_value(refreshed.discount_type, refreshed.value)  # noqa: SLF001
    text = _format_promo_item_details(
        refreshed,
        status=status,
        value=value,
        max_uses=max_uses,
        expiry=expiry,
    )
    await safe_edit_message_text(
        callback.message,
        text,
        reply_markup=promo_item_keyboard(refreshed.id, is_active=refreshed.is_active),
    )


@router.callback_query(F.data.startswith(PC_REDEEM_PREFIX))
async def handle_promo_redemptions(
    callback: CallbackQuery,
    promo_code_service: PromoCodeService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    promo_id = _parse_id(callback.data, PC_REDEEM_PREFIX)
    if promo_id is None:
        await callback.answer("Некорректный промокод.", show_alert=True)
        return
    try:
        text = await promo_code_service.get_redemptions_text(promo_id)
    except PromoCodeError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    items = await promo_code_service.list_promos(limit=200)
    item = next((x for x in items if x.id == promo_id), None)
    is_active = item.is_active if item is not None else True
    await safe_edit_message_text(
        callback.message,
        text,
        reply_markup=promo_item_keyboard(promo_id, is_active=is_active),
    )
    await callback.answer()


@router.callback_query(F.data == PC_SEARCH)
async def handle_promo_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminPromoSearchStates.waiting_query)
    if callback.message is not None:
        await callback.message.answer(
            "🔎 Введите код или часть кода для поиска:\n/cancel для отмены",
            reply_markup=promo_cancel_keyboard(),
        )
    await callback.answer()


@router.message(StateFilter(AdminPromoSearchStates.waiting_query), F.text, ~F.text.startswith("/"))
async def handle_promo_search_query(
    message: Message,
    state: FSMContext,
    promo_code_service: PromoCodeService,
) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("Введите непустой запрос.")
        return
    items = await promo_code_service.search_promos(query)
    await state.clear()
    text = promo_code_service.format_list(items)
    await message.answer(text, reply_markup=promo_list_keyboard(items))


@router.callback_query(F.data == PC_CREATE)
async def handle_promo_create_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminPromoCreateStates.waiting_code)
    if callback.message is not None:
        await callback.message.answer(
            "➕ Создание промокода\n\n"
            "Введите код (латиница/цифры, будет сохранён в ВЕРХНЕМ регистре):\n"
            "/cancel для отмены",
            reply_markup=promo_cancel_keyboard(),
        )
    await callback.answer()


@router.message(StateFilter(AdminPromoCreateStates.waiting_code), F.text, ~F.text.startswith("/"))
async def create_step_code(message: Message, state: FSMContext, promo_code_service: PromoCodeService) -> None:
    code = promo_code_service.normalize_code(message.text or "")
    if len(code) < 3:
        await message.answer("Код слишком короткий (мин. 3 символа).")
        return
    if len(code) > 32:
        await message.answer("Код слишком длинный (макс. 32 символа).")
        return
    await state.update_data(code=code)
    await state.set_state(AdminPromoCreateStates.waiting_discount_type)
    await message.answer(
        "Выберите тип скидки:",
        reply_markup=promo_discount_type_keyboard(),
    )


@router.callback_query(
    StateFilter(AdminPromoCreateStates.waiting_discount_type),
    F.data.startswith(PC_TYPE_PREFIX),
)
async def create_step_discount_type(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    discount_type = callback.data.removeprefix(PC_TYPE_PREFIX)
    if discount_type not in {t.value for t in PromoDiscountType}:
        await callback.answer("Некорректный тип.", show_alert=True)
        return
    await state.update_data(discount_type=discount_type)
    await state.set_state(AdminPromoCreateStates.waiting_value)
    prompts = {
        PromoDiscountType.PERCENT.value: "Введите процент скидки (1–100):",
        PromoDiscountType.FIXED_AMOUNT.value: "Введите сумму скидки в рублях:",
        PromoDiscountType.EXTRA_DAYS.value: "Введите количество дополнительных дней:",
    }
    await callback.message.answer(
        prompts.get(discount_type, "Введите значение:"),
        reply_markup=promo_cancel_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(AdminPromoCreateStates.waiting_value), F.text, ~F.text.startswith("/"))
async def create_step_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    discount_type = data.get("discount_type", "")
    raw = (message.text or "").strip().replace(",", ".")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        await message.answer("Введите корректное число.")
        return
    if discount_type == PromoDiscountType.PERCENT.value:
        if value <= 0 or value > 100:
            await message.answer("Процент должен быть от 1 до 100.")
            return
    elif discount_type == PromoDiscountType.EXTRA_DAYS.value:
        if value <= 0 or value != int(value):
            await message.answer("Введите целое число дней больше 0.")
            return
    else:
        if value <= 0:
            await message.answer("Сумма должна быть больше 0.")
            return
    await state.update_data(value=str(value))
    await state.set_state(AdminPromoCreateStates.waiting_dates)
    await message.answer(
        "Введите период действия ДД.ММ.ГГГГ-ДД.ММ.ГГГГ\n"
        "или нажмите «Без ограничений»:",
        reply_markup=promo_dates_keyboard(),
    )


@router.callback_query(StateFilter(AdminPromoCreateStates.waiting_dates), F.data == PC_SKIP_DATES)
async def create_step_skip_dates(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await state.update_data(starts_at=None, expires_at=None)
    await state.set_state(AdminPromoCreateStates.waiting_max_uses)
    await callback.message.answer(
        "Введите максимальное число использований (целое > 0)\n"
        "или нажмите «Безлимит»:",
        reply_markup=promo_max_uses_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(AdminPromoCreateStates.waiting_dates), F.text, ~F.text.startswith("/"))
async def create_step_dates(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if raw in {"-", "—", "пропустить"}:
        await state.update_data(starts_at=None, expires_at=None)
    else:
        try:
            starts_at, expires_at = _parse_date_range(raw)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.update_data(starts_at=starts_at.isoformat(), expires_at=expires_at.isoformat())
    await state.set_state(AdminPromoCreateStates.waiting_max_uses)
    await message.answer(
        "Введите максимальное число использований (целое > 0)\n"
        "или нажмите «Безлимит»:",
        reply_markup=promo_max_uses_keyboard(),
    )


@router.callback_query(StateFilter(AdminPromoCreateStates.waiting_max_uses), F.data == PC_UNLIMITED_USES)
async def create_step_unlimited_uses(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await state.update_data(max_uses=None)
    await state.set_state(AdminPromoCreateStates.waiting_max_per_user)
    await callback.message.answer(
        "Введите лимит использований на одного пользователя (по умолчанию 1):",
        reply_markup=promo_cancel_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(AdminPromoCreateStates.waiting_max_uses), F.text, ~F.text.startswith("/"))
async def create_step_max_uses(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    try:
        max_uses = int(raw)
    except ValueError:
        await message.answer("Введите целое число или нажмите «Безлимит».")
        return
    if max_uses <= 0:
        await message.answer("Число должно быть больше 0.")
        return
    await state.update_data(max_uses=max_uses)
    await state.set_state(AdminPromoCreateStates.waiting_max_per_user)
    await message.answer(
        "Введите лимит использований на одного пользователя (по умолчанию 1):",
        reply_markup=promo_cancel_keyboard(),
    )


@router.message(StateFilter(AdminPromoCreateStates.waiting_max_per_user), F.text, ~F.text.startswith("/"))
async def create_step_max_per_user(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw:
        max_per_user = 1
    else:
        try:
            max_per_user = int(raw)
        except ValueError:
            await message.answer("Введите целое число.")
            return
        if max_per_user <= 0:
            await message.answer("Число должно быть больше 0.")
            return
    await state.update_data(max_uses_per_user=max_per_user)
    await state.set_state(AdminPromoCreateStates.waiting_scope)
    await message.answer("Выберите область применения:", reply_markup=promo_scope_keyboard())


@router.callback_query(
    StateFilter(AdminPromoCreateStates.waiting_scope),
    F.data.startswith(PC_SCOPE_PREFIX),
)
async def create_step_scope(
    callback: CallbackQuery,
    state: FSMContext,
    plan_service: PlanService,
    promo_code_service: PromoCodeService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    scope = callback.data.removeprefix(PC_SCOPE_PREFIX)
    if scope == "plan":
        plans = await plan_service.list_active_plans()
        if not plans:
            await callback.answer("Нет активных тарифов.", show_alert=True)
            return
        await state.update_data(applies_to_request_type=PromoRequestScope.ANY.value)
        await state.set_state(AdminPromoCreateStates.waiting_plan)
        plan_rows = [(p.id, p.name) for p in plans]
        await callback.message.answer(
            "Выберите тариф:",
            reply_markup=promo_plan_keyboard(plan_rows),
        )
        await callback.answer()
        return
    if scope not in {s.value for s in PromoRequestScope}:
        await callback.answer("Некорректная область.", show_alert=True)
        return
    await state.update_data(
        applies_to_request_type=scope,
        applies_to_plan_id=None,
    )
    await _show_create_preview(callback.message, state, promo_code_service)
    await callback.answer()


@router.callback_query(
    StateFilter(AdminPromoCreateStates.waiting_plan),
    F.data.startswith(PC_PLAN_PREFIX),
)
async def create_step_plan(
    callback: CallbackQuery,
    state: FSMContext,
    promo_code_service: PromoCodeService,
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    plan_id = _parse_id(callback.data, PC_PLAN_PREFIX)
    if plan_id is None:
        await callback.answer("Некорректный тариф.", show_alert=True)
        return
    plan = await plan_service.get_active_plan(plan_id)
    if plan is None:
        await callback.answer("Тариф недоступен.", show_alert=True)
        return
    await state.update_data(applies_to_plan_id=plan_id)
    await _show_create_preview(callback.message, state, promo_code_service)
    await callback.answer()


@router.callback_query(StateFilter(AdminPromoCreateStates.confirm), F.data == PC_CONFIRM)
async def create_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    promo_code_service: PromoCodeService,
) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return
    draft = await _draft_from_state(await state.get_data())
    try:
        promo = await promo_code_service.create_promo(
            draft,
            admin_telegram_id=callback.from_user.id,
        )
    except PromoCodeError as exc:
        await callback.answer(exc.message, show_alert=True)
        return
    await state.clear()
    await callback.message.answer(
        f"✅ Промокод {promo.code} создан.",
        reply_markup=promo_home_keyboard(),
    )
    await callback.answer("Создано.")


async def _show_create_preview(
    message: Message,
    state: FSMContext,
    promo_code_service: PromoCodeService,
) -> None:
    draft = await _draft_from_state(await state.get_data())
    text = promo_code_service.format_preview(draft)
    await state.set_state(AdminPromoCreateStates.confirm)
    await message.answer(text, reply_markup=promo_confirm_keyboard())


async def _draft_from_state(data: dict) -> PromoCodeDraft:
    starts_raw = data.get("starts_at")
    expires_raw = data.get("expires_at")
    starts_at = datetime.fromisoformat(starts_raw) if isinstance(starts_raw, str) else None
    expires_at = datetime.fromisoformat(expires_raw) if isinstance(expires_raw, str) else None
    return PromoCodeDraft(
        code=str(data["code"]),
        discount_type=str(data["discount_type"]),
        value=Decimal(str(data["value"])),
        starts_at=starts_at,
        expires_at=expires_at,
        max_uses=data.get("max_uses"),
        max_uses_per_user=int(data.get("max_uses_per_user") or 1),
        min_amount=None,
        applies_to_plan_id=data.get("applies_to_plan_id"),
        applies_to_request_type=data.get("applies_to_request_type"),
        new_users_only=False,
    )


def _format_promo_item_details(
    item,
    *,
    status: str,
    value: str,
    max_uses: str,
    expiry: str,
) -> str:
    return (
        f"🎁 Промокод {item.code}\n\n"
        f"Статус: {status}\n"
        f"Тип: {value}\n"
        f"Использований: {item.used_count}/{max_uses}\n"
        f"Действует до: {expiry}\n"
        f"На пользователя: {item.max_uses_per_user}"
    )


def _parse_id(data: str, prefix: str) -> int | None:
    try:
        return int(data.removeprefix(prefix))
    except ValueError:
        return None


def _parse_date_range(raw: str) -> tuple[datetime, datetime]:
    parts = raw.split("-", maxsplit=1)
    if len(parts) != 2:
        raise ValueError("Формат: ДД.ММ.ГГГГ-ДД.ММ.ГГГГ")
    start = _parse_date(parts[0].strip())
    end = _parse_date(parts[1].strip())
    if end < start:
        raise ValueError("Дата окончания не может быть раньше начала.")
    return start, end


def _parse_date(raw: str) -> datetime:
    try:
        return datetime.strptime(raw, "%d.%m.%Y").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError("Некорректная дата. Формат: ДД.ММ.ГГГГ") from exc

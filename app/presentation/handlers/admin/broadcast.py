from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.services.broadcast_sender_service import BroadcastSenderService
from app.application.services.broadcast_service import BroadcastDraft, BroadcastService
from app.domain.enums import BroadcastTargetType
from app.infrastructure.db.uow import UnitOfWork
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_broadcast import (
    BC_BACK_ADMIN,
    BC_CANCEL,
    BC_CONFIRM_SEND,
    BC_CREATE,
    BC_EDIT_PHOTO,
    BC_EDIT_TEXT,
    BC_HISTORY,
    BC_SKIP_PHOTO,
    BC_TARGET_PREFIX,
    broadcast_audience_keyboard,
    broadcast_home_keyboard,
    broadcast_preview_keyboard,
    broadcast_skip_photo_keyboard,
)
from app.presentation.states.admin_broadcast import AdminBroadcastStates
from app.presentation.utils.telegram import safe_edit_message_text

logger = logging.getLogger(__name__)

router = Router(name="admin_broadcast")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())


@router.message(F.text == "📣 Рассылки")
async def handle_broadcast_menu(message: Message) -> None:
    await message.answer(
        "📣 <b>Рассылки</b>\n\nСоздавайте промо- и новостные сообщения для пользователей бота.",
        reply_markup=broadcast_home_keyboard(),
    )


@router.callback_query(F.data == BC_BACK_ADMIN)
async def handle_broadcast_back_admin(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.answer("Админ-панель", reply_markup=admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == BC_CANCEL)
async def handle_broadcast_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message is not None:
        await callback.message.answer(
            "📣 <b>Рассылки</b>",
            reply_markup=broadcast_home_keyboard(),
        )
    await callback.answer("Отменено.")


@router.callback_query(F.data == BC_CREATE)
async def handle_broadcast_create_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminBroadcastStates.waiting_title)
    if callback.message is not None:
        await callback.message.answer(
            "📝 Введите внутреннее название рассылки (для истории):\n<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.message(StateFilter(AdminBroadcastStates.waiting_title), F.text, ~F.text.startswith("/"))
async def handle_broadcast_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    if len(title) > 128:
        await message.answer("Название слишком длинное (макс. 128 символов).")
        return
    await state.update_data(title=title)
    await state.set_state(AdminBroadcastStates.waiting_text)
    await message.answer(
        "✉️ Введите текст сообщения для пользователей:\n<i>/cancel для отмены</i>",
    )


@router.message(StateFilter(AdminBroadcastStates.waiting_text), F.text, ~F.text.startswith("/"))
async def handle_broadcast_text(
    message: Message,
    state: FSMContext,
    broadcast_service: BroadcastService,
) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не может быть пустым.")
        return
    await state.update_data(text=text)
    data = await state.get_data()
    if data.get("target_type"):
        await _show_preview_message(message, state, broadcast_service)
        return
    await state.set_state(AdminBroadcastStates.waiting_photo)
    await message.answer(
        "🖼 Отправьте фото для рассылки (будет подпись) или нажмите «Без фото»:",
        reply_markup=broadcast_skip_photo_keyboard(),
    )


@router.callback_query(StateFilter(AdminBroadcastStates.waiting_photo), F.data == BC_SKIP_PHOTO)
async def handle_broadcast_skip_photo(
    callback: CallbackQuery,
    state: FSMContext,
    broadcast_service: BroadcastService,
) -> None:
    await state.update_data(photo_file_id=None)
    data = await state.get_data()
    if data.get("target_type"):
        await _show_preview(callback, state, broadcast_service)
        return
    await _prompt_audience(callback, state)


@router.message(StateFilter(AdminBroadcastStates.waiting_photo), F.photo)
async def handle_broadcast_photo(
    message: Message,
    state: FSMContext,
    broadcast_service: BroadcastService,
) -> None:
    if not message.photo:
        return
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id)
    data = await state.get_data()
    if data.get("target_type"):
        await _show_preview_message(message, state, broadcast_service)
        return
    await state.set_state(AdminBroadcastStates.waiting_audience)
    await message.answer(
        "👥 Выберите аудиторию рассылки:",
        reply_markup=broadcast_audience_keyboard(),
    )


@router.callback_query(F.data.startswith(BC_TARGET_PREFIX))
async def handle_broadcast_audience(
    callback: CallbackQuery,
    state: FSMContext,
    broadcast_service: BroadcastService,
) -> None:
    if callback.data is None:
        await callback.answer()
        return
    target_type = callback.data.removeprefix(BC_TARGET_PREFIX)
    if target_type not in {item.value for item in BroadcastTargetType}:
        await callback.answer("Некорректная аудитория.", show_alert=True)
        return
    await state.update_data(target_type=target_type)
    await _show_preview(callback, state, broadcast_service)


@router.callback_query(F.data == BC_EDIT_TEXT)
async def handle_broadcast_edit_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastStates.waiting_text)
    if callback.message is not None:
        await callback.message.answer(
            "✏️ Введите новый текст сообщения:\n<i>/cancel для отмены</i>",
        )
    await callback.answer()


@router.callback_query(F.data == BC_EDIT_PHOTO)
async def handle_broadcast_edit_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastStates.waiting_photo)
    if callback.message is not None:
        await callback.message.answer(
            "🖼 Отправьте новое фото или нажмите «Без фото»:",
            reply_markup=broadcast_skip_photo_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == BC_CONFIRM_SEND)
async def handle_broadcast_confirm_send(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    uow: UnitOfWork,
    broadcast_service: BroadcastService,
    broadcast_sender_service: BroadcastSenderService,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return
    draft = await _load_draft(state, broadcast_service)
    if draft is None:
        await callback.answer("Данные рассылки утеряны. Начните заново.", show_alert=True)
        await state.clear()
        return
    if draft.recipient_count == 0:
        await callback.answer("Нет получателей для выбранной аудитории.", show_alert=True)
        return

    broadcast = await broadcast_service.create_and_queue(
        draft,
        admin_telegram_id=callback.from_user.id,
    )
    await uow.commit()
    await state.clear()

    asyncio.create_task(
        broadcast_sender_service.send_broadcast(
            bot,
            broadcast.id,
            admin_telegram_id=callback.from_user.id,
        )
    )

    if callback.message is not None:
        await callback.message.answer(
            f"🚀 Рассылка «{broadcast_service.escape_text(draft.title)}» запущена.\n"
            f"Получателей: <b>{draft.recipient_count}</b>\n"
            "Статус можно посмотреть в истории.",
            reply_markup=broadcast_home_keyboard(),
        )
    await callback.answer("Рассылка запущена.")


@router.callback_query(F.data == BC_HISTORY)
async def handle_broadcast_history(
    callback: CallbackQuery,
    broadcast_service: BroadcastService,
) -> None:
    items = await broadcast_service.list_history()
    text = broadcast_service.format_history(items)
    if callback.message is not None:
        await safe_edit_message_text(
            callback.message,
            text,
            reply_markup=broadcast_home_keyboard(),
        )
    await callback.answer()


async def _prompt_audience(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminBroadcastStates.waiting_audience)
    if callback.message is not None:
        await callback.message.answer(
            "👥 Выберите аудиторию рассылки:",
            reply_markup=broadcast_audience_keyboard(),
        )
    await callback.answer()


async def _show_preview(
    callback: CallbackQuery,
    state: FSMContext,
    broadcast_service: BroadcastService,
) -> None:
    draft = await _load_draft(state, broadcast_service)
    if draft is None:
        await callback.answer("Заполните все поля рассылки.", show_alert=True)
        return
    if callback.message is not None:
        await _send_preview_message(callback.message, draft, broadcast_service)
    await callback.answer()


async def _show_preview_message(
    message: Message,
    state: FSMContext,
    broadcast_service: BroadcastService,
) -> None:
    draft = await _load_draft(state, broadcast_service)
    if draft is None:
        await message.answer("Заполните все поля рассылки.")
        return
    await _send_preview_message(message, draft, broadcast_service)


async def _send_preview_message(
    message: Message,
    draft: BroadcastDraft,
    broadcast_service: BroadcastService,
) -> None:
    text = broadcast_service.format_preview(draft)
    if draft.photo_file_id:
        await message.answer_photo(
            draft.photo_file_id,
            caption=text,
            reply_markup=broadcast_preview_keyboard(),
        )
    else:
        await message.answer(text, reply_markup=broadcast_preview_keyboard())


async def _load_draft(
    state: FSMContext,
    broadcast_service: BroadcastService,
) -> BroadcastDraft | None:
    data = await state.get_data()
    title = data.get("title")
    text = data.get("text")
    target_type = data.get("target_type")
    if not isinstance(title, str) or not isinstance(text, str) or not isinstance(target_type, str):
        return None
    photo_file_id = data.get("photo_file_id")
    if photo_file_id is not None and not isinstance(photo_file_id, str):
        photo_file_id = None
    return await broadcast_service.build_draft(
        title=title,
        text=text,
        photo_file_id=photo_file_id,
        target_type=target_type,
    )

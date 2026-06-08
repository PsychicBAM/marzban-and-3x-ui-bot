from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import StatisticsLoadError
from app.application.services.statistics_service import StatisticsService
from app.presentation.filters.admin import IsAdminCallbackFilter, IsAdminFilter
from app.presentation.keyboards.admin import admin_main_keyboard
from app.presentation.keyboards.admin_statistics import (
    STAT_BACK,
    STAT_MONTH,
    STAT_REFRESH,
    STAT_TODAY,
    statistics_keyboard,
)

logger = logging.getLogger(__name__)

router = Router(name="admin_statistics")
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminCallbackFilter())

ERROR_TEXT = "❌ Не удалось загрузить статистику. Попробуйте позже."


@router.message(F.text == "📊 Статистика")
async def handle_statistics_menu(
    message: Message,
    statistics_service: StatisticsService,
) -> None:
    await _send_overview(message, statistics_service)


@router.callback_query(F.data == STAT_REFRESH)
async def handle_statistics_refresh(
    callback: CallbackQuery,
    statistics_service: StatisticsService,
) -> None:
    await _edit_or_answer_overview(callback, statistics_service)


@router.callback_query(F.data == STAT_TODAY)
async def handle_statistics_today(
    callback: CallbackQuery,
    statistics_service: StatisticsService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    try:
        snapshot, total, by_plan, count = await statistics_service.build_today_payment_summary()
        text = statistics_service.format_today_summary(
            snapshot,
            period_total=total,
            by_plan=by_plan,
            approved_count=count,
        )
        await callback.message.edit_text(text, reply_markup=statistics_keyboard())
    except StatisticsLoadError:
        await callback.message.answer(ERROR_TEXT, reply_markup=statistics_keyboard())
    except Exception as exc:
        logger.exception("Statistics today view failed", extra={"error": str(exc)[:300]})
        await callback.message.answer(ERROR_TEXT, reply_markup=statistics_keyboard())
    await callback.answer()


@router.callback_query(F.data == STAT_MONTH)
async def handle_statistics_month(
    callback: CallbackQuery,
    statistics_service: StatisticsService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    try:
        snapshot, total, by_plan, count = await statistics_service.build_month_payment_summary()
        text = statistics_service.format_month_summary(
            snapshot,
            period_total=total,
            by_plan=by_plan,
            approved_count=count,
        )
        await callback.message.edit_text(text, reply_markup=statistics_keyboard())
    except StatisticsLoadError:
        await callback.message.answer(ERROR_TEXT, reply_markup=statistics_keyboard())
    except Exception as exc:
        logger.exception("Statistics month view failed", extra={"error": str(exc)[:300]})
        await callback.message.answer(ERROR_TEXT, reply_markup=statistics_keyboard())
    await callback.answer()


@router.callback_query(F.data == STAT_BACK)
async def handle_statistics_back(callback: CallbackQuery) -> None:
    if callback.message is None:
        await callback.answer()
        return
    await callback.message.answer("Админ-панель", reply_markup=admin_main_keyboard())
    await callback.answer()


async def _send_overview(message: Message, statistics_service: StatisticsService) -> None:
    try:
        snapshot = await statistics_service.build_snapshot()
        text = statistics_service.format_overview(snapshot)
        await message.answer(text, reply_markup=statistics_keyboard())
    except StatisticsLoadError:
        await message.answer(ERROR_TEXT, reply_markup=statistics_keyboard())
    except Exception as exc:
        logger.exception("Statistics overview failed", extra={"error": str(exc)[:300]})
        await message.answer(ERROR_TEXT, reply_markup=statistics_keyboard())


async def _edit_or_answer_overview(
    callback: CallbackQuery,
    statistics_service: StatisticsService,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    try:
        snapshot = await statistics_service.build_snapshot()
        text = statistics_service.format_overview(snapshot)
        await callback.message.edit_text(text, reply_markup=statistics_keyboard())
    except StatisticsLoadError:
        await callback.message.answer(ERROR_TEXT, reply_markup=statistics_keyboard())
    except Exception as exc:
        logger.exception("Statistics refresh failed", extra={"error": str(exc)[:300]})
        await callback.message.answer(ERROR_TEXT, reply_markup=statistics_keyboard())
    await callback.answer()

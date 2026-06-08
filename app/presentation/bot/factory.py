from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config.settings import Settings, get_settings
from app.presentation.bot.middlewares.database import DatabaseMiddleware
from app.presentation.handlers import build_root_router
from app.presentation.handlers.global_cancel import router as global_cancel_router


def create_bot(settings: Settings | None = None) -> Bot:
    cfg = settings or get_settings()
    return Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings | None = None) -> Dispatcher:
    cfg = settings or get_settings()
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher["settings"] = cfg
    dispatcher.update.middleware(DatabaseMiddleware())
    dispatcher.include_router(global_cancel_router)
    dispatcher.include_router(build_root_router())
    return dispatcher

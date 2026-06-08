from __future__ import annotations

import logging

from app.application.services.plan_service import PlanService
from app.config.settings import Settings
from app.infrastructure.db.session import session_scope
from app.infrastructure.db.uow import UnitOfWork

logger = logging.getLogger(__name__)


async def bootstrap_database(settings: Settings) -> None:
    async with session_scope() as session:
        uow = UnitOfWork(session)
        plan_service = PlanService(uow, settings)
        seeded = await plan_service.seed_defaults_if_empty()
        if seeded:
            logger.info("Bootstrap completed: demo plans seeded", extra={"count": seeded})
        else:
            logger.info("Bootstrap completed: plans already exist")

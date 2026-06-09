from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from app.application.dto.plan import PlanCreateInput, PlanInfo
from app.application.exceptions import PlanValidationError
from app.config.settings import Settings
from app.domain.enums import IssuingMode
from app.infrastructure.db.models.plan import Plan
from app.infrastructure.db.uow import UnitOfWork
from app.infrastructure.seed.default_plans import DEFAULT_DEMO_PLANS

logger = logging.getLogger(__name__)

ISSUING_MODE_LABELS: dict[str, str] = {
    IssuingMode.MARZBAN.value: "Marzban",
    IssuingMode.XUI.value: "3x-ui",
    IssuingMode.BOTH.value: "Marzban + 3x-ui",
}

EDITABLE_FIELDS: tuple[str, ...] = (
    "name",
    "price",
    "duration_days",
    "traffic_limit_gb",
    "ip_limit",
    "issuing_mode",
    "description",
)

FIELD_LABELS: dict[str, str] = {
    "name": "Название",
    "price": "Цена",
    "duration_days": "Срок (дни)",
    "traffic_limit_gb": "Трафик (ГБ)",
    "ip_limit": "Лимит устройств",
    "issuing_mode": "Режим выдачи",
    "description": "Описание",
}


class PlanService:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    async def seed_defaults_if_empty(self) -> int:
        count = await self._uow.plans.count_all()
        if count > 0:
            return 0

        created = 0
        for seed in DEFAULT_DEMO_PLANS:
            issuing_mode = seed.issuing_mode or self._settings.default_issuing_mode
            await self._uow.plans.create(
                name=seed.name,
                price=seed.price,
                duration_days=seed.duration_days,
                traffic_limit_gb=seed.traffic_limit_gb,
                ip_limit=seed.ip_limit,
                issuing_mode=issuing_mode,
                description=seed.description,
            )
            created += 1

        logger.info("Seeded default demo plans", extra={"count": created})
        return created

    async def list_all_plans(self) -> list[PlanInfo]:
        plans = await self._uow.plans.list_all()
        return [self._to_info(plan) for plan in plans]

    async def list_active_plans(self) -> list[PlanInfo]:
        plans = await self._uow.plans.list_active()
        return [self._to_info(plan) for plan in plans]

    async def get_plan(self, plan_id: int) -> PlanInfo | None:
        plan = await self._uow.plans.get_by_id(plan_id)
        if plan is None:
            return None
        return self._to_info(plan)

    async def get_active_plan(self, plan_id: int) -> PlanInfo | None:
        plan = await self._uow.plans.get_by_id(plan_id)
        if plan is None or not plan.is_active:
            return None
        return self._to_info(plan)

    async def create_plan(self, data: PlanCreateInput) -> PlanInfo:
        self.validate_create_input(data)
        plan = await self._uow.plans.create(
            name=data.name.strip(),
            price=data.price,
            duration_days=data.duration_days,
            traffic_limit_gb=data.traffic_limit_gb,
            ip_limit=data.ip_limit,
            issuing_mode=data.issuing_mode,
            description=data.description,
        )
        logger.info("Plan created", extra={"plan_id": plan.id, "plan_name": plan.name})
        return self._to_info(plan)

    async def update_plan_field(
        self,
        plan_id: int,
        field: str,
        raw_value: str,
    ) -> tuple[PlanInfo, object, object]:
        if field not in EDITABLE_FIELDS:
            raise PlanValidationError("Недопустимое поле для редактирования.")

        plan = await self._uow.plans.get_by_id(plan_id)
        if plan is None:
            raise PlanValidationError("Тариф не найден.")

        old_value = getattr(plan, field)
        new_value = self.parse_field_value(field, raw_value)
        await self._uow.plans.update_fields(plan, **{field: new_value})
        logger.info(
            "Plan field updated",
            extra={"plan_id": plan_id, "field": field},
        )
        return self._to_info(plan), old_value, new_value

    async def set_plan_issuing_mode(self, plan_id: int, issuing_mode: str) -> tuple[PlanInfo, str, str]:
        return await self.update_plan_field(plan_id, "issuing_mode", issuing_mode)

    async def set_plan_active(self, plan_id: int, *, is_active: bool) -> PlanInfo:
        plan = await self._uow.plans.get_by_id(plan_id)
        if plan is None:
            raise PlanValidationError("Тариф не найден.")
        await self._uow.plans.update_fields(plan, is_active=is_active)
        logger.info(
            "Plan active status changed",
            extra={"plan_id": plan_id, "is_active": is_active},
        )
        return self._to_info(plan)

    def validate_create_input(self, data: PlanCreateInput) -> None:
        self.parse_name(data.name)
        self.parse_price(str(data.price))
        self.parse_duration_days(str(data.duration_days))
        self.parse_traffic_limit_gb(str(data.traffic_limit_gb))
        self.parse_ip_limit(str(data.ip_limit))
        self.parse_issuing_mode(data.issuing_mode)
        self.parse_description(data.description or "")

    def parse_field_value(self, field: str, raw_value: str) -> object:
        parsers = {
            "name": self.parse_name,
            "price": self.parse_price,
            "duration_days": self.parse_duration_days,
            "traffic_limit_gb": self.parse_traffic_limit_gb,
            "ip_limit": self.parse_ip_limit,
            "issuing_mode": self.parse_issuing_mode,
            "description": self.parse_description,
        }
        parser = parsers.get(field)
        if parser is None:
            raise PlanValidationError("Недопустимое поле.")
        return parser(raw_value)

    def parse_name(self, raw_value: str) -> str:
        value = raw_value.strip()
        if not value:
            raise PlanValidationError("Название не может быть пустым.")
        if len(value) > 128:
            raise PlanValidationError("Название слишком длинное (макс. 128 символов).")
        return value

    def parse_price(self, raw_value: str) -> Decimal:
        value = raw_value.strip().replace(",", ".")
        try:
            price = Decimal(value)
        except InvalidOperation as exc:
            raise PlanValidationError("Цена должна быть числом.") from exc
        if price < 0:
            raise PlanValidationError("Цена не может быть отрицательной.")
        return price

    def parse_duration_days(self, raw_value: str) -> int:
        value = raw_value.strip()
        try:
            days = int(value)
        except ValueError as exc:
            raise PlanValidationError("Срок должен быть целым числом дней.") from exc
        if days <= 0:
            raise PlanValidationError("Срок должен быть больше 0.")
        return days

    def parse_traffic_limit_gb(self, raw_value: str) -> int:
        value = raw_value.strip()
        try:
            gb = int(value)
        except ValueError as exc:
            raise PlanValidationError("Трафик должен быть целым числом ГБ.") from exc
        if gb < 0:
            raise PlanValidationError("Трафик не может быть отрицательным.")
        return gb

    def parse_ip_limit(self, raw_value: str) -> int:
        value = raw_value.strip()
        try:
            limit = int(value)
        except ValueError as exc:
            raise PlanValidationError("Лимит устройств должен быть целым числом.") from exc
        if limit < 0:
            raise PlanValidationError("Лимит устройств не может быть отрицательным.")
        return limit

    def parse_issuing_mode(self, raw_value: str) -> str:
        value = raw_value.strip().lower()
        allowed = {mode.value for mode in IssuingMode}
        if value not in allowed:
            raise PlanValidationError("Режим выдачи: marzban, xui или both.")
        return value

    def parse_description(self, raw_value: str) -> str | None:
        value = raw_value.strip()
        if not value or value == "-":
            return None
        return value

    def build_create_input_from_state(self, data: dict[str, object]) -> PlanCreateInput:
        return PlanCreateInput(
            name=str(data["name"]),
            price=Decimal(str(data["price"])),
            duration_days=int(data["duration_days"]),
            traffic_limit_gb=int(data["traffic_limit_gb"]),
            ip_limit=int(data["ip_limit"]),
            issuing_mode=str(data["issuing_mode"]),
            description=data.get("description"),  # type: ignore[arg-type]
        )

    @staticmethod
    def format_traffic_gb(gb: int) -> str:
        return "Безлимит" if gb <= 0 else f"{gb} ГБ"

    @staticmethod
    def format_ip_limit(limit: int) -> str:
        return "Безлимит" if limit <= 0 else str(limit)

    @staticmethod
    def format_status(is_active: bool) -> str:
        return "✅ Активен" if is_active else "🚫 Отключён"

    @staticmethod
    def format_price(price: Decimal) -> str:
        return "Бесплатно" if price == 0 else f"{price:.0f} ₽"

    @staticmethod
    def is_free(plan: PlanInfo) -> bool:
        return plan.price == 0

    def format_free_plan_checkout(self, *, plan_details: str) -> str:
        return "\n".join(
            [
                plan_details,
                "",
                "🎁 Этот тариф бесплатный. Нажмите кнопку ниже для мгновенной активации.",
            ],
        )

    def format_plan_details(self, plan: PlanInfo) -> str:
        traffic = self.format_traffic_gb(plan.traffic_limit_gb)
        devices = self.format_ip_limit(plan.ip_limit)
        issuing = ISSUING_MODE_LABELS.get(plan.issuing_mode, plan.issuing_mode)
        price = self.format_price(plan.price)

        lines = [
            f"<b>{plan.name}</b>",
            f"💰 Цена: {price}",
            f"📅 Срок: {plan.duration_days} дн.",
            f"📶 Трафик: {traffic}",
            f"📱 Устройств: {devices}",
            f"🖥 Панели: {issuing}",
        ]
        if plan.description:
            lines.append(f"\n{plan.description}")
        return "\n".join(lines)

    def format_admin_plan_full(self, plan: PlanInfo) -> str:
        traffic = self.format_traffic_gb(plan.traffic_limit_gb)
        devices = self.format_ip_limit(plan.ip_limit)
        issuing = ISSUING_MODE_LABELS.get(plan.issuing_mode, plan.issuing_mode)
        status = self.format_status(plan.is_active)
        price = f"{plan.price:.0f} ₽"

        lines = [
            f"<b>Тариф #{plan.id}</b>",
            f"📝 Название: {plan.name}",
            f"💰 Цена: {price}",
            f"📅 Срок: {plan.duration_days} дн.",
            f"📶 Трафик: {traffic}",
            f"📱 Устройств: {devices}",
            f"🖥 Режим выдачи: {issuing}",
            f"📌 Статус: {status}",
        ]
        if plan.description:
            lines.append(f"📄 Описание: {plan.description}")
        return "\n".join(lines)

    def format_admin_all_plans_list(self, plans: list[PlanInfo]) -> str:
        if not plans:
            return "💰 <b>Тарифы</b>\n\nТарифов пока нет."

        lines = ["💰 <b>Тарифы</b>", ""]
        for plan in plans:
            traffic = self.format_traffic_gb(plan.traffic_limit_gb).lower()
            devices = self.format_ip_limit(plan.ip_limit)
            if devices != "Безлимит":
                devices = f"{devices} устр."
            else:
                devices = "безлимит устр."
            issuing = ISSUING_MODE_LABELS.get(plan.issuing_mode, plan.issuing_mode)
            status = self.format_status(plan.is_active)
            lines.append(
                f"<b>#{plan.id} {plan.name}</b> — {status}\n"
                f"   💰 {plan.price:.0f} ₽ · 📅 {plan.duration_days} дн.\n"
                f"   📶 {traffic} · 📱 {devices}\n"
                f"   🖥 {issuing}"
            )
            if plan.description:
                lines.append(f"   📄 {plan.description}")
            lines.append("")
        return "\n".join(lines).strip()

    def format_create_confirmation(self, data: dict[str, object]) -> str:
        draft = self.build_create_input_from_state(data)
        info = PlanInfo(
            id=0,
            name=draft.name,
            price=draft.price,
            duration_days=draft.duration_days,
            traffic_limit_gb=draft.traffic_limit_gb,
            ip_limit=draft.ip_limit,
            issuing_mode=draft.issuing_mode,
            is_active=True,
            description=draft.description,
        )
        return (
            "<b>Подтверждение создания тарифа</b>\n\n"
            f"{self.format_admin_plan_full(info)}"
        )

    def format_field_value(self, field: str, value: object) -> str:
        if field == "price":
            return f"{Decimal(str(value)):.0f} ₽"
        if field == "traffic_limit_gb":
            return self.format_traffic_gb(int(value))
        if field == "ip_limit":
            return self.format_ip_limit(int(value))
        if field == "issuing_mode":
            return ISSUING_MODE_LABELS.get(str(value), str(value))
        if field == "description":
            return str(value) if value else "—"
        return str(value)

    def get_field_prompt(self, field: str) -> str:
        prompts = {
            "name": "Введите новое <b>название</b> тарифа:",
            "price": "Введите новую <b>цену</b> (₽, число ≥ 0):",
            "duration_days": "Введите новый <b>срок</b> в днях (целое число > 0):",
            "traffic_limit_gb": "Введите новый <b>лимит трафика</b> в ГБ (0 = безлимит):",
            "ip_limit": "Введите новый <b>лимит устройств</b> (0 = безлимит):",
            "description": "Введите новое <b>описание</b> (или «-» чтобы очистить):",
        }
        return prompts.get(field, "Введите новое значение:")

    @staticmethod
    def _to_info(plan: Plan) -> PlanInfo:
        return PlanInfo(
            id=plan.id,
            name=plan.name,
            price=plan.price,
            duration_days=plan.duration_days,
            traffic_limit_gb=plan.traffic_limit_gb,
            ip_limit=plan.ip_limit,
            issuing_mode=plan.issuing_mode,
            is_active=plan.is_active,
            description=plan.description,
        )

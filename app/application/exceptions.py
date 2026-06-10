from __future__ import annotations


class PlanValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class PaymentRequestError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class PaymentRequestDuplicateError(PaymentRequestError):
    pass


class PaymentRequestAlreadyProcessedError(PaymentRequestError):
    pass


class PaymentRequestNotFoundError(PaymentRequestError):
    pass


class FreePlanNotEligibleError(PaymentRequestError):
    pass


class PromoCodeError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ReferralError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class StatisticsLoadError(Exception):
    def __init__(self, message: str = "Не удалось загрузить статистику.") -> None:
        self.message = message
        super().__init__(message)


class VpnProvisioningError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class VpnPanelError(Exception):
    def __init__(self, message: str, *, panel: str | None = None) -> None:
        self.message = message
        self.panel = panel
        super().__init__(message)


class VpnPanelAuthError(VpnPanelError):
    pass


class VpnPanelNotFoundError(VpnPanelError):
    pass


class VpnPanelConflictError(VpnPanelError):
    pass


class VpnPanelValidationError(VpnPanelError):
    pass


__all__ = [
    "PaymentRequestAlreadyProcessedError",
    "FreePlanNotEligibleError",
    "PaymentRequestDuplicateError",
    "PaymentRequestError",
    "PaymentRequestNotFoundError",
    "PromoCodeError",
    "PlanValidationError",
    "StatisticsLoadError",
    "VpnPanelAuthError",
    "VpnPanelConflictError",
    "VpnPanelError",
    "VpnPanelNotFoundError",
    "VpnPanelValidationError",
    "VpnProvisioningError",
]

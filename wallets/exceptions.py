class WalletServiceError(Exception):
    
    status_code = 400
    error_code = "wallet_error"

    def __init__(self, detail):
        self.detail = detail
        super().__init__(detail)

    def to_dict(self):
        return {"error": self.error_code, "detail": self.detail}


class WalletNotFoundError(WalletServiceError):
    status_code = 404
    error_code = "wallet_not_found"


class InsufficientFundsError(WalletServiceError):
    status_code = 422
    error_code = "insufficient_funds"


class SameWalletTransferError(WalletServiceError):
    status_code = 400
    error_code = "same_wallet_transfer"


class IdempotencyKeyConflict(WalletServiceError):
    status_code = 409
    error_code = "idempotency_key_conflict"


class IdempotencyInProgress(WalletServiceError):
    status_code = 409
    error_code = "idempotency_key_in_progress"

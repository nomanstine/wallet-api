from django.db import transaction

from .exceptions import InsufficientFundsError, SameWalletTransferError, WalletNotFoundError
from .models import Transaction, Transfer, Wallet


def _get_wallet_locked(tenant, wallet_id):
    try:
        return Wallet.objects.select_for_update().get(id=wallet_id, tenant=tenant)
    except (Wallet.DoesNotExist, ValueError, TypeError):
        raise WalletNotFoundError(f"Wallet {wallet_id} not found for this tenant.")


@transaction.atomic
def deposit(tenant, wallet_id, amount, description=""):
    wallet = _get_wallet_locked(tenant, wallet_id)
    wallet.balance = wallet.balance + amount
    wallet.save(update_fields=["balance"])
    txn = Transaction.objects.create(
        tenant=tenant, wallet=wallet, type=Transaction.Type.DEPOSIT,
        amount=amount, balance_after=wallet.balance, description=description,
    )
    return wallet, txn


@transaction.atomic
def withdraw(tenant, wallet_id, amount, description=""):
    wallet = _get_wallet_locked(tenant, wallet_id)
    if wallet.balance < amount:
        raise InsufficientFundsError(
            f"Wallet balance {wallet.balance} is less than withdrawal amount {amount}."
        )
    wallet.balance = wallet.balance - amount
    wallet.save(update_fields=["balance"])
    txn = Transaction.objects.create(
        tenant=tenant, wallet=wallet, type=Transaction.Type.WITHDRAWAL,
        amount=amount, balance_after=wallet.balance, description=description,
    )
    return wallet, txn


@transaction.atomic
def transfer(tenant, from_wallet_id, to_wallet_id, amount, description=""):
    if str(from_wallet_id) == str(to_wallet_id):
        raise SameWalletTransferError("Cannot transfer a wallet to itself.")

    # Lock both wallets in a stable order to avoid deadlocks
    ordered_ids = sorted([str(from_wallet_id), str(to_wallet_id)])
    wallets = list(
        Wallet.objects.select_for_update().filter(tenant=tenant, id__in=ordered_ids).order_by("id")
    )
    wallets_by_id = {str(w.id): w for w in wallets}

    if str(from_wallet_id) not in wallets_by_id:
        raise WalletNotFoundError(f"Wallet {from_wallet_id} not found for this tenant.")
    if str(to_wallet_id) not in wallets_by_id:
        raise WalletNotFoundError(f"Wallet {to_wallet_id} not found for this tenant.")

    from_wallet = wallets_by_id[str(from_wallet_id)]
    to_wallet = wallets_by_id[str(to_wallet_id)]

    if from_wallet.balance < amount:
        raise InsufficientFundsError(
            f"Wallet balance {from_wallet.balance} is less than transfer amount {amount}."
        )

    from_wallet.balance -= amount
    to_wallet.balance += amount
    from_wallet.save(update_fields=["balance"])
    to_wallet.save(update_fields=["balance"])

    transfer_obj = Transfer.objects.create(
        tenant=tenant, from_wallet=from_wallet, to_wallet=to_wallet,
        amount=amount, description=description,
    )
    out_txn = Transaction.objects.create(
        tenant=tenant, wallet=from_wallet, type=Transaction.Type.TRANSFER_OUT,
        amount=amount, balance_after=from_wallet.balance, transfer=transfer_obj, description=description,
    )
    in_txn = Transaction.objects.create(
        tenant=tenant, wallet=to_wallet, type=Transaction.Type.TRANSFER_IN,
        amount=amount, balance_after=to_wallet.balance, transfer=transfer_obj, description=description,
    )
    return transfer_obj, out_txn, in_txn

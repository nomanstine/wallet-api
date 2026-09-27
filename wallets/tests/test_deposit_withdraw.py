from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from ..models import Transaction
from .helpers import client_for, create_tenant, create_user, create_wallet


class DepositWithdrawTests(APITestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.wallet = create_wallet(self.tenant, self.user, balance="10.00")
        self.client = client_for(self.tenant)

    def test_deposit_increases_balance_and_creates_ledger_entry(self):
        resp = self.client.post(
            f"/api/wallets/{self.wallet.id}/deposit/",
            {"amount": "5.00", "idempotency_key": "dep-1"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("15.00"))
        self.assertEqual(
            Transaction.objects.filter(wallet=self.wallet, type=Transaction.Type.DEPOSIT).count(), 1
        )

    def test_deposit_rejects_non_positive_amount(self):
        resp = self.client.post(
            f"/api/wallets/{self.wallet.id}/deposit/",
            {"amount": "0.00", "idempotency_key": "dep-2"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_withdraw_decreases_balance_and_creates_ledger_entry(self):
        resp = self.client.post(
            f"/api/wallets/{self.wallet.id}/withdraw/",
            {"amount": "4.00", "idempotency_key": "wd-1"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("6.00"))
        self.assertEqual(
            Transaction.objects.filter(wallet=self.wallet, type=Transaction.Type.WITHDRAWAL).count(), 1
        )

    def test_withdraw_insufficient_funds_is_rejected_and_nothing_changes(self):
        resp = self.client.post(
            f"/api/wallets/{self.wallet.id}/withdraw/",
            {"amount": "999.00", "idempotency_key": "wd-2"},
            format="json",
        )
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertEqual(resp.data["error"], "insufficient_funds")
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("10.00"))
        self.assertEqual(Transaction.objects.filter(wallet=self.wallet).count(), 0)

    def test_balance_endpoint_reflects_ledger(self):
        self.client.post(
            f"/api/wallets/{self.wallet.id}/deposit/",
            {"amount": "5.00", "idempotency_key": "dep-3"},
            format="json",
        )
        resp = self.client.get(f"/api/wallets/{self.wallet.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["balance"], "15.00")

    def test_transaction_history_is_paginated(self):
        for i in range(3):
            self.client.post(
                f"/api/wallets/{self.wallet.id}/deposit/",
                {"amount": "1.00", "idempotency_key": f"dep-hist-{i}"},
                format="json",
            )
        resp = self.client.get(f"/api/wallets/{self.wallet.id}/transactions/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data)
        self.assertEqual(resp.data["count"], 3)

from decimal import Decimal

from rest_framework.test import APITestCase

from .helpers import client_for, create_tenant, create_user, create_wallet


class TransferTests(APITestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.alice = create_user(self.tenant, "Alice")
        self.bob = create_user(self.tenant, "Bob")
        self.wallet_a = create_wallet(self.tenant, self.alice, balance="50.00")
        self.wallet_b = create_wallet(self.tenant, self.bob, balance="5.00")
        self.client = client_for(self.tenant)

    def _transfer(self, amount, key, from_id=None, to_id=None):
        return self.client.post(
            "/api/transfers/",
            {
                "from_wallet_id": str(from_id or self.wallet_a.id),
                "to_wallet_id": str(to_id or self.wallet_b.id),
                "amount": amount,
                "idempotency_key": key,
            },
            format="json",
        )

    def test_transfer_moves_funds_atomically(self):
        resp = self._transfer("20.00", "t-1")
        self.assertEqual(resp.status_code, 201, resp.data)
        self.wallet_a.refresh_from_db()
        self.wallet_b.refresh_from_db()
        self.assertEqual(self.wallet_a.balance, Decimal("30.00"))
        self.assertEqual(self.wallet_b.balance, Decimal("25.00"))

    def test_transfer_insufficient_funds_leaves_both_wallets_unchanged(self):
        resp = self._transfer("1000.00", "t-2")
        self.assertEqual(resp.status_code, 422, resp.data)
        self.wallet_a.refresh_from_db()
        self.wallet_b.refresh_from_db()
        self.assertEqual(self.wallet_a.balance, Decimal("50.00"))
        self.assertEqual(self.wallet_b.balance, Decimal("5.00"))

    def test_cannot_transfer_wallet_to_itself(self):
        resp = self._transfer("1.00", "t-3", from_id=self.wallet_a.id, to_id=self.wallet_a.id)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["error"], "same_wallet_transfer")

    def test_transfer_to_nonexistent_wallet_is_not_found(self):
        resp = self._transfer("1.00", "t-4", to_id="00000000-0000-0000-0000-000000000000")
        self.assertEqual(resp.status_code, 404)

from decimal import Decimal

from rest_framework.test import APITestCase

from .helpers import client_for, create_tenant, create_user, create_wallet


class IdempotencyTests(APITestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.wallet = create_wallet(self.tenant, self.user, balance="0.00")
        self.client = client_for(self.tenant)

    def test_retrying_same_key_does_not_double_credit(self):
        payload = {"amount": "10.00", "idempotency_key": "abc-123"}
        first = self.client.post(f"/api/wallets/{self.wallet.id}/deposit/", payload, format="json")
        second = self.client.post(f"/api/wallets/{self.wallet.id}/deposit/", payload, format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.data["transaction"]["id"], second.data["transaction"]["id"])
        self.assertEqual(first["Idempotent-Replayed"], "false")
        self.assertEqual(second["Idempotent-Replayed"], "true")

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("10.00"))

    def test_same_key_different_amount_is_a_conflict(self):
        self.client.post(
            f"/api/wallets/{self.wallet.id}/deposit/",
            {"amount": "10.00", "idempotency_key": "k1"}, format="json",
        )
        resp = self.client.post(
            f"/api/wallets/{self.wallet.id}/deposit/",
            {"amount": "20.00", "idempotency_key": "k1"}, format="json",
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data["error"], "idempotency_key_conflict")

    def test_failed_operation_is_also_cached_under_the_key(self):
        # withdraw more than the balance -> 422, then deposit enough to cover
        # it and retry with the SAME key: must still replay the original
        # failure, not re-evaluate against the now-sufficient balance.
        first = self.client.post(
            f"/api/wallets/{self.wallet.id}/withdraw/",
            {"amount": "5.00", "idempotency_key": "wd-key"}, format="json",
        )
        self.assertEqual(first.status_code, 422)

        self.client.post(
            f"/api/wallets/{self.wallet.id}/deposit/",
            {"amount": "100.00", "idempotency_key": "fund-it"}, format="json",
        )

        retry = self.client.post(
            f"/api/wallets/{self.wallet.id}/withdraw/",
            {"amount": "5.00", "idempotency_key": "wd-key"}, format="json",
        )
        self.assertEqual(retry.status_code, 422)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("100.00"))

    def test_idempotency_key_is_scoped_per_tenant(self):
        other_tenant = create_tenant("Other")
        other_user = create_user(other_tenant, "Bob")
        other_wallet = create_wallet(other_tenant, other_user, balance="0.00")
        other_client = client_for(other_tenant)

        r1 = self.client.post(
            f"/api/wallets/{self.wallet.id}/deposit/",
            {"amount": "10.00", "idempotency_key": "shared-key"}, format="json",
        )
        r2 = other_client.post(
            f"/api/wallets/{other_wallet.id}/deposit/",
            {"amount": "10.00", "idempotency_key": "shared-key"}, format="json",
        )
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)

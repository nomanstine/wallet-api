from rest_framework.test import APIClient, APITestCase

from .helpers import client_for, create_tenant, create_user, create_wallet


class TenantIsolationTests(APITestCase):
    def setUp(self):
        self.tenant_a = create_tenant("A")
        self.tenant_b = create_tenant("B")
        self.user_a = create_user(self.tenant_a, "Alice")
        self.user_b = create_user(self.tenant_b, "Bob")
        self.wallet_a = create_wallet(self.tenant_a, self.user_a, balance="50.00")
        self.wallet_b = create_wallet(self.tenant_b, self.user_b, balance="50.00")
        self.client_a = client_for(self.tenant_a)
        self.client_b = client_for(self.tenant_b)

    def test_cannot_read_other_tenants_wallet(self):
        resp = self.client_a.get(f"/api/wallets/{self.wallet_b.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_cannot_list_other_tenants_wallets(self):
        resp = self.client_a.get("/api/wallets/")
        ids = {w["id"] for w in resp.data["results"]}
        self.assertNotIn(str(self.wallet_b.id), ids)

    def test_cannot_deposit_to_other_tenants_wallet(self):
        resp = self.client_a.post(
            f"/api/wallets/{self.wallet_b.id}/deposit/",
            {"amount": "5.00", "idempotency_key": "x"}, format="json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_cannot_withdraw_from_other_tenants_wallet(self):
        resp = self.client_a.post(
            f"/api/wallets/{self.wallet_b.id}/withdraw/",
            {"amount": "5.00", "idempotency_key": "x"}, format="json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_cannot_read_other_tenants_transaction_history(self):
        resp = self.client_a.get(f"/api/wallets/{self.wallet_b.id}/transactions/")
        self.assertEqual(resp.status_code, 404)

    def test_transfer_across_tenants_is_rejected(self):
        resp = self.client_a.post(
            "/api/transfers/",
            {
                "from_wallet_id": str(self.wallet_a.id),
                "to_wallet_id": str(self.wallet_b.id),
                "amount": "5.00",
                "idempotency_key": "t1",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_missing_tenant_credentials_rejected(self):
        client = APIClient()
        resp = client.get(f"/api/wallets/{self.wallet_a.id}/")
        self.assertEqual(resp.status_code, 401)

    def test_invalid_api_key_rejected(self):
        client = APIClient()
        client.credentials(HTTP_X_API_KEY="not-a-real-key")
        resp = client.get(f"/api/wallets/{self.wallet_a.id}/")
        self.assertEqual(resp.status_code, 401)

    def test_x_tenant_id_header_also_works(self):
        client = APIClient()
        client.credentials(HTTP_X_TENANT_ID=str(self.tenant_a.id))
        resp = client.get(f"/api/wallets/{self.wallet_a.id}/")
        self.assertEqual(resp.status_code, 200)

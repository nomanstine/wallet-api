import threading
from decimal import Decimal

from django.db import connections
from django.test import TransactionTestCase
from rest_framework import status

from .helpers import client_for, create_tenant, create_user, create_wallet


class ConcurrencyTests(TransactionTestCase):
    """
    Uses TransactionTestCase (not TestCase) because these tests need real,
    separately-committed transactions across threads -- TestCase wraps each
    test in one outer transaction, which would hide any locking behaviour.
    """

    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.wallet = create_wallet(self.tenant, self.user, balance="100.00")

    def _post(self, path, payload, results, index):
        try:
            client = client_for(self.tenant)
            resp = client.post(path, payload, format="json")
            results[index] = resp.status_code
        finally:
            connections.close_all()

    def test_concurrent_withdrawals_cannot_overdraw_the_wallet(self):
        # Balance is 100. Two concurrent withdrawals of 60 each: at most one
        # can succeed, otherwise the wallet would go negative.
        results = [None, None]
        path = f"/api/wallets/{self.wallet.id}/withdraw/"
        threads = [
            threading.Thread(
                target=self._post, args=(path, {"amount": "60.00", "idempotency_key": f"w{i}"}, results, i)
            )
            for i in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.wallet.refresh_from_db()
        successes = sum(1 for code in results if code == status.HTTP_201_CREATED)
        self.assertEqual(successes, 1, f"expected exactly one success, got statuses={results}")
        self.assertEqual(self.wallet.balance, Decimal("40.00"))

    def test_concurrent_transfers_in_opposite_directions_do_not_deadlock(self):
        other_user = create_user(self.tenant, "Bob")
        other_wallet = create_wallet(self.tenant, other_user, balance="100.00")

        results = [None, None]
        threads = [
            threading.Thread(
                target=self._post,
                args=(
                    "/api/transfers/",
                    {
                        "from_wallet_id": str(self.wallet.id),
                        "to_wallet_id": str(other_wallet.id),
                        "amount": "10.00",
                        "idempotency_key": "a-to-b",
                    },
                    results, 0,
                ),
            ),
            threading.Thread(
                target=self._post,
                args=(
                    "/api/transfers/",
                    {
                        "from_wallet_id": str(other_wallet.id),
                        "to_wallet_id": str(self.wallet.id),
                        "amount": "5.00",
                        "idempotency_key": "b-to-a",
                    },
                    results, 1,
                ),
            ),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        self.assertTrue(all(t.is_alive() is False for t in threads), "a thread deadlocked / never finished")
        self.assertEqual(results, [status.HTTP_201_CREATED, status.HTTP_201_CREATED])

        self.wallet.refresh_from_db()
        other_wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("95.00"))  # 100 - 10 + 5
        self.assertEqual(other_wallet.balance, Decimal("105.00"))  # 100 + 10 - 5

    def test_duplicate_idempotency_key_fired_concurrently_only_applies_once(self):
        results = [None, None]
        path = f"/api/wallets/{self.wallet.id}/deposit/"
        payload = {"amount": "25.00", "idempotency_key": "concurrent-dup"}
        threads = [
            threading.Thread(target=self._post, args=(path, payload, results, i)) for i in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.wallet.refresh_from_db()
        self.assertTrue(all(code == status.HTTP_201_CREATED for code in results), results)
        self.assertEqual(self.wallet.balance, Decimal("125.00"))

import hashlib
import json

from django.db import IntegrityError, transaction

from .exceptions import IdempotencyInProgress, IdempotencyKeyConflict
from .models import IdempotencyKey


def make_fingerprint(data):
    payload = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def run_idempotent(tenant, key, action, fingerprint_data, fn):

    fingerprint = make_fingerprint(fingerprint_data)

    with transaction.atomic():
        try:
            record = IdempotencyKey.objects.select_for_update().get(tenant=tenant, key=key)
            created = False
        except IdempotencyKey.DoesNotExist:
            try:
                with transaction.atomic():  # savepoint: isolate the race-prone insert
                    record = IdempotencyKey.objects.create(
                        tenant=tenant, key=key, action=action, request_fingerprint=fingerprint,
                    )
                created = True
            except IntegrityError:
                # Someone else won the race and inserted the row first.
                record = IdempotencyKey.objects.select_for_update().get(tenant=tenant, key=key)
                created = False

        if not created:
            if record.action != action or record.request_fingerprint != fingerprint:
                raise IdempotencyKeyConflict(
                    "This idempotency key was already used with different request parameters."
                )
            if record.response_status is None:
                raise IdempotencyInProgress(
                    "A request with this idempotency key is still being processed."
                )
            return record.response_status, record.response_body, True

        try:
            with transaction.atomic():  # savepoint: isolate the operation itself
                status_code, body = fn()
        except Exception as exc:
            status_code, body = _error_response(exc)

        record.response_status = status_code
        record.response_body = body
        record.save(update_fields=["response_status", "response_body"])
        return status_code, body, False


def _error_response(exc):
    to_dict = getattr(exc, "to_dict", None)
    if callable(to_dict):
        return exc.status_code, to_dict()
    raise exc

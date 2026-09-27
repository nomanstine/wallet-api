from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .exceptions import WalletServiceError


def custom_exception_handler(exc, context):
    if isinstance(exc, WalletServiceError):
        return Response(exc.to_dict(), status=exc.status_code)
    return drf_exception_handler(exc, context)

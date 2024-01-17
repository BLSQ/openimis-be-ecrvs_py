import logging

from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny

from ecrvs.models import HeraNotification
from ecrvs.services import process_hera_notification
from ecrvs.exception import HeraNotificationException

logger = logging.getLogger(__name__)


# Hera is sending us its own authorization Bearer JWT, we shouldn't try to validate it against the openIMIS rules
class NoAuthentication(BaseAuthentication):

    def authenticate(self, request):
        return (AnonymousUser(), None)


@api_view(["POST"])
@authentication_classes([NoAuthentication])
@permission_classes([AllowAny])
def hera_webhook(request):
    logger.info(f"Hera: new notification received")
    payload = request.data
    status = HeraNotification.determine_status(payload=payload)
    notification = HeraNotification.objects.create(
        status=status,
        operation=payload["operation"],
        context=payload["context"],
        topic=payload["topicName"],
        json_ext=payload,
    )
    if status != HeraNotification.STATUS_INVALID:
        try:
            process_hera_notification(notification)
            notification.set_processed()
            return JsonResponse({"status": "ok", "code": 200})
        except HeraNotificationException as e:
            notification.set_status(HeraNotification.STATUS_PROCESSED_ERROR)
            logger.exception("Known error while processing Hera notification on the webhook")
            return JsonResponse({"status": "error", "message": str(e), "data": payload, "code": 400})
        except Exception as e:
            notification.set_status(HeraNotification.STATUS_PROCESSED_ERROR)
            logger.exception("Unknown error while processing Hera notification on the webhook")
            return JsonResponse({"status": "error", "message": str(e), "data": payload, "code": 500})

    logger.error(f"Hera: received invalid notification - unknown value for context, operation or topic")
    return JsonResponse({
        "status": "error",
        "message": "invalid or unknown values for context, operation or topic",
        "data": payload,
        "code": 400,
    })

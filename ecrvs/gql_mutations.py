import logging
import graphene
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils.translation import gettext as _

from core.schema import OpenIMISMutation
from ecrvs.apps import EcrvsConfig
from ecrvs.models import HeraSubscriptionMutation, HeraSubscription
from ecrvs.services import create_hera_subscription, delete_hera_subscription

logger = logging.getLogger(__name__)


class CreateHeraSubscriptionMutation(OpenIMISMutation):
    _mutation_module = "ecrvs"
    _mutation_class = "CreateHeraSubscriptionMutation"

    class Input(OpenIMISMutation.Input):
        topic = graphene.String(required=True)

    @classmethod
    def async_mutate(cls, user, **data):
        try:
            if type(user) is AnonymousUser or not user.id:
                raise ValidationError(_("mutation.authentication_required"))
            if not user.has_perms(EcrvsConfig.gql_hera_subscription_create_perms):
                raise PermissionDenied(_("unauthorized"))

            client_mutation_id = data.get("client_mutation_id")
            subscription = create_hera_subscription(data["topic"], user.id_for_audit)

            HeraSubscriptionMutation.object_mutated(user,
                                                    client_mutation_id=client_mutation_id,
                                                    hera_subscription=subscription)
            return None
        except Exception as exc:
            logger.exception("ecrvs.mutation.failed_to_create_subscription")
            return [{
                'message': _("ecrvs.mutation.failed_to_create_subscription"),
                'detail': str(exc)
            }]


class DeleteHeraSubscriptionMutation(OpenIMISMutation):
    """
    Deletes (and unsubscribes) one or several HeraSubscriptions
    """

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)

    _mutation_module = "ecrvs"
    _mutation_class = "DeleteHeraSubscriptionMutation"

    @classmethod
    def async_mutate(cls, user, **data):
        if not user.has_perms(EcrvsConfig.gql_hera_subscription_delete_perms):
            raise PermissionDenied(_("unauthorized"))
        errors = []
        for subscription_uuid in data["uuids"]:
            subscription = HeraSubscription.objects.filter(uuid=subscription_uuid, active=True).first()
            if subscription is None:
                errors += {
                    'title': subscription_uuid,
                    'list': [{
                        'message': _("hera_subscription.validation.id_does_not_exist") % {'id': subscription_uuid}
                    }]
                }
                continue
            errors += delete_hera_subscription(subscription, user.id_for_audit)
        if len(errors) == 1:
            errors = errors[0]['list']
        return errors

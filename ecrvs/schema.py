import graphene
from graphene_django import DjangoObjectType
import graphene_django_optimizer as gql_optimizer


from core import ExtendedConnection
from core.schema import OrderedDjangoFilterConnectionField
from .gql_mutations import CreateHeraSubscriptionMutation, DeleteHeraSubscriptionMutation
from .models import HeraNotification, HeraSubscription


class HeraNotificationGQLType(DjangoObjectType):
    class Meta:
        model = HeraNotification
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            'id': ['exact'],
            'topic': ['exact', 'icontains', 'istartswith'],
            'context': ['exact', 'icontains', 'istartswith'],
            'operation': ['exact', 'icontains', 'istartswith'],
            'status': ['exact', 'icontains', 'istartswith'],
            'datetime_received': ['lt', 'lte', 'gt', 'gte'],
        }
        connection_class = ExtendedConnection


class HeraSubscriptionGQLType(DjangoObjectType):
    class Meta:
        model = HeraSubscription
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            'uuid': ['exact'],
            'active': ['exact'],
            'topic': ['exact', 'icontains', 'istartswith'],
            'created_at': ['lt', 'lte', 'gt', 'gte'],
        }
        connection_class = ExtendedConnection


class Query(graphene.ObjectType):
    hera_notifications = OrderedDjangoFilterConnectionField(
        HeraNotificationGQLType,
        orderBy=graphene.List(of_type=graphene.String)
    )
    hera_subscriptions = OrderedDjangoFilterConnectionField(
        HeraSubscriptionGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        client_mutation_id=graphene.String(),
    )

    def resolve_hera_notifications(self, info, client_mutation_id: str = None, **kwargs):
        queryset = HeraNotification.objects

        if client_mutation_id:
            queryset.filter(mutations__mutation__client_mutation_id=client_mutation_id)

        return gql_optimizer.query(queryset, info)


class Mutation(graphene.ObjectType):
    create_hera_subscription = CreateHeraSubscriptionMutation.Field()
    delete_hera_subscription = DeleteHeraSubscriptionMutation.Field()

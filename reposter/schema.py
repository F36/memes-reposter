import graphene
from graphene_django.debug import DjangoDebug

from apps.core.schema import CoreMutations, CoreQuery
from apps.reddit.schema import RedditMutation, RedditQuery
from apps.tgapp.schema import TelegramQuery


class Query(CoreQuery, RedditQuery, TelegramQuery, graphene.ObjectType):
    node = graphene.relay.Node.Field()
    debug = graphene.Field(DjangoDebug, name='__debug')


class Mutation(CoreMutations, RedditMutation, graphene.ObjectType):
    pass


# noinspection PyTypeChecker
schema = graphene.Schema(query=Query, mutation=Mutation)

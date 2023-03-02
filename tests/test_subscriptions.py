from asyncio import sleep, create_task, wait
from dataclasses import dataclass
from inspect import isawaitable
from typing import AsyncIterator, Optional

import pytest
from graphql import GraphQLSchema, GraphQLObjectType, GraphQLField, \
    GraphQLInt, subscribe, parse, MapAsyncIterator, graphql
from graphql.pyutils import SimplePubSub

from graphql_api import GraphQLAPI

count = 0
pubsub = SimplePubSub()


async def resolve_count(_root, info, **args):
    return count


async def resolve_increase_count(_root, info, **args):
    global count
    count += 1
    pubsub.emit(count)
    return count


def subscribe_count(_root, info):
    return pubsub.get_subscriber()


schema = GraphQLSchema(
    query=GraphQLObjectType(
        "RootQueryType",
        {
            "count": GraphQLField(GraphQLInt, resolve=resolve_count)
        },
    ),
    mutation=GraphQLObjectType(
        "RootMutationType",
        {
            "increaseCount": GraphQLField(
                GraphQLInt,
                resolve=resolve_increase_count
            )
        },
    ),
    subscription=GraphQLObjectType(
        "RootSubscriptionType",
        {
            "count": GraphQLField(
                GraphQLInt,
                subscribe=subscribe_count,
                resolve=lambda a, *args, **kwargs: a,
            )
        },
    ),
)


class TestSubscriptions:

    @pytest.mark.asyncio
    async def test_subscribe_to_count(self):

        a = await graphql(schema, "query {count}")
        b = await graphql(schema, "mutation {increaseCount}")
        c = await graphql(schema, "query {count}")

        query = "subscription {count}"

        subscription = await subscribe(schema, parse(query))
        assert isinstance(subscription, MapAsyncIterator)

        assert a and b and c

        received_count = []

        async def mutate_count():
            await sleep(0.1)  # make sure subscribers are running
            await graphql(schema, "mutation {increaseCount}")
            await sleep(0.1)
            await graphql(schema, "mutation {increaseCount}")
            await sleep(0.1)
            await graphql(schema, "mutation {increaseCount}")
            await sleep(0.1)
            await graphql(schema, "mutation {increaseCount}")

        subscription = subscribe(schema, parse(query))

        async def receive_count():
            async for result in await subscription:
                received_count.append(result)

        done, pending = await wait([
            create_task(receive_count()), create_task(mutate_count())
        ], timeout=1)

        assert len(received_count) == 4 \
               and all(result.data["count"] for result in received_count)

    @pytest.mark.asyncio
    async def test_graphql_api_subscribe(self):
        api = GraphQLAPI()

        @dataclass
        class Comment:
            user: str
            comment: str

        @api.type(root=True)
        class Root:

            @api.field
            # async
            def on_comment_added(
                    self,
                    by_user: str = None
            ) -> Comment:   # AsyncIterator[Comment]:
                return Comment(user="rob", comment="test comment")
                # comment_pub_sub = SimplePubSub()
                # return comment_pub_sub.get_subscriber()

        executor = api.executor()

        test_input_query = '''
            query {
                onCommentAdded {
                    comment
                }
            }
        '''

        result = executor.execute(test_input_query)

        expected = {
            "onCommentAdded": {"comment": "test comment"}
        }
        assert not result.errors
        assert result.data == expected

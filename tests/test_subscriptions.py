from asyncio import create_task, sleep, wait
from dataclasses import dataclass
from typing import AsyncGenerator
import enum

import pytest
from graphql import (
    GraphQLField,
    GraphQLInt,
    GraphQLObjectType,
    GraphQLSchema,
    MapAsyncIterator,
    graphql,
    parse,
    subscribe,
)
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
        {"count": GraphQLField(GraphQLInt, resolve=resolve_count)},
    ),
    mutation=GraphQLObjectType(
        "RootMutationType",
        {"increaseCount": GraphQLField(GraphQLInt, resolve=resolve_increase_count)},
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

        subscription = await subscribe(schema, parse(query))  # type: ignore

        async def receive_count():
            async for result in subscription:  # type: ignore
                received_count.append(result)

        done, pending = await wait(
            [create_task(receive_count()), create_task(mutate_count())], timeout=1
        )

        assert len(received_count) == 4 and all(
            result.data["count"] for result in received_count
        )

    @pytest.mark.asyncio
    async def test_graphql_api_subscribe(self):
        api = GraphQLAPI()

        @dataclass
        class Comment:
            user: str
            comment: str

        # Define a Subscription root that yields comments
        @api.type(is_root_type=True)
        class Query:
            @api.field
            def ping(self) -> str:
                return "pong"

        @api.type()
        class Subscription:
            @api.field
            async def on_comment_added(self, by_user: str = "") -> AsyncGenerator[Comment, None]:
                # simple async generator emitting two comments
                yield Comment(user="rob", comment="first")  # type: ignore
                yield Comment(user="rob", comment="second")  # type: ignore

        # Build API with subscription type
        api.subscription_type = Subscription
        executor = api.executor()

        # Start subscription
        subscription_query = """
            subscription {
                onCommentAdded {
                    comment
                }
            }
        """

        async_iter = await executor.subscribe(subscription_query)

        received = []
        async for result in async_iter:
            received.append(result.data)
            if len(received) >= 2:
                break

        assert received == [
            {"onCommentAdded": {"comment": "first"}},
            {"onCommentAdded": {"comment": "second"}},
        ]

    @pytest.mark.asyncio
    async def test_subscription_with_arguments(self):
        """Test subscription with arguments"""
        api = GraphQLAPI()

        @dataclass
        class Message:
            id: int
            content: str
            user: str
            timestamp: str

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def ping(self) -> str:
                return "pong"

        @api.type()
        class Subscription:
            @api.field
            async def on_message(self, user_id: str = "", channel: str = "") -> AsyncGenerator[Message, None]:
                # Filter messages based on arguments
                if user_id == "user1" and channel == "general":
                    yield Message(id=1, content="Hello user1", user="user1", timestamp="2024-01-01T10:00:00Z")
                    yield Message(id=2, content="Welcome to general", user="user1", timestamp="2024-01-01T10:01:00Z")
                elif user_id == "user2":
                    yield Message(id=3, content="Hi user2", user="user2", timestamp="2024-01-01T10:02:00Z")

        api.subscription_type = Subscription
        executor = api.executor()

        # Test subscription with arguments
        subscription_query = """
            subscription($userId: String!, $channel: String!) {
                onMessage(userId: $userId, channel: $channel) {
                    id
                    content
                    user
                    timestamp
                }
            }
        """

        variables = {"userId": "user1", "channel": "general"}
        async_iter = await executor.subscribe(subscription_query, variables=variables)

        received = []
        async for result in async_iter:
            received.append(result.data)
            if len(received) >= 2:
                break

        assert len(received) == 2
        assert received[0]["onMessage"]["user"] == "user1"
        assert received[1]["onMessage"]["content"] == "Welcome to general"

    @pytest.mark.asyncio
    async def test_subscription_with_complex_types(self):
        """Test subscription with complex nested types"""
        api = GraphQLAPI()

        @dataclass
        class User:
            id: str
            name: str
            email: str

        @dataclass
        class Post:
            id: str
            title: str
            content: str
            author: User
            tags: list[str]

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def ping(self) -> str:
                return "pong"

        @api.type()
        class Subscription:
            @api.field
            async def on_post_created(self, category: str = "") -> AsyncGenerator[Post, None]:
                if category == "tech":
                    yield Post(
                        id="post1",
                        title="GraphQL Subscriptions",
                        content="Learn about GraphQL subscriptions",
                        author=User(id="user1", name="Alice", email="alice@example.com"),
                        tags=["graphql", "subscriptions", "tech"]
                    )
                    yield Post(
                        id="post2",
                        title="Async Programming",
                        content="Understanding async/await",
                        author=User(id="user2", name="Bob", email="bob@example.com"),
                        tags=["python", "async", "tech"]
                    )

        api.subscription_type = Subscription
        executor = api.executor()

        subscription_query = """
            subscription($category: String!) {
                onPostCreated(category: $category) {
                    id
                    title
                    content
                    author {
                        id
                        name
                        email
                    }
                    tags
                }
            }
        """

        variables = {"category": "tech"}
        async_iter = await executor.subscribe(subscription_query, variables=variables)

        received = []
        async for result in async_iter:
            received.append(result.data)
            if len(received) >= 2:
                break

        assert len(received) == 2
        assert received[0]["onPostCreated"]["author"]["name"] == "Alice"
        assert "graphql" in received[0]["onPostCreated"]["tags"]
        assert received[1]["onPostCreated"]["title"] == "Async Programming"

    @pytest.mark.asyncio
    async def test_subscription_with_enum_types(self):
        """Test subscription with enum types"""
        api = GraphQLAPI()

        class Status(enum.Enum):
            ONLINE = "online"
            OFFLINE = "offline"
            AWAY = "away"

        @dataclass
        class UserStatus:
            user_id: str
            status: Status
            last_seen: str

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def ping(self) -> str:
                return "pong"

        @api.type()
        class Subscription:
            @api.field
            async def on_user_status_change(self, status_filter: str = "") -> AsyncGenerator[UserStatus, None]:
                if status_filter == "online":
                    yield UserStatus(user_id="user1", status=Status.ONLINE, last_seen="2024-01-01T10:00:00Z")
                    yield UserStatus(user_id="user2", status=Status.ONLINE, last_seen="2024-01-01T10:01:00Z")
                elif status_filter == "offline":
                    yield UserStatus(user_id="user3", status=Status.OFFLINE, last_seen="2024-01-01T09:59:00Z")

        api.subscription_type = Subscription
        executor = api.executor()

        subscription_query = """
            subscription($statusFilter: String!) {
                onUserStatusChange(statusFilter: $statusFilter) {
                    userId
                    status
                    lastSeen
                }
            }
        """

        variables = {"statusFilter": "online"}
        async_iter = await executor.subscribe(subscription_query, variables=variables)

        received = []
        async for result in async_iter:
            received.append(result.data)
            if len(received) >= 2:
                break

        assert len(received) == 2
        assert received[0]["onUserStatusChange"]["status"] == "ONLINE"
        assert received[1]["onUserStatusChange"]["userId"] == "user2"

    @pytest.mark.asyncio
    async def test_subscription_error_handling(self):
        """Test subscription error handling"""
        api = GraphQLAPI()

        @dataclass
        class Data:
            value: str

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def ping(self) -> str:
                return "pong"

        @api.type()
        class Subscription:
            @api.field
            async def on_data_with_error(self, should_error: bool = False) -> AsyncGenerator[Data, None]:
                if should_error:
                    raise Exception("Simulated subscription error")
                yield Data(value="success")
                yield Data(value="more data")

        api.subscription_type = Subscription
        executor = api.executor()

        # Test successful subscription
        subscription_query = """
            subscription($shouldError: Boolean!) {
                onDataWithError(shouldError: $shouldError) {
                    value
                }
            }
        """

        # Test without error
        variables = {"shouldError": False}
        async_iter = await executor.subscribe(subscription_query, variables=variables)

        received = []
        async for result in async_iter:
            received.append(result.data)
            if len(received) >= 2:
                break

        assert len(received) == 2
        assert received[0]["onDataWithError"]["value"] == "success"
        assert received[1]["onDataWithError"]["value"] == "more data"

        # Test with error (should raise exception)
        variables = {"shouldError": True}
        with pytest.raises(Exception, match="Simulated subscription error"):
            async_iter = await executor.subscribe(subscription_query, variables=variables)
            async for result in async_iter:
                pass

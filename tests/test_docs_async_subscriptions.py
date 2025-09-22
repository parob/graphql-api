"""
Test all code examples from the async-and-subscriptions.md documentation
"""
import pytest
import asyncio
from typing import AsyncGenerator
from graphql_api.api import GraphQLAPI


class TestAsyncSubscriptionsExamples:

    def test_async_resolvers(self):
        """Test async resolvers from async-and-subscriptions.md"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            async def fetch_remote_data(self) -> str:
                """
                Simulates fetching data from a remote service.
                """
                # In a real application, this could be an HTTP request
                # or a database query using an async library.
                await asyncio.sleep(0.01)  # Use shorter sleep for testing
                return "Data fetched successfully!"

        # Test async query execution (api.execute works with async resolvers)
        result = api.execute("query { fetchRemoteData }")

        assert not result.errors
        assert result.data == {"fetchRemoteData": "Data fetched successfully!"}

    @pytest.mark.asyncio
    async def test_mode1_subscriptions(self):
        """Test Mode 1 subscriptions from async-and-subscriptions.md"""
        api = GraphQLAPI()

        # Mock function for testing
        def get_user_from_db(user_id):
            return {"id": user_id, "name": f"User {user_id}"}

        @api.type(is_root_type=True)
        class Root:
            # Subscription field - automatically detected by AsyncGenerator return type
            @api.field
            async def on_user_updated(self, user_id: int) -> AsyncGenerator[dict, None]:
                """Real-time user updates"""
                # For testing, just yield a couple of updates
                for i in range(2):
                    await asyncio.sleep(0.01)  # Short sleep for testing
                    yield get_user_from_db(user_id)

            # You can also explicitly mark fields as subscriptions
            @api.field(subscription=True)
            async def count(self, to: int = 5) -> AsyncGenerator[int, None]:
                """Counts up to a given number, yielding each number."""
                for i in range(1, min(to + 1, 3)):  # Limit to 2 for testing
                    await asyncio.sleep(0.01)
                    yield i

        executor = api.executor()

        # Test subscription execution
        subscription_query = """
        subscription {
            count(to: 2)
        }
        """

        async_iter = await executor.subscribe(subscription_query)

        received = []
        async for result in async_iter:
            received.append(result.data)
            if len(received) >= 2:
                break

        assert received == [
            {"count": 1},
            {"count": 2}
        ]

    @pytest.mark.asyncio
    async def test_mode2_subscriptions(self):
        """Test Mode 2 subscriptions from async-and-subscriptions.md"""
        api = GraphQLAPI()

        # Mock function for testing
        def get_user_from_db(user_id):
            return {"id": user_id, "name": f"User {user_id}"}

        @api.type
        class Subscription:
            @api.field
            async def on_user_updated(self, user_id: int) -> AsyncGenerator[dict, None]:
                """Real-time user updates"""
                # For testing, just yield one update
                await asyncio.sleep(0.01)
                yield get_user_from_db(user_id)

            @api.field
            async def count(self, to: int = 5) -> AsyncGenerator[int, None]:
                """Counts up to a given number, yielding each number."""
                for i in range(1, min(to + 1, 3)):  # Limit to 2 for testing
                    await asyncio.sleep(0.01)
                    yield i

        # Need a query type for Mode 2
        @api.type
        class Query:
            @api.field
            def placeholder(self) -> str:
                return "placeholder"

        # Use explicit types mode
        api.query_type = Query
        api.subscription_type = Subscription

        executor = api.executor()

        # Test subscription execution
        subscription_query = """
        subscription {
            onUserUpdated(userId: 123)
        }
        """

        async_iter = await executor.subscribe(subscription_query)

        result = await async_iter.__anext__()
        assert not result.errors
        assert result.data == {"onUserUpdated": '{"id": 123, "name": "User 123"}'}

    def test_sync_resolvers_still_work(self):
        """Test that synchronous resolvers still work alongside async ones"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def sync_field(self) -> str:
                return "sync result"

            @api.field
            async def async_field(self) -> str:
                await asyncio.sleep(0.01)
                return "async result"

        # Test synchronous execution
        result = api.execute("query { syncField }")
        assert not result.errors
        assert result.data == {"syncField": "sync result"}

    def test_mixed_sync_async_execution(self):
        """Test that mixed sync/async fields work in execution"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def sync_field(self) -> str:
                return "sync result"

            @api.field
            async def async_field(self) -> str:
                await asyncio.sleep(0.01)
                return "async result"

        # Test execution with both field types
        result = api.execute("query { syncField asyncField }")

        assert not result.errors
        assert result.data == {
            "syncField": "sync result",
            "asyncField": "async result"
        }

    @pytest.mark.asyncio
    async def test_subscription_with_arguments(self):
        """Test subscriptions with arguments"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            async def countdown(self, start: int = 3) -> AsyncGenerator[int, None]:
                """Countdown from a given number"""
                for i in range(start, 0, -1):
                    await asyncio.sleep(0.01)
                    yield i

        executor = api.executor()

        subscription_query = """
        subscription {
            countdown(start: 2)
        }
        """

        async_iter = await executor.subscribe(subscription_query)

        received = []
        async for result in async_iter:
            received.append(result.data)
            if len(received) >= 2:
                break

        assert received == [
            {"countdown": 2},
            {"countdown": 1}
        ]

    def test_schema_generation_with_subscriptions(self):
        """Test that subscriptions generate correct schema types"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def query_field(self) -> str:
                return "query"

            @api.field(mutable=True)
            def mutation_field(self) -> str:
                return "mutation"

            @api.field
            async def subscription_field(self) -> AsyncGenerator[str, None]:
                yield "subscription"

        schema, meta = api.build_schema()

        # Verify all three types exist
        assert schema.query_type is not None
        assert schema.mutation_type is not None
        assert schema.subscription_type is not None

        # Verify field names (converted to camelCase)
        assert "queryField" in schema.query_type.fields
        assert "mutationField" in schema.mutation_type.fields
        assert "subscriptionField" in schema.subscription_type.fields

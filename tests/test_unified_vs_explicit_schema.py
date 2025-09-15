"""
Test unified vs explicit schema definition approaches:
- Unified Schema: Single class with automatic field type separation
- Explicit Schema: Separate classes for each GraphQL operation type
"""
from dataclasses import dataclass
from typing import AsyncGenerator

import pytest
from graphql_api.api import GraphQLAPI


@dataclass
class User:
    id: int
    name: str


@dataclass
class Message:
    id: int
    content: str
    user: User


class TestUnifiedVsExplicitSchema:

    def test_unified_schema_with_asyncgen_auto_detection(self) -> None:
        """Test unified schema with AsyncGenerator auto-detection for subscriptions"""

        # Create API first
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            # Query field
            @api.field
            def get_user(self, user_id: int) -> User:
                return User(id=user_id, name=f"User {user_id}")

            # Mutation field
            @api.field(mutable=True)
            def update_user(self, user_id: int, name: str) -> User:
                return User(id=user_id, name=name)

            # Subscription field - auto-detected by AsyncGenerator
            @api.field
            async def on_user_updated(self, user_id: int) -> AsyncGenerator[User, None]:
                yield User(id=user_id, name="Updated User")

        # Update API to use the decorated Root type
        api.root_type = Root
        schema, meta = api.build_schema()

        # Verify all three types exist
        assert schema.query_type is not None
        assert schema.mutation_type is not None
        assert schema.subscription_type is not None

        # Verify field names
        assert "getUser" in schema.query_type.fields
        assert "updateUser" in schema.mutation_type.fields
        assert "onUserUpdated" in schema.subscription_type.fields

    def test_unified_schema_with_explicit_subscription(self) -> None:
        """Test unified schema with explicit subscription=True parameter"""
        # Create API first
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def get_message(self, msg_id: int) -> Message:
                return Message(id=msg_id, content="Test", user=User(id=1, name="Test"))

            @api.field(mutable=True)
            def send_message(self, content: str) -> Message:
                return Message(id=123, content=content, user=User(id=1, name="Sender"))

            # Explicit subscription field
            @api.field(subscription=True)
            async def on_message_sent(self) -> AsyncGenerator[Message, None]:
                yield Message(id=456, content="New message", user=User(id=2, name="User"))

        # Update API to use the decorated Root type
        api.root_type = Root
        schema, meta = api.build_schema()

        assert schema.query_type is not None
        assert schema.mutation_type is not None
        assert schema.subscription_type is not None

        assert "getMessage" in schema.query_type.fields
        assert "sendMessage" in schema.mutation_type.fields
        assert "onMessageSent" in schema.subscription_type.fields

    def test_explicit_schema_with_separate_types(self) -> None:
        """Test explicit schema with separate Query, Mutation, and Subscription classes"""
        # Create API for explicit types mode
        api = GraphQLAPI()

        @api.type
        class Query:
            @api.field
            def get_user(self, user_id: int) -> User:
                return User(id=user_id, name=f"User {user_id}")

        @api.type
        class Mutation:
            @api.field
            def create_user(self, name: str) -> User:
                return User(id=999, name=name)

        @api.type
        class Subscription:
            @api.field
            async def on_user_created(self) -> AsyncGenerator[User, None]:
                yield User(id=888, name="New User")

        # Set explicit types and build schema
        api.query_type = Query
        api.mutation_type = Mutation
        api.subscription_type = Subscription

        schema, meta = api.build_schema()

        assert schema.query_type is not None
        assert schema.mutation_type is not None
        assert schema.subscription_type is not None

        assert "getUser" in schema.query_type.fields
        assert "createUser" in schema.mutation_type.fields
        assert "onUserCreated" in schema.subscription_type.fields

    def test_explicit_schema_query_only(self) -> None:
        """Test explicit schema with only Query type (minimal setup)"""
        # Create API for minimal mode
        api = GraphQLAPI()

        @api.type
        class Query:
            @api.field
            def hello(self) -> str:
                return "Hello World"

        # Set only query_type and build schema
        api.query_type = Query
        schema, meta = api.build_schema()

        assert schema.query_type is not None
        assert schema.mutation_type is None
        assert schema.subscription_type is None

        assert "hello" in schema.query_type.fields

    def test_validation_cannot_mix_schema_styles(self) -> None:
        """Test that mixing unified and explicit schema styles raises ValueError"""
        class DummyRoot:
            pass

        api = GraphQLAPI(root_type=DummyRoot)

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def test(self) -> str:
                return "test"

        @api.type
        class Query:
            @api.field
            def hello(self) -> str:
                return "hello"

        # Should raise error when mixing schema definition styles
        with pytest.raises(ValueError, match="Cannot use root_type with query_type"):
            GraphQLAPI(root_type=Root, query_type=Query)

    def test_empty_api_creates_placeholder(self) -> None:
        """Test that empty API creates placeholder schema for backward compatibility"""
        # Empty constructor is allowed for backward compatibility
        api = GraphQLAPI()
        schema, meta = api.build_schema()

        # Should create a placeholder query type
        assert schema.query_type is not None
        assert schema.query_type.name == "PlaceholderQuery"
        assert "placeholder" in schema.query_type.fields

    def test_field_cannot_be_both_mutable_and_subscription(self) -> None:
        """Test that a field cannot be both mutable and subscription"""
        class DummyRoot:
            pass

        api = GraphQLAPI(root_type=DummyRoot)

        # This should raise error during decorator execution
        with pytest.raises(ValueError, match="Field cannot be both mutable and subscription"):
            @api.field(mutable=True, subscription=True)
            def invalid_field(self) -> str:
                return "invalid"

    @pytest.mark.asyncio
    async def test_unified_schema_subscription_execution(self) -> None:
        """Test that unified schema subscription actually works"""
        # Create API first
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def ping(self) -> str:
                return "pong"

            @api.field
            async def on_ping(self, count: int = 2) -> AsyncGenerator[str, None]:
                for i in range(count):
                    yield f"ping {i + 1}"

        # Update API to use the decorated Root type
        api.root_type = Root
        executor = api.executor()

        subscription_query = """
            subscription {
                onPing(count: 2)
            }
        """

        async_iter = await executor.subscribe(subscription_query)

        received = []
        async for result in async_iter:
            received.append(result.data)
            if len(received) >= 2:
                break

        assert received == [
            {"onPing": "ping 1"},
            {"onPing": "ping 2"}
        ]

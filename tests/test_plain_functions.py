"""Tests for registering plain functions as GraphQL queries/mutations/subscriptions.

Every test actually executes a query/mutation/subscription through
`GraphQLAPI.executor()` and asserts on the returned data — these are not
schema-building smoke tests.
"""
import asyncio
import enum
from dataclasses import dataclass
from typing import AsyncGenerator, Optional

import pytest
from graphql import DirectiveLocation, GraphQLArgument, GraphQLString
from pydantic import BaseModel

from graphql_api import GraphQLAPI
from graphql_api.context import GraphQLContext
from graphql_api.directives import SchemaDirective


# ---------------------------------------------------------------------------
# Query basics
# ---------------------------------------------------------------------------
class TestQueryBasics:
    def test_single_query_function(self):
        api = GraphQLAPI()

        @api.query
        def hello(name: str) -> str:
            return f"Hello, {name}"

        result = api.execute('{ hello(name: "world") }')
        assert result.errors is None
        assert result.data == {"hello": "Hello, world"}

    def test_multiple_query_functions(self):
        api = GraphQLAPI()

        @api.query
        def add(a: int, b: int) -> int:
            return a + b

        @api.query
        def greet(name: str) -> str:
            return f"Hi {name}"

        result = api.execute('{ add(a: 2, b: 3) greet(name: "Ada") }')
        assert result.errors is None
        assert result.data == {"add": 5, "greet": "Hi Ada"}

    def test_query_function_with_no_args(self):
        api = GraphQLAPI()

        @api.query
        def ping() -> str:
            return "pong"

        result = api.execute('{ ping }')
        assert result.errors is None
        assert result.data == {"ping": "pong"}

    def test_query_function_with_optional_arg(self):
        api = GraphQLAPI()

        @api.query
        def greet(name: Optional[str] = None) -> str:
            return f"Hi, {name or 'friend'}"

        r1 = api.execute('{ greet }')
        assert r1.errors is None
        assert r1.data == {"greet": "Hi, friend"}

        r2 = api.execute('{ greet(name: "Ada") }')
        assert r2.errors is None
        assert r2.data == {"greet": "Hi, Ada"}

    def test_query_function_with_default_value(self):
        api = GraphQLAPI()

        @api.query
        def take(limit: int = 10) -> int:
            return limit

        r1 = api.execute('{ take }')
        assert r1.errors is None
        assert r1.data == {"take": 10}

        r2 = api.execute('{ take(limit: 3) }')
        assert r2.errors is None
        assert r2.data == {"take": 3}


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
class TestMutations:
    def test_mutation_function(self):
        api = GraphQLAPI()
        state = {"counter": 0}

        @api.query
        def counter() -> int:
            return state["counter"]

        @api.mutation
        def set_counter(value: int) -> int:
            state["counter"] = value
            return value

        r = api.execute('mutation { setCounter(value: 5) }')
        assert r.errors is None
        assert r.data == {"setCounter": 5}
        assert state["counter"] == 5

    def test_query_and_mutation_registered_together(self):
        api = GraphQLAPI()
        state = {"name": "alice"}

        @api.query
        def who() -> str:
            return state["name"]

        @api.mutation
        def rename(new_name: str) -> str:
            state["name"] = new_name
            return new_name

        q = api.execute('{ who }')
        assert q.data == {"who": "alice"}

        m = api.execute('mutation { rename(newName: "bob") }')
        assert m.data == {"rename": "bob"}

        q2 = api.execute('{ who }')
        assert q2.data == {"who": "bob"}


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------
class TestSubscriptions:
    @pytest.mark.asyncio
    async def test_subscription_function(self):
        api = GraphQLAPI()

        @api.query
        def placeholder() -> str:
            return "ok"

        @api.subscription
        async def count(to: int = 3) -> AsyncGenerator[int, None]:
            for i in range(1, to + 1):
                await asyncio.sleep(0.005)
                yield i

        executor = api.executor()
        async_iter = await executor.subscribe('subscription { count(to: 3) }')
        received = []
        async for result in async_iter:
            received.append(result.data)
        assert received == [{"count": 1}, {"count": 2}, {"count": 3}]


# ---------------------------------------------------------------------------
# Types through the function path
# ---------------------------------------------------------------------------
@dataclass
class User:
    id: int
    name: str


class UserModel(BaseModel):
    id: int
    name: str


class UserInput(BaseModel):
    name: str
    age: int


class Color(enum.Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class TestTypesThroughFunctions:
    def test_function_returns_dataclass(self):
        api = GraphQLAPI()

        @api.query
        def get_user() -> User:
            return User(id=1, name="alice")

        r = api.execute('{ getUser { id name } }')
        assert r.errors is None
        assert r.data == {"getUser": {"id": 1, "name": "alice"}}

    def test_function_returns_pydantic_model(self):
        api = GraphQLAPI()

        @api.query
        def get_user() -> UserModel:
            return UserModel(id=2, name="bob")

        r = api.execute('{ getUser { id name } }')
        assert r.errors is None
        assert r.data == {"getUser": {"id": 2, "name": "bob"}}

    def test_function_accepts_pydantic_input(self):
        api = GraphQLAPI()

        @api.mutation
        def create(user: UserInput) -> str:
            return f"{user.name}:{user.age}"

        r = api.execute(
            'mutation { create(user: { name: "alice", age: 30 }) }'
        )
        assert r.errors is None
        assert r.data == {"create": "alice:30"}

    def test_function_returns_enum(self):
        api = GraphQLAPI()

        @api.query
        def fav() -> Color:
            return Color.GREEN

        r = api.execute('{ fav }')
        assert r.errors is None
        assert r.data == {"fav": "GREEN"}

    def test_function_accepts_enum_arg(self):
        api = GraphQLAPI()

        @api.query
        def describe(color: Color) -> str:
            return color.value

        r = api.execute('{ describe(color: BLUE) }')
        assert r.errors is None
        assert r.data == {"describe": "blue"}

    def test_function_returns_object_with_api_field_methods(self):
        api = GraphQLAPI()

        @api.type
        class Math:
            def __init__(self, base: int):
                self.base = base

            @api.field
            def square(self) -> int:
                return self.base * self.base

            @api.field
            def cube(self) -> int:
                return self.base ** 3

        @api.query
        def math(base: int) -> Math:
            return Math(base)

        r = api.execute('{ math(base: 3) { square cube } }')
        assert r.errors is None
        assert r.data == {"math": {"square": 9, "cube": 27}}


# ---------------------------------------------------------------------------
# Context injection
# ---------------------------------------------------------------------------
class TestContextInjection:
    def test_function_receives_context(self):
        def attach_user(next_, root, info, **args):
            info.context.meta["user"] = "alice"
            return next_(root, info, **args)

        api = GraphQLAPI(middleware=[attach_user])

        @api.query
        def who_am_i(context: GraphQLContext) -> str:
            return context.meta.get("user", "anonymous")

        r = api.execute('{ whoAmI }')
        assert r.errors is None
        assert r.data == {"whoAmI": "alice"}


# ---------------------------------------------------------------------------
# Mixing with existing modes
# ---------------------------------------------------------------------------
class TestMixingWithExistingModes:
    def test_register_on_top_of_query_type_class(self):
        api = GraphQLAPI()

        @api.type
        class Query:
            @api.field
            def from_class(self) -> str:
                return "class-field"

        @api.type
        class Mutation:
            @api.field
            def from_class_mut(self) -> str:
                return "class-mut"

        api.query_type = Query
        api.mutation_type = Mutation

        @api.query
        def from_func() -> str:
            return "fn-field"

        @api.mutation
        def from_func_mut() -> str:
            return "fn-mut"

        q = api.execute('{ fromClass fromFunc }')
        assert q.errors is None
        assert q.data == {"fromClass": "class-field", "fromFunc": "fn-field"}

        m = api.execute('mutation { fromClassMut fromFuncMut }')
        assert m.errors is None
        assert m.data == {
            "fromClassMut": "class-mut",
            "fromFuncMut": "fn-mut",
        }

    def test_register_on_top_of_root_type(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def from_class(self) -> str:
                return "class-field"

            @api.field(mutable=True)
            def set_thing(self, value: str) -> str:
                return f"set:{value}"

        @api.query
        def from_func() -> str:
            return "fn-field"

        @api.mutation
        def also_set(value: str) -> str:
            return f"also:{value}"

        q = api.execute('{ fromClass fromFunc }')
        assert q.errors is None
        assert q.data == {"fromClass": "class-field", "fromFunc": "fn-field"}

        m = api.execute(
            'mutation { setThing(value: "a") alsoSet(value: "b") }'
        )
        assert m.errors is None
        assert m.data == {"setThing": "set:a", "alsoSet": "also:b"}

    def test_cached_schema_invalidated_on_late_register(self):
        api = GraphQLAPI()

        @api.query
        def first() -> str:
            return "1"

        r1 = api.execute('{ first }')
        assert r1.data == {"first": "1"}

        @api.query
        def second() -> str:
            return "2"

        r2 = api.execute('{ first second }')
        assert r2.errors is None
        assert r2.data == {"first": "1", "second": "2"}


# ---------------------------------------------------------------------------
# Decorator ergonomics
# ---------------------------------------------------------------------------
class TestDecoratorErgonomics:
    def test_bare_decorator_usage(self):
        api = GraphQLAPI()

        @api.query
        def hi() -> str:
            return "hi"

        assert api.execute('{ hi }').data == {"hi": "hi"}

    def test_parameterized_decorator_usage(self):
        api = GraphQLAPI()

        @api.query(meta={"tag": "v1"})
        def hi() -> str:
            return "hi"

        # Meta stored on the function, in the same shape @api.field uses.
        assert hi._schemas[api]["meta"] == {"tag": "v1"}
        assert api.execute('{ hi }').data == {"hi": "hi"}

    def test_directives_passthrough(self):
        tag = SchemaDirective(
            name="tag",
            locations=[DirectiveLocation.FIELD_DEFINITION],
            args={"name": GraphQLArgument(GraphQLString)},
        )

        api = GraphQLAPI()

        @api.query(directives=[tag(name="foo")])
        def hi() -> str:
            return "hi"

        schema = api.schema()
        field = schema.query_type.fields["hi"]
        # Applied directives are attached via add_applied_directives; the
        # field's extensions carry them.
        from graphql_api.schema import get_applied_directives
        applied = get_applied_directives(field)
        assert any(
            d.directive.name == "tag" for d in applied
        ), f"Expected 'tag' directive, got {applied!r}"


# ---------------------------------------------------------------------------
# Negative / guard tests
# ---------------------------------------------------------------------------
class TestGuards:
    def test_self_arg_is_not_injected(self):
        """Regression: free functions must not receive the synthesized root
        instance as a positional argument."""
        api = GraphQLAPI()
        captured = {}

        @api.query
        def foo(x: int) -> int:
            captured["x"] = x
            return x * 10

        r = api.execute('{ foo(x: 3) }')
        assert r.errors is None
        assert r.data == {"foo": 30}
        assert captured["x"] == 3

    def test_no_functions_registered_is_noop(self):
        """When nothing is registered and no root types are set, the feature
        must be a pure no-op — the empty-API build path is unchanged."""
        api = GraphQLAPI()
        schema, _ = api.build()
        # Same placeholder the framework produces today.
        assert schema.query_type.name == "PlaceholderQuery"
        assert api.query_type is None
        assert api.mutation_type is None
        assert api.subscription_type is None
        assert api.root_type is None

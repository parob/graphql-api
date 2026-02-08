import asyncio
from typing import Any

from graphql_api import GraphQLAPI
from graphql_api.middleware import middleware_local_proxy, middleware_call_coroutine
from graphql_api.remote import GraphQLRemoteObject


class TestMiddleware:
    def test_middleware_local_proxy(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class House:
            @api.field
            def number_of_doors(self) -> int:
                return 5

        # noinspection PyTypeChecker
        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore

        def remote_iterable(root, info, **args):
            return house

        # Testing a bug where this would throw a GraphQLError
        # exception if a function returning a GraphQLRemoteObject
        # was passed
        value = middleware_local_proxy(remote_iterable, None, None)

        assert value == house

    def test_middleware(self) -> None:
        def log_middleware(next_, root, info, **args) -> Any:
            print("before")
            value = next_(root, info, **args)
            print("after")
            return value

        api = GraphQLAPI(middleware=[log_middleware])

        @api.type(is_root_type=True)
        class House:
            @api.field
            def number(self) -> int:
                return 5

        result = api.execute(query="{number}")

        assert result.data

    def test_middleware_call_coroutine_sync_context(self) -> None:
        async def _next(_root, _info, **_args):
            return 123

        value = middleware_call_coroutine(_next, None, None)
        assert value == 123

    @staticmethod
    async def _run_middleware_in_async_context() -> int:
        async def _next(_root, _info, **_args):
            return 456

        value = middleware_call_coroutine(_next, None, None)
        return await value

    def test_middleware_call_coroutine_async_context(self) -> None:
        value = asyncio.run(self._run_middleware_in_async_context())
        assert value == 456

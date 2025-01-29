from typing import Callable, Any

from graphql_api import GraphQLAPI
from graphql_api.middleware import middleware_local_proxy
from graphql_api.remote import GraphQLRemoteObject


class TestMiddleware:
    def test_middleware(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class House:
            @api.field
            def number_of_doors(self) -> int:
                return 5

        # noinspection PyTypeChecker
        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)

        def remote_iterable():
            return house

        # Testing a bug where this would throw a GraphQLError
        # exception if a function returning a GraphQLRemoteObject
        # was passed
        value = middleware_local_proxy(remote_iterable, None)

        assert value == house

    def test_middleware_local_proxy(self):
        def log_middleware(next: Callable, _) -> Any:
            print("before")
            value = next()
            print("after")
            return value

        api = GraphQLAPI(middleware=[log_middleware])

        @api.type(is_root_type=True)
        class House:
            @api.field
            def number(self) -> int:
                return 5

        # Testing a bug where this would throw a GraphQLError
        # exception if a function returning a GraphQLRemoteObject
        # was passed
        result = api.execute(query="{number}")

        assert result

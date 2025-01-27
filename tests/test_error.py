from typing import Optional

import pytest

from graphql_api.mapper import GraphQLMetaKey

from graphql_api.api import GraphQLAPI


# noinspection PyPep8Naming,DuplicatedCode
class TestError:
    def test_raise(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def math(self) -> int:
                raise Exception("error 1")

        print("test")
        result = api.execute(
            """
            query {
                math
            }
        """
        )

        assert result.errors

    def test_nullable_raise(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def math(self) -> Optional[int]:
                raise Exception("error 1")

        print("test")
        result = api.execute(
            """
            query {
                math
            }
        """
        )

        assert result.data == {"math": None}

    def test_partial_raise(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def math(self, error: bool = True) -> Optional[int]:
                if error:
                    raise Exception("error 1")
                return 1

            @api.field
            def log(self, error: bool = True) -> int:
                if error:
                    raise Exception("error 2")
                return 1

        result = api.execute(
            """
            query {
                math
                log
            }
        """
        )

        assert result.errors
        assert not result.data

        result = api.execute(
            """
            query {
                math
                log(error: false)
            }
        """
        )

        assert result.errors
        assert result.data

    def test_error_protection(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field({GraphQLMetaKey.error_protection: False})
            def math_error(self, error: bool = True) -> Optional[int]:
                raise Exception("error 1")

        with pytest.raises(Exception, match="error 1"):
            api.execute(
                """
                query {
                    mathError
                }
            """
            )

    def test_api_error_protection(self):
        api = GraphQLAPI(error_protection=False)

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def math_error(self, error: bool = True) -> Optional[int]:
                raise Exception("error 1")

        with pytest.raises(Exception):
            api.execute(
                """
                query {
                    mathError
                }
            """
            )

    def test_execute_error_protection(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def math_error(self, error: bool = True) -> Optional[int]:
                raise Exception("error 1")

        with pytest.raises(Exception):
            api.execute(
                """
                query {
                    mathError
                }
            """,
                error_protection=False,
            )

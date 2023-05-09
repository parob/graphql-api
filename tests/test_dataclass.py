from dataclasses import dataclass
from typing import Optional
from graphql_api.api import GraphQLAPI


class TestDataclass:
    def test_dataclass(self):
        api = GraphQLAPI()

        # noinspection PyUnusedLocal
        @api.type(root=True)
        @dataclass
        class Root:
            hello_world: str = "hello world"
            hello_world_optional: Optional[str] = None

        executor = api.executor()

        test_query = """
            query HelloWorld {
                helloWorld
                helloWorldOptional
            }
        """

        result = executor.execute(test_query)

        expected = {"helloWorld": "hello world", "helloWorldOptional": None}
        assert not result.errors
        assert result.data == expected

    def test_dataclas_inheritance(self):
        api = GraphQLAPI()

        @dataclass
        class Person:
            name: str

        # noinspection PyUnusedLocal
        @api.type(root=True)
        @dataclass
        class Root:
            person: Person

        executor = api.executor(root_value=Root(person=Person(name="rob")))

        test_query = """
            query {
                person { name }
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data == {"person": {"name": "rob"}}

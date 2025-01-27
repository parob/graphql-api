from dataclasses import dataclass
from typing import Optional, List
from graphql_api.api import GraphQLAPI


class TestDataclass:
    def test_dataclass(self):
        api = GraphQLAPI()

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
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

    def test_dataclass_inheritance(self):
        api = GraphQLAPI()

        @dataclass
        class Entity:
            name: str
            embedding: List[float]

        @dataclass
        class Person(Entity):
            name: str
            embedding: List[float]

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        @dataclass
        class Root:
            person: Person

        executor = api.executor(
            root_value=Root(person=Person(name="rob", embedding=[1, 2]))
        )

        test_query = """
            query {
                person { name, embedding }
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data == {"person": {"name": "rob", "embedding": [1, 2]}}

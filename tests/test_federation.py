from typing import List, Optional, Union

from graphql import print_schema as graphql_print_schema

from graphql_api import GraphQLAPI, field, type

from graphql_api.federation.directives import key


class TestFederation:
    def test_federation_schema(self):

        names = {
            "1": "Rob",
            "2": "Tom"
        }

        @key(fields="id")
        @type
        class User:
            @classmethod
            def _resolve_reference(cls, reference):
                return User(id=reference["id"])

            def __init__(self, id: str):
                self._id = id
                self._name = names[id]

            @field
            def id(self) -> str:
                return self._id

            @field
            def name(self) -> str:
                return self._name

        @key(fields="name")
        @type
        class Food:
            def __init__(self, name: str):
                self._name = name

            @field
            def name(self) -> str:
                return self._name

        @type
        class Root:
            @field
            def users(self) -> List[User]:
                return [User(id="1"), User(id="2")]


        api = GraphQLAPI(root_type=Root, types=[Food], federation=True)
        schema, _ = api.graphql_schema()

        response = api.execute("{users{id,name}}")

        assert response.data == {
            "users": [{"id": "1", "name": "Rob"}, {"id": "2", "name": "Tom"}]
        }

        response = api.execute(
            '{_entities(representations:["{\\"__typename\\": \\"User\\",\\"id\\": '
            '\\"1\\"}"]) { ... on User { id name } } }'
        )
        assert response.data == {"_entities": [{"id": "1", "name": "Rob"}]}

        printed_schema = graphql_print_schema(schema)
        assert printed_schema

        assert "scalar FieldSet" in printed_schema
        assert "directive @tag" in printed_schema
        assert "directive @key" in printed_schema
        assert "scalar _Any" in printed_schema
        assert "_entities(representations: [_Any!]!): [_Entity]!" in printed_schema
        assert "_service: _Service!" in printed_schema
        assert "type_Service{sdl:String!}" in printed_schema.replace("\n", "").replace(
            " ", ""
        )

        response = api.execute("{_service{ sdl }}")

        sdl = response.data["_service"]["sdl"]

        assert sdl

        assert "scalar FieldSet" not in sdl
        assert "directive @tag" not in sdl
        assert "directive @key" not in sdl
        assert "scalar _Any" not in sdl
        assert "_entities(representations: [_Any!]!): [_Entity]!" in printed_schema
        assert "type_Service{sdl:String!}" not in sdl
        assert "extend schema" in sdl

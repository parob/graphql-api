from typing import List

from graphql import DirectiveLocation
from graphql import print_schema as graphql_print_schema

from graphql_api import GraphQLAPI, field, type
from graphql_api.directives import SchemaDirective
from graphql_api.federation.directives import key, link
from tests.test_federation_example import federation_example_api


class TestFederation:
    def test_federation_schema(self):
        names = {"1": "Rob", "2": "Tom"}

        custom = SchemaDirective(name="custom", locations=[DirectiveLocation.OBJECT])

        @custom
        @key(fields="name")  # type: ignore[reportIncompatibleMethodOverride]
        @key(fields="id")  # type: ignore[reportIncompatibleMethodOverride]
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

        @key(fields="name")  # type: ignore[reportIncompatibleMethodOverride]
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
        schema, _ = api.build_schema()

        link(
            **{
                "url": "https://myspecs.dev/myCustomDirective/v1.0",
                "import": ["@custom"],
            }
        )(schema)  # type: ignore[reportIncompatibleMethodOverride]

        response = api.execute("{users{id,name}}")

        assert response.data == {
            "users": [{"id": "1", "name": "Rob"}, {"id": "2", "name": "Tom"}]
        }

        response = api.execute(
            '{_entities(representations:["{\\"__typename\\": \\"User\\",\\"id\\": '
            '\\"1\\"}"]) { ... on User { id name } } }'
        )
        assert response.data == {"_entities": [{"id": "1", "name": "Rob"}]}

        response = api.execute(
            '{_entities(representations:["{\\"__typename\\": \\"Food\\",\\"name\\": '
            '\\"apple\\"}"]) { ... on Food { name } } }'
        )
        assert "not implemented" in str(response.errors)

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

        sdl = response.data["_service"]["sdl"]  # type: ignore[reportIncompatibleMethodOverride]

        assert sdl

        assert "scalar FieldSet" not in sdl
        assert "directive @tag" not in sdl
        assert "directive @key" not in sdl
        assert "scalar _Any" not in sdl
        assert "_entities(representations: [_Any!]!): [_Entity]!" not in sdl
        assert "_service: _Service!" not in sdl
        assert "type _Service" not in sdl
        assert "@link(url:" in sdl
        assert 'import: ["@key"])' in sdl

    def test_federation_example(self):
        api = federation_example_api()
        schema, meta = api.build_schema()

        response = api.execute(
            'query { _entities(representations: ["{ \\"__typename\\": \\"User\\", '
            '\\"email\\": \\"support@apollographql.com\\" }"]) '
            "{ ...on User { email name } } }"
        )

        assert response.data == {
            "_entities": [{"email": "support@apollographql.com", "name": "Jane Smith"}]
        }

        response = api.execute(
            'query { _entities(representations: ["{ \\"__typename\\": '
            '\\"DeprecatedProduct\\", \\"sku\\": \\"apollo-federation-v1\\", '
            '\\"package\\": \\"@apollo/federation-v1\\" }"]) '
            "{ ...on DeprecatedProduct { sku package reason } } }"
        )

        assert response.data == {
            "_entities": [
                {
                    "package": "@apollo/federation-v1",
                    "reason": "Migrate to Federation V2",
                    "sku": "apollo-federation-v1",
                }
            ]
        }

        printed_schema = graphql_print_schema(schema)
        assert printed_schema

        response = api.execute("{_service{ sdl }}")

        sdl = response.data["_service"]["sdl"]  # type: ignore[reportIncompatibleMethodOverride]
        assert sdl

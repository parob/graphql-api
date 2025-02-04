from typing import List, Optional

from graphql import print_schema as graphql_print_schema, DirectiveLocation, GraphQLID

from graphql_api import GraphQLAPI, field, type, AppliedDirective
from graphql_api.directives import SchemaDirective, deprecated

from graphql_api.federation.directives import key, link, composeDirective, provides, \
    tag, interfaceObject, external, requires, inaccessible, shareable, override
from graphql_api.schema import add_applied_directives


class TestFederation:
    def test_federation_schema(self):
        names = {"1": "Rob", "2": "Tom"}

        custom = SchemaDirective(
            name="custom",
            locations=[DirectiveLocation.OBJECT]
        )

        @custom
        @key(fields="name")
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
        schema, _ = api.build_schema()

        link(**{
            "url": "https://myspecs.dev/myCustomDirective/v1.0",
            "import": ["@custom"],
        })(schema)

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
        assert "_entities(representations: [_Any!]!): [_Entity]!" not in sdl
        assert "_service: _Service!" not in sdl
        assert "type _Service" not in sdl
        assert "@link(url:" in sdl
        assert 'import: ["@key"])' in sdl


    def test_federation_example(self):
        names = {"1": "Rob", "2": "Tom"}

        custom = SchemaDirective(
            name="custom",
            locations=[DirectiveLocation.OBJECT]
        )


        @type
        class ProductVariation:
            @field
            def id(self) -> GraphQLID:
                return "1"

        @type
        class CaseStudy:
            @field
            def case_number(self) -> GraphQLID:
                return "1"

            @field
            def description(self) -> Optional[str]:
                return ""

        @key(fields="study { caseNumber }")
        @type
        class ProductResearch:
            @field
            def study(self) -> CaseStudy:
                return CaseStudy()

            @field
            def outcome(self) -> Optional[str]:
                return ""


        @shareable
        @type
        class ProductDimension:
            @field
            def size(self) -> Optional[str]:
                return ""

            @field
            def weight(self) -> Optional[float]:
                return 0.0

            @inaccessible
            @field
            def unit(self) -> Optional[str]:
                return ""

        @key(fields="email")
        @type
        class User:
            @requires(fields="totalProductsCreated yearsOfEmployment")
            @field
            def average_products_created_per_year(self) -> Optional[int]:
                return 0

            @external
            @field
            def email(self) -> GraphQLID:
                return ""

            @override(from_="users")
            @field
            def name(self) -> Optional[str]:
                return ""

            @external
            @field
            def total_products_created(self) -> Optional[int]:
                return 0

            @external
            @field
            def years_of_employment(self) -> int:
                return 0

        @key(fields="sku package")
        @type
        class DeprecatedProduct:
            @field
            def sku(self) -> str:
                return ""

            @field
            def package(self) -> str:
                return ""

            @field
            def reason(self) -> Optional[str]:
                return ""

            @field
            def created_by(self) -> Optional[User]:
                return ""

        @interfaceObject
        @key(fields="id")
        @type
        class Inventory:
            @field
            def id(self) -> GraphQLID:
                return "1"

            @field
            def deprecated_products(self) -> List[DeprecatedProduct]:
                return []


        @custom
        @key(fields="id")
        @key(fields="sku package")
        @key(fields="sku variation { id }")
        @type
        class Product:
            @classmethod
            def _resolve_reference(cls, reference):
                return Product(id=reference["id"])

            @field
            def id(self) -> GraphQLID:
                return "1"

            @field
            def sku(self) -> Optional[str]:
                return ""

            @field
            def package(self) -> Optional[str]:
                return ""

            @field
            def variation(self) -> Optional[ProductVariation]:
                return ""

            @field
            def dimensions(self) -> Optional[ProductDimension]:
                return ""

            @provides(fields="totalProductsCreated")
            @field
            def created_by(self) -> Optional[User]:
                return ""

            @tag(name="internal")
            @field
            def notes(self) -> Optional[str]:
                return ""

            @field
            def research(self) -> List[ProductResearch]:
                return ""

        @type
        class Root:
            @field
            def product(self, id: GraphQLID) -> Product:
                return Product()

            @deprecated(reason="Use product query instead")
            @field
            def deprecated_product(self, sku: str, package: str) -> DeprecatedProduct:
                return DeprecatedProduct()


        api = GraphQLAPI(root_type=Root, federation=True)
        schema, _ = api.build_schema()

        link(**{
            "url": "https://myspecs.dev/myCustomDirective/v1.0",
            "import": ["@custom"],
        })(schema)

        composeDirective(name="@custom")(schema)

        response = api.execute("{users{id,name}}")

        # assert response.data == {
        #     "users": [{"id": "1", "name": "Rob"}, {"id": "2", "name": "Tom"}]
        # }

        printed_schema = graphql_print_schema(schema)
        assert printed_schema

        response = api.execute("{_service{ sdl }}")

        sdl = response.data["_service"]["sdl"]
        assert sdl

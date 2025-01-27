import enum
from typing import List, Optional, Union

import pytest
from graphql import DirectiveLocation, GraphQLDirective, GraphQLString, GraphQLArgument

from graphql_api import GraphQLAPI, type, field
from graphql_api.directives import LocatedSchemaDirective, SchemaDirective
from graphql_api.mapper import GraphQLTypeMapper
from graphql_api.print_directives import print_schema


class TestGraphQLDirectives:
    def test_operation_directive(self):
        class TestSchema:
            @field
            def test(self, a: int) -> int:
                return a + 1

        api = GraphQLAPI(root_type=TestSchema)

        executor = api.executor()

        test_query = """
            query Test($testBool: Boolean!) {
                test(a:1) @skip(if: $testBool)
            }
        """

        result = executor.execute(test_query, variables={"testBool": True})

        assert not result.errors
        assert result.data == {}

        result = executor.execute(test_query, variables={"testBool": False})

        assert not result.errors
        assert result.data == {"test": 2}

    def test_custom_directive(self):
        custom_directive_definition = GraphQLDirective(
            name="test1",
            locations=[
                DirectiveLocation.SCHEMA,
                DirectiveLocation.OBJECT,
                DirectiveLocation.FIELD_DEFINITION,
            ],
            args={"arg": GraphQLArgument(GraphQLString, description="arg description")},
            description="test description",
            is_repeatable=True,
        )

        @type
        class TestSchema:
            @field
            def test(self, a: int) -> int:
                return a + 1

        api = GraphQLAPI(root_type=TestSchema, directives=[custom_directive_definition])

        schema, _ = api.graphql_schema()
        printed_schema = print_schema(schema)

        assert "directive @test1" in printed_schema

    def test_schema_directive_object(self):
        key = SchemaDirective(
            name="key",
            locations=[DirectiveLocation.OBJECT],
            args={
                "fields": GraphQLArgument(GraphQLString, description="arg description")
            },
            description="Key Directive Description",
            is_repeatable=True,
        )

        @type(
            directives=[
                LocatedSchemaDirective(directive=key, args={"fields": "object_key"})
            ]
        )
        class Person:
            @field
            def name(self) -> str:
                return "rob"

        @key(fields="object_decorator_key")
        @type
        class TestSchema:
            @field
            def person(self) -> Person:
                return Person()

        api = GraphQLAPI(root_type=TestSchema)

        schema, _ = api.graphql_schema()
        printed_schema = print_schema(schema)

        assert "directive @key" in printed_schema
        assert "object_decorator_key" in printed_schema
        assert "object_key" in printed_schema

    def test_schema_directive_field(self):
        tag = SchemaDirective(
            name="tag",
            locations=[DirectiveLocation.FIELD_DEFINITION],
            args={
                "name": GraphQLArgument(
                    GraphQLString, description="tag name description"
                )
            },
            description="Tag Directive Description",
            is_repeatable=True,
        )

        @type
        class TestSchema:
            @field(
                directives=[
                    LocatedSchemaDirective(directive=tag, args={"name": "field_tag"})
                ]
            )
            def test(self, a: int) -> int:
                return a + 1

            @tag(name="field_decorator_tag")
            @field
            def test_2(self, a: int) -> int:
                return a + 1

            @tag(name="mutable_field_decorator_tag")
            @field(mutable=True)
            def add(self, a: int) -> int:
                return a + 1

        api = GraphQLAPI(root_type=TestSchema)

        schema, _ = api.graphql_schema()
        printed_schema = print_schema(schema)

        assert tag in self.get_directives(api.query_mapper)
        assert tag in self.get_directives(api.mutation_mapper)

        assert "directive @tag" in printed_schema
        assert "field_tag" in printed_schema
        assert "field_decorator_tag" in printed_schema

        assert "mutable_field_decorator_tag" in printed_schema

    @pytest.mark.skip(reason="Union directives not yet supported")
    def test_schema_directive_union(self):
        big = SchemaDirective(
            name="big",
            locations=[DirectiveLocation.UNION],
            description="Big Directive Description",
        )

        class Customer:
            @field
            def id(self) -> int:
                return 5

        class Owner:
            @field
            def name(self) -> str:
                return "rob"

        @type
        class Bank:
            @field
            def owner_or_customer(self) -> Optional[big(Union[Owner, Customer])]:
                return Customer()

        api = GraphQLAPI(root_type=Bank)

        schema, _ = api.graphql_schema()
        printed_schema = print_schema(schema)

        assert big in self.get_directives(api.query_mapper)

        assert "directive @big" in printed_schema

    def test_schema_directive_interface(self):
        interface_directive = SchemaDirective(
            name="interface_directive",
            locations=[DirectiveLocation.INTERFACE, DirectiveLocation.OBJECT],
            args={},
            description="Interface directive description",
            is_repeatable=True,
        )

        @interface_directive
        @type(interface=True)
        class Animal:
            @field
            def name(self) -> str:
                return "GenericAnimalName"

        class Dog(Animal):
            @field
            def name(self) -> str:
                return "Floppy"

        class Root:
            @field
            def animal(self) -> Animal:
                return Dog()

        api = GraphQLAPI(root_type=Root)

        schema, _ = api.graphql_schema()
        printed_schema = print_schema(schema)

        assert interface_directive in self.get_directives(api.query_mapper)
        assert interface_directive in self.get_directives(api.mutation_mapper)

        assert "directive @interface_directive" in printed_schema
        assert "Interface directive description" in printed_schema

    def test_schema_directive_enum(self):
        enum_directive = SchemaDirective(
            name="enum_directive",
            locations=[DirectiveLocation.ENUM],
            args={},
            description="Enum directive description",
            is_repeatable=True,
        )

        # enum_value_directive = SchemaDirective(
        #     name="enum_value_directive",
        #     locations=[DirectiveLocation.ENUM_VALUE],
        #     description="Enum value directive description",
        # )

        @enum_directive()
        class AnimalType(enum.Enum):
            dog = "dog"
            cat = "cat"

        @type
        class Root:
            @field
            def opposite(self, animal: AnimalType) -> AnimalType:
                assert isinstance(animal, AnimalType)

                if animal == AnimalType.dog:
                    return AnimalType.cat

                return AnimalType.dog

        api = GraphQLAPI(root_type=Root)

        schema, _ = api.graphql_schema()
        printed_schema = print_schema(schema)

        assert enum_directive in self.get_directives(api.query_mapper)

        assert "directive @enum_directive" in printed_schema
        assert "Enum directive description" in printed_schema

    def test_schema_directive_invalid_location(self):
        object_directive = SchemaDirective(
            name="object_directive", locations=[DirectiveLocation.OBJECT]
        )

        @object_directive
        @type(interface=True)
        class Animal:
            @field
            def name(self) -> str:
                return "GenericAnimalName"

        class Root:
            @field
            def animal(self) -> Animal:
                return Animal()

        api = GraphQLAPI(root_type=Root)

        with pytest.raises(TypeError, match="Directive '@object_directive' only supp"):
            schema, _ = api.graphql_schema()

    def test_multiple_schema_directives(self):
        key = SchemaDirective(
            name="key",
            locations=[DirectiveLocation.OBJECT],
            args={
                "fields": GraphQLArgument(GraphQLString, description="arg description")
            },
            description="Key Directive Description",
            is_repeatable=True,
        )

        tag = SchemaDirective(
            name="tag",
            locations=[DirectiveLocation.FIELD_DEFINITION],
            args={"name": GraphQLArgument(GraphQLString, description="tag name")},
            description="Tag Directive Description",
            is_repeatable=True,
        )

        @key(fields="schema_decorator_test")
        @type
        class TestSchema:
            @field(
                directives=[
                    LocatedSchemaDirective(
                        directive=tag, args={"name": "field_declarative_tag"}
                    )
                ]
            )
            def test(self, a: int) -> int:
                return a + 1

            @tag(name="field_decorator_tag")
            @field
            def test_2(self, a: int) -> int:
                return a + 1

            @tag
            @field
            def test_3(self, a: int) -> int:
                return a + 1

            @tag(name="mutable_field_decorator_tag")
            @field(mutable=True)
            def add(self, a: int) -> int:
                return a + 1

        api = GraphQLAPI(root_type=TestSchema)

        schema, _ = api.graphql_schema()
        printed_schema = print_schema(schema)

        assert tag in self.get_directives(api.query_mapper)
        assert tag in self.get_directives(api.mutation_mapper)

        assert "directive @key" in printed_schema
        assert "schema_decorator_test" in printed_schema
        assert "field_declarative_tag" in printed_schema
        assert "field_decorator_tag" in printed_schema

        schema_nw = printed_schema.replace(" ", "").replace("\n", "")

        assert "test3(a:Int!):Int!@tag}" in schema_nw

    @staticmethod
    def get_directives(mapper: GraphQLTypeMapper):
        query_schema_directives = mapper.schema_directives
        query_directives = []
        for _key, value, directives in query_schema_directives:
            query_directives: List[LocatedSchemaDirective] = [
                *query_directives,
                *directives,
            ]

        return [query_directive.directive for query_directive in query_directives]

    # def test_schema_directives_locations(self):
    #     key = SchemaDirective(
    #         name="key",
    #         locations=[DirectiveLocation.OBJECT],
    #         args={"fields": GraphQLArgument(
    #               GraphQLString,
    #               description="arg description"
    #         )},
    #         description="Key Directive Description",
    #         is_repeatable=True,
    #     )
    #
    #     # Type System Definitions
    #     SCHEMA = "schema"
    #     SCALAR = "scalar"
    #     OBJECT = "object"
    #     FIELD_DEFINITION = "field definition"
    #     ARGUMENT_DEFINITION = "argument definition"
    #     INTERFACE = "interface"
    #     UNION = "union"
    #     ENUM = "enum"
    #     ENUM_VALUE = "enum value"
    #     INPUT_OBJECT = "input object"
    #     INPUT_FIELD_DEFINITION = "input field definition"

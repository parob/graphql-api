# noinspection PyPep8Naming,DuplicatedCode
import dataclasses
from dataclasses import dataclass
from typing import Generic, List, Optional, Callable, TypeVar, Dict

from graphql import DirectiveLocation, GraphQLDirective, GraphQLString, GraphQLArgument, GraphQLSkipDirective, \
    GraphQLDirectiveKwargs, print_introspection_schema, print_schema

from graphql_api import GraphQLAPI, type, field
from graphql_api.directives import SchemaDirective


class TestGraphQLSchema:
    def test_decorators_no_schema(self):
        @type
        class ObjectNoSchema:
            @field
            def test_query_no_schema(self, a: int) -> int:
                pass

            @field(mutable=True)
            def test_mutation_no_schema(self, a: int) -> int:
                pass

        @type(abstract=True)
        class AbstractNoSchema:
            @field
            def test_abstract_query_no_schema(self, a: int) -> int:
                pass

            @field(mutable=True)
            def test_abstract_mutation_no_schema(self, a: int) -> int:
                pass

        @type(interface=True)
        class InterfaceNoSchema:
            @field
            def test_interface_query_no_schema(self, a: int) -> int:
                pass

            @field(mutable=True)
            def test_interface_mutation_no_schema(self, a: int) -> int:
                pass

        assert ObjectNoSchema._graphql
        assert ObjectNoSchema.test_query_no_schema._graphql
        assert ObjectNoSchema.test_mutation_no_schema._graphql

        assert AbstractNoSchema._graphql
        assert AbstractNoSchema.test_abstract_query_no_schema._graphql
        assert AbstractNoSchema.test_abstract_mutation_no_schema._graphql

        assert InterfaceNoSchema._graphql
        assert InterfaceNoSchema.test_interface_query_no_schema._graphql
        assert InterfaceNoSchema.test_interface_mutation_no_schema._graphql

    def test_decorators_schema(self):
        api_1 = GraphQLAPI()

        @api_1.type
        class ObjectSchema:
            @api_1.field
            def test_query_schema(self, a: int) -> int:
                pass

            @api_1.field(mutable=True)
            def test_mutation_schema(self, a: int) -> int:
                pass

        assert ObjectSchema._graphql
        assert ObjectSchema.test_query_schema._graphql
        assert ObjectSchema.test_mutation_schema._graphql

    def test_decorators_no_schema_meta(self):
        @type(meta={"test": "test"})
        class ObjectNoSchemaMeta:
            @field(meta={"test": "test"})
            def test_query_no_schema_meta(self, a: int) -> int:
                pass

            @field(meta={"test": "test"}, mutable=True)
            def test_mutation_no_schema_meta(self, a: int) -> int:
                pass

        # noinspection PyUnresolvedReferences
        assert ObjectNoSchemaMeta._graphql
        # noinspection PyUnresolvedReferences
        assert ObjectNoSchemaMeta.test_query_no_schema_meta._graphql
        # noinspection PyUnresolvedReferences
        assert ObjectNoSchemaMeta.test_mutation_no_schema_meta._graphql

    def test_decorators_schema_meta(self):
        api_1 = GraphQLAPI()

        @api_1.type(meta={"test1": "test2"}, root=True)
        class ObjectSchemaMeta:
            @api_1.field(meta={"test3": "test4"})
            def test_query_schema_meta(self, a: int) -> int:
                pass

            @api_1.field(meta={"test5": "test6"}, mutable=True)
            def test_mutation_schema_meta(self, a: int) -> int:
                pass

        assert ObjectSchemaMeta._graphql
        assert ObjectSchemaMeta.test_query_schema_meta._graphql
        assert ObjectSchemaMeta.test_mutation_schema_meta._graphql

        # api_1.set_root(ObjectSchemaMeta)
        schema = api_1.graphql_schema()

        assert schema

    def test_operation_directive(self):
        class TestSchema:

            @field
            def test(self, a: int) -> int:
                return a + 1

        api = GraphQLAPI(root=TestSchema)

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
            locations=[DirectiveLocation.SCHEMA, DirectiveLocation.OBJECT, DirectiveLocation.FIELD_DEFINITION],
            args={"arg": GraphQLArgument(GraphQLString, description="arg description")},
            description="test description",
            is_repeatable=True,
        )

        @type
        class TestSchema:

            @field
            def test(self, a: int) -> int:
                return a + 1

        api = GraphQLAPI(root=TestSchema, directives=[custom_directive_definition])

        schema, _ = api.graphql_schema()
        printed_schema = print_schema(schema)

        assert "directive @test1" in printed_schema

    def test_schema_directives(self):

        key_directive = GraphQLDirective(
            name="key",
            locations=[DirectiveLocation.OBJECT],
            args={"fields": GraphQLArgument(GraphQLString, description="arg description")},
            description="Key Directive Description",
            is_repeatable=True,
        )

        tag_directive = GraphQLDirective(
            name="tag",
            locations=[DirectiveLocation.FIELD_DEFINITION],
            args={"name": GraphQLArgument(GraphQLString, description="tag name")},
            description="Tag Directive Description",
            is_repeatable=True,
        )

        @type(directives=[SchemaDirective(directive=key_directive, args={"fields": "test"})])
        class TestSchema:

            @field(directives=[SchemaDirective(directive=tag_directive, args={"name": "test_tag"})])
            def test(self, a: int) -> int:
                return a + 1

        api = GraphQLAPI(root=TestSchema)

        schema, _ = api.graphql_schema()
        printed_schema = print_schema(schema)

        query_directives_map = api.query_mapper.schema_directives_map
        mutation_directives_map = api.mutation_mapper.schema_directives_map

        assert "directive @key" in printed_schema

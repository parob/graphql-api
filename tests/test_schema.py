# noinspection PyPep8Naming,DuplicatedCode
from graphql_api import GraphQLAPI, type, field


class TestGraphQL:

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

        assert ObjectNoSchema.graphql
        assert ObjectNoSchema.test_query_no_schema.graphql
        assert ObjectNoSchema.test_mutation_no_schema.graphql

        assert AbstractNoSchema.graphql
        assert AbstractNoSchema.test_abstract_query_no_schema.graphql
        assert AbstractNoSchema.test_abstract_mutation_no_schema.graphql

        assert InterfaceNoSchema.graphql
        assert InterfaceNoSchema.test_interface_query_no_schema.graphql
        assert InterfaceNoSchema.test_interface_mutation_no_schema.graphql

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

        assert ObjectSchema.graphql
        assert ObjectSchema.test_query_schema.graphql
        assert ObjectSchema.test_mutation_schema.graphql

    def test_decorators_no_schema_meta(self):

        @type(meta={"test": "test"})
        class ObjectNoSchemaMeta:

            @field(meta={"test": "test"})
            def test_query_no_schema_meta(self, a: int) -> int:
                pass

            @field(meta={"test": "test"}, mutable=True)
            def test_mutation_no_schema_meta(self, a: int) -> int:
                pass

        assert ObjectNoSchemaMeta.graphql
        assert ObjectNoSchemaMeta.test_query_no_schema_meta.graphql
        assert ObjectNoSchemaMeta.test_mutation_no_schema_meta.graphql

    def test_decorators_schema_meta(self):
        api_1 = GraphQLAPI()

        @api_1.type(meta={"test": "test"})
        class ObjectSchemaMeta:

            @api_1.field(meta={"test": "test"})
            def test_query_schema_meta(self, a: int) -> int:
                pass

            @api_1.field(meta={"test": "test"}, mutable=True)
            def test_mutation_schema_meta(self, a: int) -> int:
                pass

        assert ObjectSchemaMeta.graphql
        assert ObjectSchemaMeta.test_query_schema_meta.graphql
        assert ObjectSchemaMeta.test_mutation_schema_meta.graphql

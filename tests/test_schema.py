# noinspection PyPep8Naming,DuplicatedCode
from objectql import ObjectQLSchema


class TestGraphQL:

    def test_decorators_no_schema(self):

        @ObjectQLSchema.object
        class ObjectNoSchema:

            @ObjectQLSchema.query
            def test_query_no_schema(self, a: int) -> int:
                pass

            @ObjectQLSchema.mutation
            def test_mutation_no_schema(self, a: int) -> int:
                pass

        @ObjectQLSchema.abstract
        class AbstractNoSchema:

            @ObjectQLSchema.query
            def test_abstract_query_no_schema(self, a: int) -> int:
                pass

            @ObjectQLSchema.mutation
            def test_abstract_mutation_no_schema(self, a: int) -> int:
                pass

        @ObjectQLSchema.interface
        class InterfaceNoSchema:

            @ObjectQLSchema.query
            def test_interface_query_no_schema(self, a: int) -> int:
                pass

            @ObjectQLSchema.mutation
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
        api_1 = ObjectQLSchema()

        @api_1.object
        class ObjectSchema:

            @api_1.query
            def test_query_schema(self, a: int) -> int:
                pass

            @api_1.mutation
            def test_mutation_schema(self, a: int) -> int:
                pass

        assert ObjectSchema.graphql
        assert ObjectSchema.test_query_schema.graphql
        assert ObjectSchema.test_mutation_schema.graphql

    def test_decorators_no_schema_meta(self):

        @ObjectQLSchema.object(meta={"test": "test"})
        class ObjectNoSchemaMeta:

            @ObjectQLSchema.query(meta={"test": "test"})
            def test_query_no_schema_meta(self, a: int) -> int:
                pass

            @ObjectQLSchema.mutation(meta={"test": "test"})
            def test_mutation_no_schema_meta(self, a: int) -> int:
                pass

        assert ObjectNoSchemaMeta.graphql
        assert ObjectNoSchemaMeta.test_query_no_schema_meta.graphql
        assert ObjectNoSchemaMeta.test_mutation_no_schema_meta.graphql

    def test_decorators_schema_meta(self):
        api_1 = ObjectQLSchema()

        @api_1.object(meta={"test": "test"})
        class ObjectSchemaMeta:

            @api_1.query(meta={"test": "test"})
            def test_query_schema_meta(self, a: int) -> int:
                pass

            @api_1.mutation(meta={"test": "test"})
            def test_mutation_schema_meta(self, a: int) -> int:
                pass

        assert ObjectSchemaMeta.graphql
        assert ObjectSchemaMeta.test_query_schema_meta.graphql
        assert ObjectSchemaMeta.test_mutation_schema_meta.graphql

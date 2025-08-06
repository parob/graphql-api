import pytest
from unittest.mock import MagicMock

from graphql_api import GraphQLAPI, GraphQLRootTypeDelegate, field, type


class TestGraphQLSchema:
    def test_decorators_no_schema(self):
        @type
        class ObjectNoSchema:
            @field
            def test_query_no_schema(self, a: int) -> int:
                ...

            @field(mutable=True)
            def test_mutation_no_schema(self, a: int) -> int:
                ...

        @type(abstract=True)
        class AbstractNoSchema:
            @field
            def test_abstract_query_no_schema(self, a: int) -> int:
                ...

            @field(mutable=True)
            def test_abstract_mutation_no_schema(self, a: int) -> int:
                ...

        @type(interface=True)
        class InterfaceNoSchema:
            @field
            def test_interface_query_no_schema(self, a: int) -> int:
                ...

            @field(mutable=True)
            def test_interface_mutation_no_schema(self, a: int) -> int:
                ...

        # noinspection PyUnresolvedReferences
        assert ObjectNoSchema._graphql  # type: ignore[reportAttributeAccess]
        assert ObjectNoSchema.test_query_no_schema._graphql
        assert ObjectNoSchema.test_mutation_no_schema._graphql

        # noinspection PyUnresolvedReferences
        assert AbstractNoSchema._graphql  # type: ignore[reportAttributeAccess]
        assert AbstractNoSchema.test_abstract_query_no_schema._graphql
        assert AbstractNoSchema.test_abstract_mutation_no_schema._graphql

        # noinspection PyUnresolvedReferences
        assert InterfaceNoSchema._graphql  # type: ignore[reportAttributeAccess]
        assert InterfaceNoSchema.test_interface_query_no_schema._graphql
        assert InterfaceNoSchema.test_interface_mutation_no_schema._graphql

    def test_decorators_schema(self):
        api_1 = GraphQLAPI()

        @api_1.type
        class ObjectSchema:
            @api_1.field
            def test_query_schema(self, a: int) -> int:
                ...

            @api_1.field(mutable=True)
            def test_mutation_schema(self, a: int) -> int:
                ...

        # noinspection PyUnresolvedReferences
        assert ObjectSchema._graphql  # type: ignore[reportAttributeAccess]
        assert ObjectSchema.test_query_schema._graphql
        assert ObjectSchema.test_mutation_schema._graphql

    def test_decorators_no_schema_meta(self):
        @type(meta={"test": "test"})
        class ObjectNoSchemaMeta:
            @field(meta={"test": "test"})
            def test_query_no_schema_meta(self, a: int) -> int:
                ...

            @field(meta={"test": "test"}, mutable=True)
            def test_mutation_no_schema_meta(self, a: int) -> int:
                ...

        # noinspection PyUnresolvedReferences
        assert ObjectNoSchemaMeta._graphql  # type: ignore[reportAttributeAccess]
        assert ObjectNoSchemaMeta.test_query_no_schema_meta._graphql
        assert ObjectNoSchemaMeta.test_mutation_no_schema_meta._graphql

    def test_decorators_schema_meta(self):
        api_1 = GraphQLAPI()

        @api_1.type(meta={"test1": "test2"}, is_root_type=True)
        class ObjectSchemaMeta:
            @api_1.field(meta={"test3": "test4"})
            def test_query_schema_meta(self, a: int) -> int:
                ...

            @api_1.field(meta={"test5": "test6"}, mutable=True)
            def test_mutation_schema_meta(self, a: int) -> int:
                ...

        # noinspection PyUnresolvedReferences
        assert ObjectSchemaMeta._graphql  # type: ignore[reportAttributeAccess]
        assert ObjectSchemaMeta.test_query_schema_meta._graphql
        assert ObjectSchemaMeta.test_mutation_schema_meta._graphql

        schema, _ = api_1.build_schema()

        assert schema is not None
        assert schema.query_type is not None

    def test_schema_with_no_root_type(self):
        """
        Tests that a schema can be built with no root type, resulting
        in a placeholder query type.
        """
        api = GraphQLAPI()
        schema, _ = api.build_schema()

        assert schema is not None
        assert schema.query_type is not None
        assert schema.query_type.name == "PlaceholderQuery"
        assert "placeholder" in schema.query_type.fields
        assert schema.mutation_type is None

    def test_root_type_delegate_is_called(self):
        """
        Tests that for a root_type that inherits from GraphQLRootTypeDelegate,
        the validate_graphql_schema method is called when building the schema.
        """

        class RootWithDelegate(GraphQLRootTypeDelegate):
            @field
            def a_query(self) -> str:
                return "test"

        # Mock the class method
        RootWithDelegate.validate_graphql_schema = MagicMock(
            side_effect=lambda schema: schema
        )

        api = GraphQLAPI(root_type=RootWithDelegate)
        schema, _ = api.build_schema()

        assert schema is not None
        RootWithDelegate.validate_graphql_schema.assert_called_once()

        # Check that it was called with the schema
        schema_arg = RootWithDelegate.validate_graphql_schema.call_args[0][0]
        assert schema_arg is schema

    def test_interface_cannot_be_root_type(self):
        """
        Tests that a TypeError is raised when trying to set an interface
        as the root type of a schema.
        """
        with pytest.raises(
            TypeError, match="Cannot set .* of type 'interface' as a root."
        ):
            api = GraphQLAPI()

            @api.type(is_root_type=True, interface=True)
            class MyInterface:
                pass

    def test_abstract_cannot_be_root_type(self):
        """
        Tests that a TypeError is raised when trying to set an abstract type
        as the root type of a schema.
        """
        with pytest.raises(
            TypeError, match="Cannot set .* of type 'abstract' as a root."
        ):
            api = GraphQLAPI()

            @api.type(is_root_type=True, abstract=True)
            class MyAbstract:
                pass

"""
Test all code examples from the getting-started.md documentation
"""
import pytest
from graphql_api.api import GraphQLAPI


class TestGettingStartedExamples:

    def test_basic_hello_world_api(self):
        """Test the basic Hello World API from getting-started.md"""
        # Example 1: Basic API initialization and root query
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            """
            The root query for our amazing API.
            """
            @api.field
            def hello(self, name: str = "World") -> str:
                """
                Returns a classic greeting. The docstring will be used as the field's description in the schema.
                """
                return f"Hello, {name}!"

        # Test the query execution
        graphql_query = """
            query Greetings {
                hello(name: "Developer")
            }
        """

        result = api.execute(graphql_query)
        assert not result.errors
        assert result.data == {'hello': 'Hello, Developer!'}

    def test_hello_world_with_default_parameter(self):
        """Test hello world with default parameter"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def hello(self, name: str = "World") -> str:
                return f"Hello, {name}!"

        # Test with default parameter
        graphql_query = """
            query Greetings {
                hello
            }
        """

        result = api.execute(graphql_query)
        assert not result.errors
        assert result.data == {'hello': 'Hello, World!'}

    def test_introspection_query(self):
        """Test the introspection query example from getting-started.md"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def hello(self, name: str = "World") -> str:
                return f"Hello, {name}!"

        # Test introspection
        introspection_query = """
            query IntrospectionQuery {
                __schema {
                    types {
                        name
                        kind
                    }
                }
            }
        """

        result = api.execute(introspection_query)
        assert not result.errors
        assert result.data is not None

        # Check that we have the expected types
        types = result.data['__schema']['types']
        type_names = [t['name'] for t in types]

        # Should include standard GraphQL types and our custom Query type
        assert 'Query' in type_names
        assert 'String' in type_names
        assert 'Boolean' in type_names
        # Note: Int type only appears if actually used in the schema

    def test_schema_description_from_docstring(self):
        """Test that docstrings are properly used as descriptions"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            """
            The root query for our amazing API.
            """
            @api.field
            def hello(self, name: str = "World") -> str:
                """
                Returns a classic greeting. The docstring will be used as the field's description in the schema.
                """
                return f"Hello, {name}!"

        # Get the schema and check descriptions
        executor = api.executor()
        schema = executor.schema

        # Check query type description
        query_type = schema.query_type
        assert query_type.description == "The root query for our amazing API."

        # Check field description
        hello_field = query_type.fields['hello']
        assert "Returns a classic greeting" in hello_field.description

    def test_type_hints_generate_schema(self):
        """Test that Python type hints properly generate GraphQL schema types"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def hello(self, name: str = "World") -> str:
                return f"Hello, {name}!"

        executor = api.executor()
        schema = executor.schema

        # Check that the field has the correct argument type
        hello_field = schema.query_type.fields['hello']
        name_arg = hello_field.args['name']

        # Should be a String with default value (not non-null due to default)
        assert str(name_arg.type) == 'String'
        assert name_arg.default_value == "World"

        # Check return type
        assert str(hello_field.type) == 'String!'
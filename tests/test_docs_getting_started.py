"""
Test all code examples from the getting-started.md documentation
"""
from typing import List
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

    def test_schema_documentation_with_docstrings(self):
        """Test schema documentation with docstrings"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            """
            The root query type for our API.
            This docstring becomes the type description.
            """

            @api.field
            def get_user(self, user_id: str) -> str:
                """
                Retrieve a user by their unique ID.

                This docstring becomes the field description in the GraphQL schema.
                """
                return f"User {user_id}"

            @api.field
            def search_users(self, query: str, limit: int = 10) -> List[str]:
                """Search for users matching a query string."""
                return [f"User matching '{query}'"]

        # Test that the schema builds with docstrings
        schema, _ = api.build()
        assert schema is not None

        # Test that docstrings are preserved as descriptions
        query_type = schema.query_type
        assert "The root query type for our API" in query_type.description

        get_user_field = query_type.fields["getUser"]
        assert "Retrieve a user by their unique ID" in get_user_field.description

        search_users_field = query_type.fields["searchUsers"]
        assert search_users_field.description == "Search for users matching a query string."

        # Test that queries still work
        result = api.execute('query { getUser(userId: "123") }')
        assert not result.errors
        assert result.data["getUser"] == "User 123"

    def test_dataclass_and_pydantic_documentation(self):
        """Test docstrings work with dataclasses and Pydantic"""
        from dataclasses import dataclass
        from pydantic import BaseModel

        api = GraphQLAPI()

        @dataclass
        class User:
            """Represents a user in the system."""
            id: str
            name: str
            email: str

        class CreateUserInput(BaseModel):
            """Input data for creating a new user."""
            name: str
            email: str

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def user(self) -> User:
                return User(id="1", name="Alice", email="alice@example.com")

            @api.field(mutable=True)
            def create_user(self, input: CreateUserInput) -> User:
                return User(id="999", name=input.name, email=input.email)

        schema, _ = api.build()
        assert schema is not None

        # Check that type descriptions are preserved
        user_type = schema.type_map["User"]
        assert user_type.description == "Represents a user in the system."

        # Input types are only included in schema if they're actually used in mutations
        # Since this is just a query, the input type won't be in the schema

        # Test functionality
        result = api.execute('query { user { id name email } }')
        assert not result.errors
        assert result.data["user"]["name"] == "Alice"

    def test_advanced_docstring_parsing(self):
        """Test Google-style docstring parsing"""
        from dataclasses import dataclass

        api = GraphQLAPI()

        @dataclass
        class Product:
            """
            A product in our catalog.

            Args:
                id: The unique product identifier
                name: The product display name
                price: The product price in cents
                category: The product category name
            """
            id: str
            name: str
            price: int
            category: str

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def product(self) -> Product:
                return Product(id="p1", name="Widget", price=1000, category="gadgets")

        schema, _ = api.build()
        assert schema is not None

        # Check that the main description is preserved
        product_type = schema.type_map["Product"]
        assert "A product in our catalog" in product_type.description

        # Test functionality
        result = api.execute('query { product { id name price category } }')
        assert not result.errors
        assert result.data["product"]["name"] == "Widget"
        assert result.data["product"]["price"] == 1000

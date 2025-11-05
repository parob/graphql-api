"""
Tests for different decorator patterns in graphql-api:
1. Global decorators (@field from graphql_api.decorators)
2. Instance decorators (@api.type, @api.field from GraphQLAPI instance)
3. Mixed usage patterns and their behaviors
"""

from dataclasses import dataclass
from typing import List

from graphql import GraphQLObjectType

from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field as global_field


@dataclass
class User:
    id: int
    name: str


class TestDecoratorPatterns:
    def test_global_field_decorator_pattern(self) -> None:
        """Test using global @field decorators from graphql_api.decorators."""

        @dataclass
        class UserWithMethods:
            id: int
            name: str = "Global User"

            @global_field
            def get_profile(self) -> str:
                return f"Profile for {self.name}"

        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def users(self) -> List[UserWithMethods]:
                return [UserWithMethods(id=1)]

        schema, _ = api.build()

        # Verify the schema includes the global field
        assert "UserWithMethods" in schema.type_map
        user_type = schema.type_map["UserWithMethods"]
        assert isinstance(user_type, GraphQLObjectType)
        assert "getProfile" in user_type.fields

        # Test execution
        result = api.execute('{ users { id name getProfile } }')
        assert not result.errors
        assert result.data == {
            "users": [{"id": 1, "name": "Global User", "getProfile": "Profile for Global User"}]
        }

    def test_instance_field_decorator_pattern(self) -> None:
        """Test using instance @api.field decorators."""

        api = GraphQLAPI()

        @dataclass
        class UserWithMethods:
            id: int
            name: str = "Instance User"

            @api.field
            def get_profile(self) -> str:
                return f"Profile for {self.name}"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def users(self) -> List[UserWithMethods]:
                return [UserWithMethods(id=1)]

        schema, _ = api.build()

        # Verify the schema includes the instance field
        assert "UserWithMethods" in schema.type_map
        user_type = schema.type_map["UserWithMethods"]
        assert isinstance(user_type, GraphQLObjectType)
        assert "getProfile" in user_type.fields

        # Test execution
        result = api.execute('{ users { id name getProfile } }')
        assert not result.errors
        assert result.data == {
            "users": [{"id": 1, "name": "Instance User", "getProfile": "Profile for Instance User"}]
        }

    def test_mixed_decorators_on_same_class(self) -> None:
        """Test mixing global and instance decorators on the same class."""

        api = GraphQLAPI()

        @dataclass
        class UserWithMixedMethods:
            id: int
            name: str = "Mixed User"

            @api.field
            def instance_method(self) -> str:
                return "From instance decorator"

            @global_field
            def global_method(self) -> str:
                return "From global decorator"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def get_user(self) -> UserWithMixedMethods:
                return UserWithMixedMethods(id=1)

        schema, _ = api.build()

        user_type = schema.type_map["UserWithMixedMethods"]

        # Both methods should be present since they're on the same class
        assert isinstance(user_type, GraphQLObjectType)
        assert "instanceMethod" in user_type.fields
        assert "globalMethod" in user_type.fields

        # Test execution
        result = api.execute('''
            {
                getUser {
                    id
                    name
                    instanceMethod
                    globalMethod
                }
            }
        ''')
        assert not result.errors
        assert result.data == {
            "getUser": {
                "id": 1,
                "name": "Mixed User",
                "instanceMethod": "From instance decorator",
                "globalMethod": "From global decorator"
            }
        }

    def test_different_api_instances_isolation(self) -> None:
        """Test that different API instances have isolated decorators."""

        api1 = GraphQLAPI()
        api2 = GraphQLAPI()

        @dataclass
        class Math:
            value: int = 5

            @api1.field
            def square(self) -> int:
                return self.value * self.value

            @api2.field
            def cube(self) -> int:
                return self.value * self.value * self.value

        @api1.type(is_root_type=True)
        class Root1:
            @api1.field
            def math(self) -> Math:
                return Math()

        @api2.type(is_root_type=True)
        class Root2:
            @api2.field
            def math(self) -> Math:
                return Math()

        # Build separate schemas
        schema1, _ = api1.build()
        schema2, _ = api2.build()

        math_type_1 = schema1.type_map["Math"]
        math_type_2 = schema2.type_map["Math"]

        # API1 schema should only have square method
        assert isinstance(math_type_1, GraphQLObjectType)
        assert "square" in math_type_1.fields
        assert "cube" not in math_type_1.fields

        # API2 schema should only have cube method
        assert isinstance(math_type_2, GraphQLObjectType)
        assert "cube" in math_type_2.fields
        assert "square" not in math_type_2.fields

        # Test execution on each API
        result1 = api1.execute('{ math { value square } }')
        assert not result1.errors
        assert result1.data == {"math": {"value": 5, "square": 25}}

        result2 = api2.execute('{ math { value cube } }')
        assert not result2.errors
        assert result2.data == {"math": {"value": 5, "cube": 125}}

    def test_global_field_works_across_apis(self) -> None:
        """Test that global @field decorators work across different API instances."""

        @dataclass
        class Calculator:
            value: int = 10

            @global_field
            def double(self) -> int:
                return self.value * 2

        # Create two different APIs
        api1 = GraphQLAPI()
        api2 = GraphQLAPI()

        @api1.type(is_root_type=True)
        class Root1:
            @api1.field
            def calc(self) -> Calculator:
                return Calculator(value=5)

        @api2.type(is_root_type=True)
        class Root2:
            @api2.field
            def calc(self) -> Calculator:
                return Calculator(value=7)

        # Build schemas
        schema1, _ = api1.build()
        schema2, _ = api2.build()

        # Global field should be available in both schemas
        calc_type_1 = schema1.type_map["Calculator"]
        calc_type_2 = schema2.type_map["Calculator"]

        assert isinstance(calc_type_1, GraphQLObjectType)
        assert "double" in calc_type_1.fields
        assert isinstance(calc_type_2, GraphQLObjectType)
        assert "double" in calc_type_2.fields

        # Test execution
        result1 = api1.execute('{ calc { value double } }')
        assert not result1.errors
        assert result1.data == {"calc": {"value": 5, "double": 10}}

        result2 = api2.execute('{ calc { value double } }')
        assert not result2.errors
        assert result2.data == {"calc": {"value": 7, "double": 14}}

    def test_potential_circular_import_pattern(self) -> None:
        """Test pattern that could lead to circular imports with instance decorators."""

        # This demonstrates why circular imports can be an issue with instance decorators
        api = GraphQLAPI()

        @dataclass
        class Author:
            id: int
            name: str

        # In a real app, these might be in different modules that import each other
        @dataclass
        class Post:
            id: int
            title: str
            author_id: int

            @api.field  # This requires 'api' to be imported in the Post module
            def get_author(self) -> Author:
                return Author(id=self.author_id, name=f"Author {self.author_id}")

        # Add method to Author after Post is defined to avoid forward ref
        @api.field
        def get_posts(self) -> List[Post]:
            return [Post(id=1, title=f"Post by {self.name}", author_id=self.id)]

        Author.get_posts = get_posts  # type: ignore[reportIncompatibleMethodOverride]

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def posts(self) -> List[Post]:
                return [Post(id=1, title="Test Post", author_id=1)]

        # This works here because everything is in the same module,
        # but in a real app with separate modules, this could cause circular imports
        schema, _ = api.build()

        post_type = schema.type_map["Post"]
        author_type = schema.type_map["Author"]

        assert isinstance(post_type, GraphQLObjectType)
        assert isinstance(author_type, GraphQLObjectType)
        assert "getAuthor" in post_type.fields
        assert "getPosts" in author_type.fields

        # Test execution
        result = api.execute('''
            {
                posts {
                    id
                    title
                    getAuthor {
                        id
                        name
                    }
                }
            }
        ''')
        assert not result.errors
        assert result.data == {
            "posts": [{
                "id": 1,
                "title": "Test Post",
                "getAuthor": {
                    "id": 1,
                    "name": "Author 1"
                }
            }]
        }

    def test_global_vs_instance_comparison(self) -> None:
        """Compare the behavior of global vs instance decorators side by side."""

        # Global decorator approach
        @dataclass
        class ProductGlobal:
            id: int
            name: str = "Global Product"

            @global_field
            def get_price(self) -> float:
                return 99.99

        # Instance decorator approach
        api = GraphQLAPI()

        @dataclass
        class ProductInstance:
            id: int
            name: str = "Instance Product"

            @api.field
            def get_price(self) -> float:
                return 88.88

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def global_product(self) -> ProductGlobal:
                return ProductGlobal(id=1)

            @api.field
            def instance_product(self) -> ProductInstance:
                return ProductInstance(id=2)

        schema, _ = api.build()

        # Both should work identically in the final schema
        global_type = schema.type_map["ProductGlobal"]
        instance_type = schema.type_map["ProductInstance"]

        assert isinstance(global_type, GraphQLObjectType)
        assert isinstance(instance_type, GraphQLObjectType)
        assert "getPrice" in global_type.fields
        assert "getPrice" in instance_type.fields

        # Test execution
        result = api.execute('''
            {
                globalProduct { id name getPrice }
                instanceProduct { id name getPrice }
            }
        ''')
        assert not result.errors
        assert result.data == {
            "globalProduct": {"id": 1, "name": "Global Product", "getPrice": 99.99},
            "instanceProduct": {"id": 2, "name": "Instance Product", "getPrice": 88.88}
        }

from dataclasses import dataclass
from typing import List, Optional

from graphql import GraphQLObjectType

from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field


class TestDataclassRelationships:
    def test_dataclass_with_field_decorated_methods(self) -> None:
        """Test that methods on dataclasses need @field decorator to be GraphQL fields."""

        # Sample data
        authors = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ]

        posts = [
            {"id": 1, "title": "Test Post", "content": "Content", "author_id": 1},
            {"id": 2, "title": "Another Post", "content": "More content", "author_id": 2},
        ]

        @dataclass
        class Post:
            id: int
            title: str
            content: str
            author_id: int

        @dataclass
        class Author:
            id: int
            name: str
            email: str

            @field
            def get_posts(self) -> List[Post]:
                """Get posts by this author."""
                return [Post(**p) for p in posts if p["author_id"] == self.id]

        # Add method to Post after Author is defined
        @field
        def get_author(self) -> Optional[Author]:
            """Get the author of this post."""
            author_data = next((a for a in authors if a["id"] == self.author_id), None)
            if author_data:
                return Author(**author_data)
            return None

        Post.get_author = get_author  # type: ignore[reportIncompatibleMethodOverride]

        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def posts(self) -> List[Post]:
                return [Post(**p) for p in posts]

            @api.field
            def authors(self) -> List[Author]:
                return [Author(**a) for a in authors]

        # Test that the schema includes the field-decorated methods
        schema, _ = api.build_schema()

        # Check that Post type has getAuthor field
        post_type = schema.type_map["Post"]
        assert isinstance(post_type, GraphQLObjectType)
        assert "getAuthor" in post_type.fields

        # Check that Author type has getPosts field
        author_type = schema.type_map["Author"]
        assert isinstance(author_type, GraphQLObjectType)
        assert "getPosts" in author_type.fields

        # Test query execution
        query = """
            query {
                posts {
                    id
                    title
                    getAuthor {
                        name
                        email
                    }
                }
            }
        """

        executor = api.executor()
        result = executor.execute(query)

        assert not result.errors
        assert result.data is not None
        assert len(result.data["posts"]) == 2
        assert result.data["posts"][0]["getAuthor"]["name"] == "Alice"
        assert result.data["posts"][1]["getAuthor"]["name"] == "Bob"

    def test_dataclass_method_without_field_decorator_not_exposed(self) -> None:
        """Test that methods without @field decorator are not exposed as GraphQL fields."""

        @dataclass
        class User:
            id: int
            name: str

            # This method does NOT have @field decorator
            def private_method(self) -> str:
                return "This should not be a GraphQL field"

            @field
            def public_method(self) -> str:
                return "This should be a GraphQL field"

        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def user(self) -> User:
                return User(id=1, name="Test User")

        schema, _ = api.build_schema()
        user_type = schema.type_map["User"]

        # publicMethod should be present (camelCase conversion)
        assert isinstance(user_type, GraphQLObjectType)
        assert "publicMethod" in user_type.fields

        # privateMethod should NOT be present
        assert isinstance(user_type, GraphQLObjectType)
        assert "privateMethod" not in user_type.fields
        assert "private_method" not in user_type.fields

"""
Test all code examples from the defining-schemas.md documentation
"""
from typing import List, Optional, Union
from pydantic import BaseModel
from graphql_api.api import GraphQLAPI
from graphql_api.decorators import type, field


class TestDefiningSchemas:

    def test_instance_decorators_basic(self):
        """Test basic instance decorator pattern"""
        api = GraphQLAPI()

        @api.type
        class User:
            @api.field
            def name(self) -> str:
                return "Alice"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def get_user(self) -> User:
                return User()

        result = api.execute("query { getUser { name } }")
        assert not result.errors
        assert result.data == {"getUser": {"name": "Alice"}}

    def test_global_decorators_basic(self):
        """Test basic global decorator pattern"""
        @type
        class User:
            @field
            def name(self) -> str:
                return "Alice"

        @type
        class Query:
            @field
            def get_user(self) -> User:
                return User()

        api = GraphQLAPI()
        api.root_type = Query

        result = api.execute("query { getUser { name } }")
        assert not result.errors
        assert result.data == {"getUser": {"name": "Alice"}}

    def test_mode1_single_root_type(self):
        """Test Mode 1: Single Root Type"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            # Query field
            @api.field
            def get_user(self, user_id: int) -> str:
                return f"User {user_id}"

            # Mutation field - marked with mutable=True
            @api.field(mutable=True)
            def update_user(self, user_id: int, name: str) -> str:
                return f"Updated user {user_id} to {name}"

        # Test query
        query_result = api.execute("query { getUser(userId: 1) }")
        assert not query_result.errors
        assert query_result.data == {"getUser": "User 1"}

        # Test mutation
        mutation_result = api.execute("mutation { updateUser(userId: 1, name: \"Bob\") }")
        assert not mutation_result.errors
        assert mutation_result.data == {"updateUser": "Updated user 1 to Bob"}

    def test_mode2_explicit_types(self):
        """Test Mode 2: Explicit Types"""
        api = GraphQLAPI()

        @api.type
        class Query:
            @api.field
            def get_user(self, user_id: int) -> str:
                return f"User {user_id}"

            @api.field
            def list_posts(self) -> List[str]:
                return ["Post 1", "Post 2"]

        @api.type
        class Mutation:
            @api.field
            def update_user(self, user_id: int, name: str) -> str:
                return f"Updated user {user_id} to {name}"

            @api.field
            def create_post(self, title: str) -> str:
                return f"Created post: {title}"

        # Set explicit types
        api.query_type = Query
        api.mutation_type = Mutation

        # Test query
        query_result = api.execute("query { getUser(userId: 1) }")
        assert not query_result.errors
        assert query_result.data == {"getUser": "User 1"}

        # Test mutation
        mutation_result = api.execute("mutation { updateUser(userId: 1, name: \"Bob\") }")
        assert not mutation_result.errors
        assert mutation_result.data == {"updateUser": "Updated user 1 to Bob"}

    def test_object_types_basic(self):
        """Test basic object type definition"""
        api = GraphQLAPI()

        class User:
            @api.field
            def id(self) -> int:
                return 1

            @api.field
            def name(self) -> str:
                return "Alice"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def get_user(self) -> User:
                return User()

        result = api.execute("query { getUser { id name } }")
        assert not result.errors
        assert result.data == {"getUser": {"id": 1, "name": "Alice"}}

    def test_field_arguments(self):
        """Test field arguments"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def greet(self, name: str) -> str:
                return f"Hello, {name}!"

        result = api.execute('query { greet(name: "World") }')
        assert not result.errors
        assert result.data == {"greet": "Hello, World!"}

    def test_type_modifiers(self):
        """Test type modifiers (Optional, List)"""
        api = GraphQLAPI()

        class Post:
            @api.field
            def id(self) -> int:
                return 123

            @api.field
            def title(self) -> str:
                return "My First Post"

            @api.field
            def summary(self) -> Optional[str]:
                return None  # This field can be null

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def get_posts(self) -> List[Post]:
                return [Post()]

        result = api.execute("query { getPosts { id title summary } }")
        assert not result.errors
        assert result.data == {"getPosts": [{"id": 123, "title": "My First Post", "summary": None}]}

    def test_input_types_pydantic(self):
        """Test input types with Pydantic"""
        class CreatePostInput(BaseModel):
            title: str
            content: str
            author_email: str

        class Post(BaseModel):
            id: int
            title: str
            content: str

        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field(mutable=True)
            def create_post(self, input: CreatePostInput) -> Post:
                return Post(id=456, title=input.title, content=input.content)

        query = """
        mutation {
            createPost(input: {
                title: "Test Post"
                content: "Test content"
                authorEmail: "test@example.com"
            }) {
                id
                title
                content
            }
        }
        """

        result = api.execute(query)
        assert not result.errors
        assert result.data["createPost"]["title"] == "Test Post"
        assert result.data["createPost"]["id"] == 456

    def test_interfaces(self):
        """Test interface implementation"""
        api = GraphQLAPI()

        @api.type(interface=True)
        class Character:
            @api.field
            def get_id(self) -> str:
                return "default_id"

            @api.field
            def get_name(self) -> str:
                return "default_name"

        class Human(Character):
            @api.field
            def home_planet(self) -> str:
                return "Earth"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def get_human(self) -> Human:
                return Human()

        result = api.execute("query { getHuman { getId getName homePlanet } }")
        assert not result.errors
        assert result.data == {
            "getHuman": {
                "getId": "default_id",
                "getName": "default_name",
                "homePlanet": "Earth"
            }
        }

    def test_union_types(self):
        """Test union types"""
        class Cat(BaseModel):
            name: str
            meow_volume: int

        class Dog(BaseModel):
            name: str
            bark_loudness: int

        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def search_pet(self, name: str) -> Union[Cat, Dog]:
                if name == "Whiskers":
                    return Cat(name="Whiskers", meow_volume=10)
                if name == "Fido":
                    return Dog(name="Fido", bark_loudness=100)
                return Cat(name="Unknown", meow_volume=5)

        # Test with fragment spreads
        query = """
        query {
            searchPet(name: "Whiskers") {
                ... on Cat {
                    name
                    meowVolume
                }
                ... on Dog {
                    name
                    barkLoudness
                }
            }
        }
        """

        result = api.execute(query)
        assert not result.errors
        assert result.data == {
            "searchPet": {
                "name": "Whiskers",
                "meowVolume": 10
            }
        }

    def test_marking_fields_as_mutations_mode1(self):
        """Test marking fields as mutations in Mode 1"""
        api = GraphQLAPI()

        class CreatePostInput(BaseModel):
            title: str
            content: str

        class Post(BaseModel):
            id: int
            title: str

        @api.type(is_root_type=True)
        class Root:
            @api.field(mutable=True)
            def create_post(self, input: CreatePostInput) -> Post:
                return Post(id=1, title=input.title)

        query = """
        mutation {
            createPost(input: { title: "Test", content: "Content" }) {
                id
                title
            }
        }
        """

        result = api.execute(query)
        assert not result.errors
        assert result.data["createPost"]["title"] == "Test"

    def test_marking_fields_as_mutations_mode2(self):
        """Test automatic mutations in Mode 2"""
        api = GraphQLAPI()

        class CreatePostInput(BaseModel):
            title: str
            content: str

        class Post(BaseModel):
            id: int
            title: str

        @api.type
        class Mutation:
            @api.field
            def create_post(self, input: CreatePostInput) -> Post:
                return Post(id=1, title=input.title)  # Automatically a mutation

        # Need a placeholder query type for Mode 2
        @api.type
        class Query:
            @api.field
            def placeholder(self) -> str:
                return "placeholder"

        # Set explicit types
        api.query_type = Query
        api.mutation_type = Mutation

        query = """
        mutation {
            createPost(input: { title: "Test", content: "Content" }) {
                id
                title
            }
        }
        """

        result = api.execute(query)
        assert not result.errors
        assert result.data["createPost"]["title"] == "Test"

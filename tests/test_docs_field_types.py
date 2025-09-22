"""
Test all code examples from the field-types.md documentation
"""
from typing import List, Optional, Union
from datetime import date, datetime
from uuid import UUID
from dataclasses import dataclass
from pydantic import BaseModel
from graphql import GraphQLID, GraphQLScalarType, StringValueNode
from graphql_api.api import GraphQLAPI
from graphql_api.types import JsonType


class TestFieldTypesExamples:

    def test_builtin_scalar_types(self):
        """Test all built-in scalar types from field-types.md"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def string_field(self) -> str:
                return "Hello World"

            @api.field
            def integer_field(self) -> int:
                return 42

            @api.field
            def float_field(self) -> float:
                return 3.14

            @api.field
            def boolean_field(self) -> bool:
                return True

            @api.field
            def uuid_field(self) -> UUID:
                return UUID("12345678-1234-5678-1234-567812345678")

            @api.field
            def datetime_field(self) -> datetime:
                return datetime(2023, 1, 1, 12, 0, 0)

            @api.field
            def date_field(self) -> date:
                return date(2023, 1, 1)

            @api.field
            def bytes_field(self) -> bytes:
                return b"binary data"

        query = """
        query {
            stringField
            integerField
            floatField
            booleanField
            uuidField
            datetimeField
            dateField
            bytesField
        }
        """

        result = api.execute(query)
        assert not result.errors
        data = result.data
        assert data["stringField"] == "Hello World"
        assert data["integerField"] == 42
        assert data["floatField"] == 3.14
        assert data["booleanField"] is True
        assert data["uuidField"] == "12345678-1234-5678-1234-567812345678"
        assert data["datetimeField"] == "2023-01-01 12:00:00"
        assert data["dateField"] == "2023-01-01"
        assert data["bytesField"] == "binary data"

    def test_collection_types(self):
        """Test collection types from field-types.md"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def string_list(self) -> List[str]:
                return ["apple", "banana", "cherry"]

            @api.field
            def optional_field(self) -> Optional[str]:
                return None  # Can be null

            @api.field
            def required_field(self) -> str:
                return "Always present"  # Non-null

            @api.field
            def nested_list(self) -> List[List[int]]:
                return [[1, 2], [3, 4]]

        query = """
        query {
            stringList
            optionalField
            requiredField
            nestedList
        }
        """

        result = api.execute(query)
        assert not result.errors
        data = result.data
        assert data["stringList"] == ["apple", "banana", "cherry"]
        assert data["optionalField"] is None
        assert data["requiredField"] == "Always present"
        assert data["nestedList"] == [[1, 2], [3, 4]]

    def test_json_and_dynamic_types(self):
        """Test JSON and dynamic types from field-types.md"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def dict_field(self) -> dict:
                return {"key": "value", "number": 42}

            @api.field
            def list_field(self) -> list:
                return [1, "mixed", True]

            @api.field
            def json_field(self, data: JsonType) -> JsonType:
                return {"processed": data}

        # Test dict field
        result = api.execute("query { dictField }")
        assert not result.errors
        assert result.data["dictField"] == '{"key": "value", "number": 42}'

        # Test list field
        result = api.execute("query { listField }")
        assert not result.errors
        assert result.data["listField"] == '[1, "mixed", true]'

        # Test json field with input
        result = api.execute('query { jsonField(data: "{\\"test\\": true}") }')
        assert not result.errors
        # The result should be a JSON string containing the processed data

    def test_enum_types(self):
        """Test enum types from field-types.md"""
        import enum

        api = GraphQLAPI()

        class Status(enum.Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"
            PENDING = "pending"

        class Priority(enum.IntEnum):
            LOW = 1
            MEDIUM = 2
            HIGH = 3

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def current_status(self) -> Status:
                return Status.ACTIVE

            @api.field
            def task_priority(self, priority: Priority) -> str:
                return f"Priority level: {priority.value}"

        # Test enum return
        result = api.execute("query { currentStatus }")
        assert not result.errors
        assert result.data["currentStatus"] == "ACTIVE"

        # Test enum argument
        result = api.execute("query { taskPriority(priority: HIGH) }")
        assert not result.errors
        assert result.data["taskPriority"] == "Priority level: 3"

    def test_custom_scalar_types(self):
        """Test custom scalar types from field-types.md"""
        api = GraphQLAPI()

        # Define a custom scalar
        def parse_value(value):
            return str(value) + "_parsed"

        def parse_literal(node):
            if isinstance(node, StringValueNode):
                return parse_value(node.value)

        def serialize(value):
            return str(value) + "_serialized"

        GraphQLKey = GraphQLScalarType(
            name="Key",
            description="The `Key` scalar type represents a unique key.",
            serialize=serialize,
            parse_value=parse_value,
            parse_literal=parse_literal,
        )

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def process_key(self, key: GraphQLKey) -> GraphQLKey:  # type: ignore[valid-type]
                return key

        # Test custom scalar with literal
        result = api.execute('query { processKey(key: "test") }')
        assert not result.errors
        assert result.data["processKey"] == "test_parsed_serialized"

    def test_graphql_id_type(self):
        """Test GraphQL ID type from field-types.md"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def get_by_id(self, id: GraphQLID) -> str:  # type: ignore[valid-type]
                return f"Found item with ID: {id}"

        result = api.execute('query { getById(id: "123") }')
        assert not result.errors
        assert result.data["getById"] == "Found item with ID: 123"

    def test_union_types(self):
        """Test union types from field-types.md"""
        api = GraphQLAPI()

        class Cat(BaseModel):
            name: str
            meow_volume: int

        class Dog(BaseModel):
            name: str
            bark_loudness: int

        @api.type(is_root_type=True)
        class Root:
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

    def test_object_types(self):
        """Test object types from field-types.md"""
        api = GraphQLAPI()

        # Using dataclasses
        @dataclass
        class Address:
            street: str
            city: str
            country: str

        # Using Pydantic models
        class User(BaseModel):
            id: int
            name: str
            email: str

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def user_address(self) -> Address:
                return Address(street="123 Main St", city="New York", country="USA")

            @api.field
            def current_user(self) -> User:
                return User(id=1, name="Alice", email="alice@example.com")

        query = """
        query {
            userAddress {
                street
                city
                country
            }
            currentUser {
                id
                name
                email
            }
        }
        """

        result = api.execute(query)
        assert not result.errors
        data = result.data
        assert data["userAddress"] == {
            "street": "123 Main St",
            "city": "New York",
            "country": "USA"
        }
        assert data["currentUser"] == {
            "id": 1,
            "name": "Alice",
            "email": "alice@example.com"
        }

    def test_input_types(self):
        """Test input types from field-types.md"""
        api = GraphQLAPI()

        class CreateUserInput(BaseModel):
            name: str
            email: str
            age: int

        class User(BaseModel):
            id: int
            name: str
            email: str

        @api.type(is_root_type=True)
        class Root:
            @api.field(mutable=True)
            def create_user(self, input: CreateUserInput) -> User:
                return User(id=999, name=input.name, email=input.email)

        query = """
        mutation {
            createUser(input: {
                name: "Bob"
                email: "bob@example.com"
                age: 30
            }) {
                id
                name
                email
            }
        }
        """

        result = api.execute(query)
        assert not result.errors
        data = result.data
        assert data["createUser"]["id"] == 999
        assert data["createUser"]["name"] == "Bob"
        assert data["createUser"]["email"] == "bob@example.com"

    def test_field_types_schema_generation(self):
        """Test that field types generate correct GraphQL schema"""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def required_string(self) -> str:
                return "test"

            @api.field
            def optional_string(self) -> Optional[str]:
                return None

            @api.field
            def string_list(self) -> List[str]:
                return ["test"]

            @api.field
            def optional_string_list(self) -> Optional[List[str]]:
                return None

        executor = api.executor()
        schema = executor.schema

        # Check field types in schema
        fields = schema.query_type.fields

        assert str(fields["requiredString"].type) == "String!"
        assert str(fields["optionalString"].type) == "String"
        assert str(fields["stringList"].type) == "[String!]!"
        assert str(fields["optionalStringList"].type) == "[String!]"

    def test_advanced_dataclass_relationships(self):
        """Test advanced dataclass relationships with @field decorator"""
        from dataclasses import dataclass
        from typing import List, Optional
        from graphql_api.decorators import field

        api = GraphQLAPI()

        # Sample data (in real apps, this would be from a database)
        authors_db = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
        ]

        posts_db = [
            {"id": 1, "title": "First Post", "content": "Content", "author_id": 1},
            {"id": 2, "title": "Second Post", "content": "More content", "author_id": 2},
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
                """Get all posts by this author."""
                return [Post(**p) for p in posts_db if p["author_id"] == self.id]

        # Add relationship method to Post after Author is defined
        @field
        def get_author(self) -> Optional[Author]:
            """Get the author of this post."""
            author_data = next((a for a in authors_db if a["id"] == self.author_id), None)
            if author_data:
                return Author(**author_data)
            return None

        # Attach the method to the dataclass
        Post.get_author = get_author

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def posts(self) -> List[Post]:
                return [Post(**p) for p in posts_db]

            @api.field
            def authors(self) -> List[Author]:
                return [Author(**a) for a in authors_db]

        # Test schema generation
        schema, _ = api.build_schema()
        assert schema is not None

        # Check that the relationships are in the schema
        post_type = schema.type_map["Post"]
        assert "getAuthor" in post_type.fields

        author_type = schema.type_map["Author"]
        assert "getPosts" in author_type.fields

        # Test query execution with relationships
        result = api.execute('''
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
        ''')

        assert not result.errors
        assert len(result.data["posts"]) == 2
        assert result.data["posts"][0]["getAuthor"]["name"] == "Alice"
        assert result.data["posts"][1]["getAuthor"]["name"] == "Bob"

        # Test reverse relationship
        result = api.execute('''
            query {
                authors {
                    name
                    getPosts {
                        title
                    }
                }
            }
        ''')

        assert not result.errors
        assert len(result.data["authors"]) == 2
        assert len(result.data["authors"][0]["getPosts"]) == 1
        assert result.data["authors"][0]["getPosts"][0]["title"] == "First Post"

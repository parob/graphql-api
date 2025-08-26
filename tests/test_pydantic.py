from pydantic import BaseModel, Field
from typing import List, Optional, Union
from enum import Enum
from dataclasses import dataclass

from graphql_api.api import GraphQLAPI
from graphql_api.decorators import field


class TestPydantic:

    def test_pydantic(self):
        class Statistics(BaseModel):
            conversations_count: int = Field(description="Number of conversations")
            messages_count: int

        class ExampleAPI:

            @field
            def get_stats(self) -> Statistics:
                return Statistics(conversations_count=10, messages_count=25)

        api = GraphQLAPI(root_type=ExampleAPI)

        query = """
            query {
                getStats {
                    conversationsCount
                    messagesCount
                }
            }
        """
        expected = {"getStats": {"conversationsCount": 10, "messagesCount": 25}}
        response = api.execute(query)
        assert response.data == expected

    def test_nested_pydantic_models(self):
        class Author(BaseModel):
            name: str

        class Book(BaseModel):
            title: str
            author: Author

        class LibraryAPI:
            @field
            def get_book(self) -> Book:
                return Book(
                    title="The Hitchhiker's Guide to the Galaxy",
                    author=Author(name="Douglas Adams"),
                )

        api = GraphQLAPI(root_type=LibraryAPI)
        query = """
            query {
                getBook {
                    title
                    author {
                        name
                    }
                }
            }
        """
        expected = {
            "getBook": {
                "title": "The Hitchhiker's Guide to the Galaxy",
                "author": {"name": "Douglas Adams"},
            }
        }
        response = api.execute(query)
        assert response.data == expected

    def test_list_of_pydantic_models(self):
        class ToDo(BaseModel):
            task: str
            completed: bool

        class ToDoAPI:
            @field
            def get_todos(self) -> List[ToDo]:
                return [
                    ToDo(task="Learn GraphQL", completed=True),
                    ToDo(task="Write more tests", completed=False),
                ]

        api = GraphQLAPI(root_type=ToDoAPI)
        query = """
            query {
                getTodos {
                    task
                    completed
                }
            }
        """
        expected = {
            "getTodos": [
                {"task": "Learn GraphQL", "completed": True},
                {"task": "Write more tests", "completed": False},
            ]
        }
        response = api.execute(query)
        assert response.data == expected

    def test_optional_fields_and_scalar_types(self):
        class UserProfile(BaseModel):
            username: str
            age: Optional[int] = None
            is_active: bool
            rating: float

        class UserAPI:
            @field
            def get_user(self) -> UserProfile:
                return UserProfile(username="testuser", is_active=True, rating=4.5)

        api = GraphQLAPI(root_type=UserAPI)
        query = """
            query {
                getUser {
                    username
                    age
                    isActive
                    rating
                }
            }
        """
        expected = {
            "getUser": {
                "username": "testuser",
                "age": None,
                "isActive": True,
                "rating": 4.5,
            }
        }
        response = api.execute(query)
        assert response.data == expected

    def test_pydantic_model_with_enum(self):
        class StatusEnum(str, Enum):
            PENDING = "PENDING"
            COMPLETED = "COMPLETED"

        class Task(BaseModel):
            name: str
            status: StatusEnum

        class TaskAPI:
            @field
            def get_task(self) -> Task:
                return Task(name="My Task", status=StatusEnum.PENDING)

        api = GraphQLAPI(root_type=TaskAPI)
        query = """
            query {
                getTask {
                    name
                    status
                }
            }
        """
        expected = {"getTask": {"name": "My Task", "status": "PENDING"}}
        response = api.execute(query)
        assert response.data == expected

    def test_deeply_nested_pydantic_models(self):
        class User(BaseModel):
            id: int
            username: str

        class Comment(BaseModel):
            text: str
            author: User

        class Post(BaseModel):
            title: str
            content: str
            comments: List[Comment]

        class BlogAPI:
            @field
            def get_latest_post(self) -> Post:
                return Post(
                    title="Deeply Nested Structures",
                    content="A post about testing them.",
                    comments=[
                        Comment(
                            text="Great post!", author=User(id=1, username="commenter1")
                        ),
                        Comment(
                            text="Very informative.",
                            author=User(id=2, username="commenter2"),
                        ),
                    ],
                )

        api = GraphQLAPI(root_type=BlogAPI)
        query = """
            query {
                getLatestPost {
                    title
                    content
                    comments {
                        text
                        author {
                            id
                            username
                        }
                    }
                }
            }
        """
        expected = {
            "getLatestPost": {
                "title": "Deeply Nested Structures",
                "content": "A post about testing them.",
                "comments": [
                    {
                        "text": "Great post!",
                        "author": {"id": 1, "username": "commenter1"},
                    },
                    {
                        "text": "Very informative.",
                        "author": {"id": 2, "username": "commenter2"},
                    },
                ],
            }
        }
        response = api.execute(query)
        assert response.data == expected

    def test_list_with_optional_nested_model(self):
        class Chapter(BaseModel):
            title: str
            page_count: int

        class Book(BaseModel):
            title: str
            chapter: Optional[Chapter] = None

        class ShelfAPI:
            @field
            def get_books(self) -> List[Book]:
                return [
                    Book(
                        title="A Book with a Chapter",
                        chapter=Chapter(title="The Beginning", page_count=20),
                    ),
                    Book(title="A Book without a Chapter"),
                ]

        api = GraphQLAPI(root_type=ShelfAPI)
        query = """
            query {
                getBooks {
                    title
                    chapter {
                        title
                        pageCount
                    }
                }
            }
        """
        expected = {
            "getBooks": [
                {
                    "title": "A Book with a Chapter",
                    "chapter": {"title": "The Beginning", "pageCount": 20},
                },
                {"title": "A Book without a Chapter", "chapter": None},
            ]
        }
        response = api.execute(query)
        assert response.data == expected

    def test_pydantic_model_with_default_value(self):
        class Config(BaseModel):
            name: str
            value: str = "default_value"

        class ConfigAPI:
            @field
            def get_config(self) -> Config:
                return Config(name="test_config")

        api = GraphQLAPI(root_type=ConfigAPI)
        query = """
            query {
                getConfig {
                    name
                    value
                }
            }
        """
        expected = {"getConfig": {"name": "test_config", "value": "default_value"}}
        response = api.execute(query)
        assert response.data == expected

    def test_pydantic_model_with_field_alias(self):
        class User(BaseModel):
            user_name: str = Field(..., alias="userName")
            user_id: int = Field(..., alias="userId")

        class UserAliasAPI:
            @field
            def get_user_with_alias(self) -> User:
                return User.model_validate({"userName": "aliased_user", "userId": 123})

        api = GraphQLAPI(root_type=UserAliasAPI)
        query = """
            query {
                getUserWithAlias {
                    userName
                    userId
                }
            }
        """
        expected = {"getUserWithAlias": {"userName": "aliased_user", "userId": 123}}
        response = api.execute(query)
        assert response.data == expected

    def test_pydantic_with_dataclass_field(self):
        @dataclass
        class DataClassDetails:
            detail: str

        class ModelWithDataClass(BaseModel):
            name: str
            details: DataClassDetails

        class MixedAPI:
            @field
            def get_mixed_model(self) -> ModelWithDataClass:
                return ModelWithDataClass(
                    name="Mixed",
                    details=DataClassDetails(detail="This is from a dataclass"),
                )

        api = GraphQLAPI(root_type=MixedAPI)
        query = """
            query {
                getMixedModel {
                    name
                    details {
                        detail
                    }
                }
            }
        """
        expected = {
            "getMixedModel": {
                "name": "Mixed",
                "details": {"detail": "This is from a dataclass"},
            }
        }
        response = api.execute(query)
        assert response.data == expected

    def test_recursive_pydantic_model(self):
        class Employee(BaseModel):
            name: str
            manager: Optional["Employee"] = None

        class OrgAPI:
            @field
            def get_employee_hierarchy(self) -> Employee:
                manager = Employee(name="Big Boss")
                return Employee(name="Direct Report", manager=manager)

        api = GraphQLAPI(root_type=OrgAPI)
        query = """
            query {
                getEmployeeHierarchy {
                    name
                    manager {
                        name
                        manager {
                            name
                        }
                    }
                }
            }
        """
        expected = {
            "getEmployeeHierarchy": {
                "name": "Direct Report",
                "manager": {"name": "Big Boss", "manager": None},
            }
        }
        response = api.execute(query)
        assert response.data == expected

    def test_pydantic_model_with_union_field(self):
        class Cat(BaseModel):
            name: str
            meow_volume: int

        class Dog(BaseModel):
            name: str
            bark_loudness: int

        class PetOwner(BaseModel):
            name: str
            pet: Union[Cat, Dog]

        class PetAPI:
            @field
            def get_cat_owner(self) -> PetOwner:
                return PetOwner(
                    name="Cat Lover", pet=Cat(name="Whiskers", meow_volume=10)
                )

        api = GraphQLAPI(root_type=PetAPI)
        query = """
            query {
                getCatOwner {
                    name
                    pet {
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
            }
        """
        expected = {
            "getCatOwner": {
                "name": "Cat Lover",
                "pet": {"name": "Whiskers", "meowVolume": 10},
            }
        }
        response = api.execute(query)
        assert response.data == expected

    def test_pydantic_forward_ref(self):
        class ModelA(BaseModel):
            b: "ModelB"

        class ModelB(BaseModel):
            a_val: int

        ModelA.model_rebuild()

        class ForwardRefAPI:
            @field
            def get_a(self) -> ModelA:
                return ModelA(b=ModelB(a_val=123))

        api = GraphQLAPI(root_type=ForwardRefAPI)
        query = """
            query {
                getA {
                    b {
                        aVal
                    }
                }
            }
        """
        expected = {"getA": {"b": {"aVal": 123}}}
        response = api.execute(query)
        assert response.data == expected

    def test_pydantic_model_as_input_argument(self):
        """Test that Pydantic models work as input arguments to GraphQL fields."""

        class UserInput(BaseModel):
            name: str
            age: int
            email: Optional[str] = None
            is_active: bool = True

        class User(BaseModel):
            id: int
            name: str
            age: int
            email: Optional[str]
            is_active: bool

        class UserAPI:
            # Class-level storage for simplicity in tests
            next_id = 1
            users = []

            @field(mutable=True)
            def create_user(self, user_input: UserInput) -> User:
                """Create a new user from input data."""
                user = User(
                    id=UserAPI.next_id,
                    name=user_input.name,
                    age=user_input.age,
                    email=user_input.email,
                    is_active=user_input.is_active
                )
                UserAPI.users.append(user)
                UserAPI.next_id += 1
                return user

            @field(mutable=True)
            def update_user(self, user_id: int, user_input: UserInput) -> Optional[User]:
                """Update an existing user."""
                for user in UserAPI.users:
                    if user.id == user_id:
                        user.name = user_input.name
                        user.age = user_input.age
                        user.email = user_input.email
                        user.is_active = user_input.is_active
                        return user
                return None

        # Reset class state for test isolation
        UserAPI.next_id = 1
        UserAPI.users = []

        api = GraphQLAPI(root_type=UserAPI)

        # Test creating a user with required fields only
        mutation1 = """
            mutation {
                createUser(userInput: {
                    name: "Alice",
                    age: 30
                }) {
                    id
                    name
                    age
                    email
                    isActive
                }
            }
        """
        expected1 = {
            "createUser": {
                "id": 1,
                "name": "Alice",
                "age": 30,
                "email": None,
                "isActive": True
            }
        }
        response1 = api.execute(mutation1)
        assert response1.data == expected1

        # Test creating a user with all fields
        mutation2 = """
            mutation {
                createUser(userInput: {
                    name: "Bob",
                    age: 25,
                    email: "bob@example.com",
                    isActive: false
                }) {
                    id
                    name
                    age
                    email
                    isActive
                }
            }
        """
        expected2 = {
            "createUser": {
                "id": 2,
                "name": "Bob",
                "age": 25,
                "email": "bob@example.com",
                "isActive": False
            }
        }
        response2 = api.execute(mutation2)
        assert response2.data == expected2

        # Test updating a user
        mutation3 = """
            mutation {
                updateUser(userId: 1, userInput: {
                    name: "Alice Updated",
                    age: 31,
                    email: "alice@updated.com",
                    isActive: false
                }) {
                    id
                    name
                    age
                    email
                    isActive
                }
            }
        """
        expected3 = {
            "updateUser": {
                "id": 1,
                "name": "Alice Updated",
                "age": 31,
                "email": "alice@updated.com",
                "isActive": False
            }
        }
        response3 = api.execute(mutation3)
        assert response3.data == expected3

    def test_nested_pydantic_models_as_input(self):
        """Test nested Pydantic models as input arguments."""

        class AddressInput(BaseModel):
            street: str
            city: str
            country: str
            postal_code: Optional[str] = None

        class ContactInput(BaseModel):
            name: str
            phone: Optional[str] = None
            address: AddressInput

        class Contact(BaseModel):
            id: int
            name: str
            phone: Optional[str]
            address: AddressInput

        class ContactAPI:
            @field(mutable=True)
            def create_contact(self, contact_input: ContactInput) -> Contact:
                """Create a new contact with address."""
                return Contact(
                    id=1,  # Simplified for test
                    name=contact_input.name,
                    phone=contact_input.phone,
                    address=contact_input.address
                )

        api = GraphQLAPI(root_type=ContactAPI)

        mutation = """
            mutation {
                createContact(contactInput: {
                    name: "John Doe",
                    phone: "123-456-7890",
                    address: {
                        street: "123 Main St",
                        city: "Anytown",
                        country: "USA",
                        postalCode: "12345"
                    }
                }) {
                    id
                    name
                    phone
                    address {
                        street
                        city
                        country
                        postalCode
                    }
                }
            }
        """
        expected = {
            "createContact": {
                "id": 1,
                "name": "John Doe",
                "phone": "123-456-7890",
                "address": {
                    "street": "123 Main St",
                    "city": "Anytown",
                    "country": "USA",
                    "postalCode": "12345"
                }
            }
        }
        response = api.execute(mutation)
        assert response.data == expected

    def test_pydantic_input_with_list_field(self):
        """Test Pydantic model with list fields as input arguments."""

        class TagInput(BaseModel):
            name: str
            color: str

        class PostInput(BaseModel):
            title: str
            content: str
            tags: List[TagInput]
            published: bool = False

        class Post(BaseModel):
            id: int
            title: str
            content: str
            tags: List[TagInput]
            published: bool

        class BlogAPI:
            @field(mutable=True)
            def create_post(self, post_input: PostInput) -> Post:
                """Create a new blog post with tags."""
                return Post(
                    id=1,  # Simplified for test
                    title=post_input.title,
                    content=post_input.content,
                    tags=post_input.tags,
                    published=post_input.published
                )

        api = GraphQLAPI(root_type=BlogAPI)

        mutation = """
            mutation {
                createPost(postInput: {
                    title: "My First Post",
                    content: "This is the content of my first post.",
                    tags: [
                        {name: "technology", color: "blue"},
                        {name: "tutorial", color: "green"}
                    ],
                    published: true
                }) {
                    id
                    title
                    content
                    tags {
                        name
                        color
                    }
                    published
                }
            }
        """
        expected = {
            "createPost": {
                "id": 1,
                "title": "My First Post",
                "content": "This is the content of my first post.",
                "tags": [
                    {"name": "technology", "color": "blue"},
                    {"name": "tutorial", "color": "green"}
                ],
                "published": True
            }
        }
        response = api.execute(mutation)
        assert response.data == expected

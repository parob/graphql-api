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

    def test_pydantic_list_input_schema_generation(self):
        """Test that List[PydanticModel] generates proper GraphQL list types, not JSON."""

        class ItemInput(BaseModel):
            name: str
            value: int

        class ContainerInput(BaseModel):
            title: str
            items: List[ItemInput]

        class Container(BaseModel):
            id: int
            title: str
            items: List[ItemInput]

        class API:
            @field(mutable=True)
            def create_container(self, container_input: ContainerInput) -> Container:
                """Create a container with items."""
                return Container(
                    id=1,
                    title=container_input.title,
                    items=container_input.items
                )

        api = GraphQLAPI(root_type=API)
        schema, _ = api.build_schema()

        # Get the GraphQL SDL to inspect the schema
        from graphql import print_schema
        schema_sdl = print_schema(schema)
        print("\nSchema SDL:")
        print(schema_sdl)

        # Check that the input type uses proper list syntax, not JSON
        assert "items: [ItemInputInput!]" in schema_sdl or "items: [ItemInputInput]" in schema_sdl
        assert "JSON" not in schema_sdl  # Should not fall back to JSON type
        assert "ItemInputInput" in schema_sdl  # Should have proper input type

        # Test the actual functionality
        mutation = """
            mutation {
                createContainer(containerInput: {
                    title: "Test Container",
                    items: [
                        {name: "Item 1", value: 100},
                        {name: "Item 2", value: 200}
                    ]
                }) {
                    id
                    title
                    items {
                        name
                        value
                    }
                }
            }
        """

        expected = {
            "createContainer": {
                "id": 1,
                "title": "Test Container",
                "items": [
                    {"name": "Item 1", "value": 100},
                    {"name": "Item 2", "value": 200}
                ]
            }
        }

        response = api.execute(mutation)
        assert response.data == expected

    def test_dict_type_mapping_to_json_scalar(self):
        """Test that Dict[str, str] and Dict[str, Any] map to JSON scalar instead of failing."""
        from typing import Dict, Any

        class ConfigInput(BaseModel):
            name: str
            settings: Dict[str, str]
            metadata: Dict[str, Any]

        class Config(BaseModel):
            id: int
            name: str
            total_settings: int

        class ConfigAPI:
            @field(mutable=True)
            def create_config(self, config_input: ConfigInput) -> Config:
                """Create config with dict fields."""
                # For this test, we just verify the schema generation works
                # The dict will be passed as JSON scalar
                return Config(
                    id=1,
                    name=config_input.name if hasattr(config_input, 'name') else "dict_input",
                    total_settings=1
                )

        api = GraphQLAPI(root_type=ConfigAPI)
        schema, _ = api.build_schema()

        # Get the GraphQL SDL to inspect the schema
        from graphql import print_schema
        schema_sdl = print_schema(schema)

        # Verify that Dict fields map to JSON instead of causing mapping errors
        assert "settings: JSON" in schema_sdl
        assert "metadata: JSON" in schema_sdl
        assert "ConfigInputInput" in schema_sdl

        # Verify we didn't get any "Unable to map" errors during schema generation
        assert "JSON" in schema_sdl  # JSON scalar should be present

        print("✅ Dict types successfully mapped to JSON scalar!")
        print(f"Schema contains {schema_sdl.count('JSON')} JSON references")

        # Demonstrate that this fixes the original issue:
        # Before fix: "Unable to map pydantic field 'settings' with type typing.Dict[str, str]"
        # After fix: Dict fields properly map to JSON scalar type in GraphQL schema

    def test_pydantic_response_status_pattern(self):
        """Test a common API response pattern with status, message, and data fields."""
        from typing import Dict, Any
        from enum import Enum

        class ResponseStatusEnum(str, Enum):
            """Status of a response operation."""
            SUCCESS = "SUCCESS"
            ERROR = "ERROR"

        class ResponseStatus(BaseModel):
            status: ResponseStatusEnum
            message: Optional[str] = None
            error_message: Optional[str] = None
            data: Optional[Dict[str, Any]] = None

            @classmethod
            def error(cls, error_message: str) -> "ResponseStatus":
                return cls(status=ResponseStatusEnum.ERROR, error_message=error_message)

            @classmethod
            def success(cls, message: str, data: Optional[Dict[str, Any]] = None) -> "ResponseStatus":
                return cls(status=ResponseStatusEnum.SUCCESS, message=message, data=data)

        class ResponseAPI:
            @field(mutable=True)
            def create_user(self, name: str, email: str) -> ResponseStatus:
                """Create a user and return status with data."""
                if not email or "@" not in email:
                    return ResponseStatus.error("Invalid email address")

                return ResponseStatus.success(
                    "User created successfully",
                    data={"user_id": 123, "name": name, "email": email}
                )

        api = GraphQLAPI(root_type=ResponseAPI)
        schema, _ = api.build_schema()

        # Verify schema generation
        from graphql import print_schema
        schema_sdl = print_schema(schema)
        assert "data: JSON" in schema_sdl
        assert "ResponseStatusEnumEnum" in schema_sdl
        assert "Status of a response operation." in schema_sdl

        # Test success case
        mutation_success = """
            mutation {
                createUser(name: "John Doe", email: "john@example.com") {
                    status
                    message
                    errorMessage
                    data
                }
            }
        """
        result_success = api.execute(mutation_success)
        assert result_success.data == {
            "createUser": {
                "status": "SUCCESS",
                "message": "User created successfully",
                "errorMessage": None,
                "data": '{"user_id": 123, "name": "John Doe", "email": "john@example.com"}'
            }
        }

        # Test error case
        mutation_error = """
            mutation {
                createUser(name: "Jane Doe", email: "invalid-email") {
                    status
                    message
                    errorMessage
                    data
                }
            }
        """
        result_error = api.execute(mutation_error)
        assert result_error.data == {
            "createUser": {
                "status": "ERROR",
                "message": None,
                "errorMessage": "Invalid email address",
                "data": None
            }
        }

    def test_list_pydantic_model_parameter_conversion(self):
        """Test that List[PydanticModel] parameters are automatically converted from dicts to model instances."""
        from enum import Enum

        class Priority(str, Enum):
            """Task priority levels."""
            LOW = "LOW"
            HIGH = "HIGH"

        class Task(BaseModel):
            title: str
            priority: Priority
            completed: bool = False

        class TaskResult(BaseModel):
            processed_count: int
            success: bool

        class TaskAPI:
            @field(mutable=True)
            def process_tasks(self, tasks: List[Task]) -> TaskResult:
                """Process a list of tasks - should receive Task objects, not dicts."""
                processed = 0

                for task in tasks:
                    # These should work because task is a Task instance, not a dict
                    assert hasattr(task, 'title'), f"Expected Task object, got {type(task)}"
                    assert hasattr(task, 'priority'), f"Expected Task object, got {type(task)}"
                    assert isinstance(task, Task), f"Expected Task instance, got {type(task)}"

                    # Test that we can access Pydantic model attributes
                    _ = task.title  # Should work
                    _ = task.priority  # Should work
                    _ = task.completed  # Should work

                    processed += 1

                return TaskResult(processed_count=processed, success=True)

        api = GraphQLAPI(root_type=TaskAPI)

        mutation = """
            mutation {
                processTasks(tasks: [
                    {title: "Task 1", priority: LOW, completed: false},
                    {title: "Task 2", priority: HIGH, completed: true},
                    {title: "Task 3", priority: LOW}
                ]) {
                    processedCount
                    success
                }
            }
        """

        result = api.execute(mutation)
        assert result.data == {
            "processTasks": {
                "processedCount": 3,
                "success": True
            }
        }
        assert result.errors is None

    def test_mixed_parameter_types_with_list_conversion(self):
        """Test that List[PydanticModel] conversion works alongside other parameter types."""

        class Item(BaseModel):
            name: str
            value: int

        class ProcessResult(BaseModel):
            total_value: int
            item_count: int
            category: str

        class MixedAPI:
            @field(mutable=True)
            def process_items_with_category(
                self,
                items: List[Item],
                category: str,
                multiplier: int = 1
            ) -> ProcessResult:
                """Test mixed parameter types with List[PydanticModel]."""
                total = sum(item.value for item in items)  # Should work with Item objects
                return ProcessResult(
                    total_value=total * multiplier,
                    item_count=len(items),
                    category=category
                )

        api = GraphQLAPI(root_type=MixedAPI)

        mutation = """
            mutation {
                processItemsWithCategory(
                    items: [
                        {name: "Item A", value: 10},
                        {name: "Item B", value: 20}
                    ],
                    category: "test",
                    multiplier: 2
                ) {
                    totalValue
                    itemCount
                    category
                }
            }
        """

        result = api.execute(mutation)
        assert result.data == {
            "processItemsWithCategory": {
                "totalValue": 60,  # (10 + 20) * 2
                "itemCount": 2,
                "category": "test"
            }
        }

    def test_optional_list_pydantic_model_parameter_conversion(self):
        """Test that Optional[List[PydanticModel]] parameters are handled correctly."""

        class Tag(BaseModel):
            name: str
            color: str

        class TagResult(BaseModel):
            message: str
            tag_count: int

        class OptionalListAPI:
            @field(mutable=True)
            def process_optional_tags(self, tags: Optional[List[Tag]] = None) -> TagResult:
                """Process optional list of tags."""
                if tags is None:
                    return TagResult(message="No tags provided", tag_count=0)

                # Should receive Tag objects, not dicts
                for tag in tags:
                    assert isinstance(tag, Tag), f"Expected Tag object, got {type(tag)}"
                    assert hasattr(tag, 'name')
                    assert hasattr(tag, 'color')

                return TagResult(
                    message=f"Processed tags: {', '.join(tag.name for tag in tags)}",
                    tag_count=len(tags)
                )

        api = GraphQLAPI(root_type=OptionalListAPI)

        # Test with None (omitted parameter)
        mutation1 = """
            mutation {
                processOptionalTags {
                    message
                    tagCount
                }
            }
        """
        result1 = api.execute(mutation1)
        assert result1.data == {
            "processOptionalTags": {
                "message": "No tags provided",
                "tagCount": 0
            }
        }

        # Test with actual tags
        mutation2 = """
            mutation {
                processOptionalTags(tags: [
                    {name: "urgent", color: "red"},
                    {name: "feature", color: "green"}
                ]) {
                    message
                    tagCount
                }
            }
        """
        result2 = api.execute(mutation2)
        assert result2.data == {
            "processOptionalTags": {
                "message": "Processed tags: urgent, feature",
                "tagCount": 2
            }
        }

        # Test with empty list
        mutation3 = """
            mutation {
                processOptionalTags(tags: []) {
                    message
                    tagCount
                }
            }
        """
        result3 = api.execute(mutation3)
        assert result3.data == {
            "processOptionalTags": {
                "message": "Processed tags: ",
                "tagCount": 0
            }
        }

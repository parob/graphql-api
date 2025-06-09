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
                return Statistics(
                    conversations_count=10, messages_count=25
                )

        api = GraphQLAPI(root_type=ExampleAPI)

        query = '''
            query {
                getStats {
                    conversationsCount
                    messagesCount
                }
            }
        '''
        expected = {
            'getStats': {
                'conversationsCount': 10,
                'messagesCount': 25
            }
        }
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
                    author=Author(name="Douglas Adams")
                )

        api = GraphQLAPI(root_type=LibraryAPI)
        query = '''
            query {
                getBook {
                    title
                    author {
                        name
                    }
                }
            }
        '''
        expected = {
            'getBook': {
                'title': "The Hitchhiker's Guide to the Galaxy",
                'author': {
                    'name': "Douglas Adams"
                }
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
        query = '''
            query {
                getTodos {
                    task
                    completed
                }
            }
        '''
        expected = {
            'getTodos': [
                {'task': "Learn GraphQL", 'completed': True},
                {'task': "Write more tests", 'completed': False},
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
                return UserProfile(
                    username="testuser",
                    is_active=True,
                    rating=4.5
                )

        api = GraphQLAPI(root_type=UserAPI)
        query = '''
            query {
                getUser {
                    username
                    age
                    isActive
                    rating
                }
            }
        '''
        expected = {
            'getUser': {
                'username': "testuser",
                'age': None,
                'isActive': True,
                'rating': 4.5
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
        query = '''
            query {
                getTask {
                    name
                    status
                }
            }
        '''
        expected = {
            'getTask': {
                'name': "My Task",
                'status': "PENDING"
            }
        }
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
                        Comment(text="Great post!", author=User(id=1, username="commenter1")),
                        Comment(text="Very informative.", author=User(id=2, username="commenter2")),
                    ]
                )

        api = GraphQLAPI(root_type=BlogAPI)
        query = '''
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
        '''
        expected = {
            'getLatestPost': {
                'title': "Deeply Nested Structures",
                'content': "A post about testing them.",
                'comments': [
                    {'text': "Great post!", 'author': {'id': 1, 'username': "commenter1"}},
                    {'text': "Very informative.", 'author': {'id': 2, 'username': "commenter2"}},
                ]
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
                    Book(title="A Book with a Chapter", chapter=Chapter(title="The Beginning", page_count=20)),
                    Book(title="A Book without a Chapter")
                ]

        api = GraphQLAPI(root_type=ShelfAPI)
        query = '''
            query {
                getBooks {
                    title
                    chapter {
                        title
                        pageCount
                    }
                }
            }
        '''
        expected = {
            'getBooks': [
                {
                    'title': "A Book with a Chapter",
                    'chapter': {'title': "The Beginning", 'pageCount': 20}
                },
                {
                    'title': "A Book without a Chapter",
                    'chapter': None
                }
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
        query = '''
            query {
                getConfig {
                    name
                    value
                }
            }
        '''
        expected = {
            'getConfig': {
                'name': "test_config",
                'value': "default_value"
            }
        }
        response = api.execute(query)
        assert response.data == expected

    def test_pydantic_model_with_field_alias(self):
        class User(BaseModel):
            user_name: str = Field(..., alias='userName')
            user_id: int = Field(..., alias='userId')

        class UserAliasAPI:
            @field
            def get_user_with_alias(self) -> User:
                return User.model_validate(
                    {'userName': "aliased_user", 'userId': 123}
                )

        api = GraphQLAPI(root_type=UserAliasAPI)
        query = '''
            query {
                getUserWithAlias {
                    userName
                    userId
                }
            }
        '''
        expected = {
            'getUserWithAlias': {
                'userName': "aliased_user",
                'userId': 123
            }
        }
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
                    details=DataClassDetails(detail="This is from a dataclass")
                )

        api = GraphQLAPI(root_type=MixedAPI)
        query = '''
            query {
                getMixedModel {
                    name
                    details {
                        detail
                    }
                }
            }
        '''
        expected = {
            'getMixedModel': {
                'name': "Mixed",
                'details': {
                    'detail': "This is from a dataclass"
                }
            }
        }
        response = api.execute(query)
        assert response.data == expected

    def test_recursive_pydantic_model(self):
        class Employee(BaseModel):
            name: str
            manager: Optional['Employee'] = None

        class OrgAPI:
            @field
            def get_employee_hierarchy(self) -> Employee:
                manager = Employee(name="Big Boss")
                return Employee(name="Direct Report", manager=manager)

        api = GraphQLAPI(root_type=OrgAPI)
        query = '''
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
        '''
        expected = {
            'getEmployeeHierarchy': {
                'name': "Direct Report",
                'manager': {
                    'name': "Big Boss",
                    'manager': None
                }
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
                return PetOwner(name="Cat Lover", pet=Cat(name="Whiskers", meow_volume=10))

        api = GraphQLAPI(root_type=PetAPI)
        query = '''
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
        '''
        expected = {
            'getCatOwner': {
                'name': "Cat Lover",
                'pet': {
                    'name': "Whiskers",
                    'meowVolume': 10
                }
            }
        }
        response = api.execute(query)
        assert response.data == expected

    def test_pydantic_forward_ref(self):
        class ModelA(BaseModel):
            b: 'ModelB'

        class ModelB(BaseModel):
            a_val: int

        ModelA.model_rebuild()

        class ForwardRefAPI:
            @field
            def get_a(self) -> ModelA:
                return ModelA(b=ModelB(a_val=123))

        api = GraphQLAPI(root_type=ForwardRefAPI)
        query = '''
            query {
                getA {
                    b {
                        aVal
                    }
                }
            }
        '''
        expected = {
            'getA': {
                'b': {
                    'aVal': 123
                }
            }
        }
        response = api.execute(query)
        assert response.data == expected

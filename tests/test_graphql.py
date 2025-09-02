import enum
import sys
from dataclasses import dataclass
from typing import List, Literal, Optional, Union

import pytest
import urllib3
from graphql import GraphQLSchema, GraphQLUnionType, GraphQLObjectType
from graphql.utilities import print_schema
from requests.api import request
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# noinspection PyPackageRequirements
# from graphql.utilities import print_schema

from graphql_api.api import GraphQLAPI, GraphQLRootTypeDelegate
from graphql_api.context import GraphQLContext
from graphql_api.decorators import field
from graphql_api.error import GraphQLError
from graphql_api.reduce import TagFilter
from graphql_api.remote import GraphQLRemoteExecutor, remote_execute
from graphql_api.utils import executor_to_ast

# Define Period at module level
Period = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y"]


def available(url, method="POST", is_graphql=False):
    try:
        if is_graphql:
            response = request(
                method,
                url,
                timeout=5,
                verify=False,
                json={"query": "{ __schema { types { name } } }"},
            )
        else:
            response = request(
                method,
                url,
                timeout=5,
                verify=False,
                headers={
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8,"
                    "application/signed-exchange;v=b3;q=0.7"
                },
            )
    except (ConnectionError, ConnectTimeout, ReadTimeout):
        return False

    if response.status_code == 400 or response.status_code == 200:
        return True

    return False


# noinspection PyPep8Naming,DuplicatedCode
class TestGraphQL:
    def test_multiple_apis(self):
        api_1 = GraphQLAPI()
        api_2 = GraphQLAPI()

        @api_1.type
        class Math:
            @api_1.field
            def test_square(self, number: int) -> int:
                return number * number

            @api_2.field
            def test_cube(self, number: int) -> int:
                return number * number * number

        # noinspection PyUnusedLocal
        @api_1.type(is_root_type=True)
        @api_2.type(is_root_type=True)
        class Root:
            @api_1.field
            @api_2.field
            def math(self) -> Math:
                return Math()

        result_1 = api_1.execute(
            """
            query GetTestSquare {
                math {
                    square: testSquare(number: %d)
                }
            }
        """
            % 5
        )

        expected = {"math": {"square": 25}}
        assert not result_1.errors
        assert result_1.data == expected

        result_2 = api_2.execute(
            """
            query GetTestCube {
                math {
                    square: testCube(number: %d)
                }
            }
        """
            % 5
        )

        expected = {"math": {"square": 125}}
        assert not result_2.errors
        assert result_2.data == expected

        result_3 = api_2.execute(
            """
            query GetTestSquare {
                math {
                    square: testSquare(number: %d)
                }
            }
        """
            % 5
        )

        assert result_3.errors

    def test_deep_query(self):
        api = GraphQLAPI()

        class Math:
            @api.field
            def test_square(self, number: int) -> int:
                return number * number

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def math(self) -> Math:
                return Math()

        result = api.execute(
            """
            query GetTestSquare {
                math {
                    square: testSquare(number: %d)
                }
            }
        """
            % 5
        )

        expected = {"math": {"square": 25}}
        assert not result.errors
        assert result.data == expected

    def test_query_object_input(self):
        api = GraphQLAPI()

        class Person:
            def __init__(self, name: str):
                self.name = name

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def get_name(self, person: Person) -> str:
                return person.name

        test_query = """
            query GetTestSquare {
                getName(person: { name: "steve" })
            }
        """

        result = api.execute(test_query)

        expected = {"getName": "steve"}
        assert not result.errors
        assert result.data == expected

    def test_custom_query_input(self):
        api = GraphQLAPI()

        class Person:
            @classmethod
            def graphql_from_input(cls, age: int):
                person = Person(name="hugh")
                person._age = age
                return person

            def __init__(self, name: str):
                self._name = name
                self._age = 20

            @api.field
            def name(self) -> str:
                return self._name

            @api.field
            def age(self) -> int:
                return self._age

        class Root:
            @api.field
            def person_info(self, person: Person) -> str:
                return person.name() + " is " + str(person.age())

        api.root_type = Root
        executor = api.executor()

        test_query = """
            query GetPersonInfo {
                personInfo(person: { age: 30 })
            }
        """

        result = executor.execute(test_query)

        expected = {"personInfo": "hugh is 30"}
        assert not result.errors
        assert result.data == expected

    def test_runtime_field(self):
        api = GraphQLAPI()

        class Person:
            @classmethod
            def graphql_fields(cls):
                @api.field
                def age(_self) -> int:
                    return _self.hidden_age

                return [age]

            def __init__(self, age: int):
                self.hidden_age = age

        class Root:
            @api.field
            def thomas(self) -> Person:
                return Person(age=2)

        api.root_type = Root
        executor = api.executor()

        test_query = """
            query GetThomasAge {
                thomas { age }
            }
        """

        result = executor.execute(test_query)

        expected = {"thomas": {"age": 2}}
        assert not result.errors
        assert result.data == expected

    def test_recursive_query(self):
        api = GraphQLAPI()

        class Root:
            @api.field
            def root(self) -> "Root":
                return Root()

            @api.field
            def value(self) -> int:
                return 5

        api.root_type = Root
        executor = api.executor()

        test_query = """
            query GetRecursiveRoot {
                root {
                    root {
                        value
                    }
                }
            }
        """

        result = executor.execute(test_query)

        expected = {"root": {"root": {"value": 5}}}
        assert not result.errors
        assert result.data == expected

    def test_field_filter(self):
        # noinspection PyUnusedLocal
        class Root:
            @field
            def name(self) -> str:
                return "rob"

            @field({"tags": ["admin"]})
            def social_security_number(self) -> int:
                return 56

        api = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=["admin"])])
        admin_api = GraphQLAPI(root_type=Root)

        api_executor = api.executor()
        admin_api_executor = admin_api.executor()

        test_query = "query GetName { name }"
        test_admin_query = "query GetSocialSecurityNumber { socialSecurityNumber }"

        result = api_executor.execute(test_query)

        assert not result.errors
        assert result.data == {"name": "rob"}

        result = admin_api_executor.execute(test_admin_query)

        assert not result.errors
        assert result.data == {"socialSecurityNumber": 56}

        result = api_executor.execute(test_admin_query)

        assert result.errors

    def test_property(self):
        api = GraphQLAPI()

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            def __init__(self):
                self._test_property = 5

            @property
            @api.field
            def test_property(self) -> int:
                return self._test_property

            # noinspection PyPropertyDefinition
            @test_property.setter
            @api.field(mutable=True)
            def test_property(self, value: int) -> int:
                self._test_property = value
                return self._test_property

        executor = api.executor()

        test_query = """
            query GetTestProperty {
                testProperty
            }
        """

        result = executor.execute(test_query)

        expected = {"testProperty": 5}
        assert not result.errors
        assert result.data == expected

        test_mutation = """
            mutation SetTestProperty {
                testProperty(value: 10)
            }
        """

        result = executor.execute(test_mutation)

        expected = {"testProperty": 10}
        assert not result.errors
        assert result.data == expected

    def test_interface(self):
        api = GraphQLAPI()

        @api.type(interface=True)
        class Animal:
            @api.field
            def planet(self) -> str:
                return "Earth"

            @api.field
            def name(self) -> str:
                return "GenericAnimalName"

        class Dog(Animal):
            @api.field
            def name(self) -> str:
                return "Floppy"

        class Human(Animal):
            @api.field
            def name(self) -> str:
                return "John"

            @api.field
            def pet(self) -> Dog:
                return Dog()

        class Root:
            @api.field
            def best_animal(self, task: str = "bark") -> Animal:
                if task == "bark":
                    return Dog()
                return Human()

        api.root_type = Root
        executor = api.executor()

        test_query = """
            query GetAnimal {
                bestAnimal(task: "%s") {
                    planet
                    name
                    ... on Human {
                        pet {
                            name
                        }
                    }
                }
            }
        """

        result = executor.execute(test_query % "bark")

        expected = {"bestAnimal": {"planet": "Earth", "name": "Floppy"}}

        assert not result.errors
        assert result.data == expected

        result = executor.execute(test_query % "making a cake")

        expected = {
            "bestAnimal": {"planet": "Earth", "name": "John", "pet": {"name": "Floppy"}}
        }
        assert not result.errors
        assert result.data == expected

    def test_multiple_interfaces(self):
        api = GraphQLAPI()

        @api.type(interface=True)
        class Animal:
            @api.field
            def name(self) -> str:
                return "GenericAnimalName"

        @api.type(interface=True)
        class Object:
            @api.field
            def weight(self) -> int:
                return 100

        @api.type(interface=True)
        class Responds:
            # noinspection PyUnusedLocal
            @api.field
            def ask_question(self, text: str) -> str:
                return "GenericResponse"

        class BasicRespondMixin(Responds, Animal):
            @api.field
            def ask_question(self, text: str) -> str:
                return f"Hello, im {self.name()}!"

        class Dog(BasicRespondMixin, Animal, Object):
            @api.field
            def name(self) -> str:
                return "Floppy"

            @api.field
            def weight(self) -> int:
                return 20

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def animal(self) -> Animal:
                return Dog()

        executor = api.executor()

        test_query = """
            query GetDog {
                animal {
                    name
                    ... on Dog {
                        weight
                        response: askQuestion(text: "Whats your name?")
                    }
                }
            }
        """

        result = executor.execute(test_query)

        expected = {
            "animal": {"name": "Floppy", "weight": 20, "response": "Hello, im Floppy!"}
        }

        assert not result.errors
        assert result.data == expected

    def test_dataclass(self):
        api = GraphQLAPI()

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        @dataclass
        class Root:
            hello_world: str = "hello world"
            hello_world_optional: Optional[str] = None

        executor = api.executor()

        test_query = """
            query HelloWorld {
                helloWorld
                helloWorldOptional
            }
        """

        result = executor.execute(test_query)

        expected = {"helloWorld": "hello world", "helloWorldOptional": None}
        assert not result.errors
        assert result.data == expected

    def test_mutation(self):
        api = GraphQLAPI()

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field(mutable=True)
            def hello_world(self) -> str:
                return "hello world"

        executor = api.executor()

        test_query = """
            mutation HelloWorld {
                helloWorld
            }
        """

        result = executor.execute(test_query)

        expected = {"helloWorld": "hello world"}
        assert not result.errors
        assert result.data == expected

    def test_deep_mutation(self):
        api = GraphQLAPI()

        class Math:
            @api.field
            def square(self, number: int) -> int:
                return number * number

            @api.field(mutable=True)
            def create_square(self, number: int) -> int:
                return number * number

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def math(self) -> Math:
                return Math()

        executor = api.executor()

        test_query = (
            """
        mutation GetTestSquare {
            math {
                square: createSquare(number: %d)
            }
        }
        """
            % 5
        )

        result = executor.execute(test_query)

        expected = {"math": {"square": 25}}
        assert not result.errors
        assert result.data == expected

    def test_print(self):
        api = GraphQLAPI()

        class Math:
            @api.field
            def square(self, number: int) -> int:
                return number * number

            @api.field(mutable=True)
            def create_square(self, number: int) -> int:
                return number * number

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def math(self) -> Math:
                return Math()

        schema, _ = api.build_schema()

        schema_str = print_schema(schema)
        schema_str = schema_str.strip().replace(" ", "")

        expected_schema_str = """
            schema {
                query: Root
                mutation: RootMutable
            }

            type Root {
                math: Math!
            }

            type RootMutable {
                math: MathMutable!
            }

            type Math {
                square(number: Int!): Int!
            }

            type MathMutable {
                createSquare(number: Int!): Int!
                square(number: Int!): Int!
            }
        """.strip().replace(
            " ", ""
        )

        assert set(schema_str.split("}")) == set(expected_schema_str.split("}"))

    # noinspection PyUnusedLocal
    def test_middleware(self):
        api = GraphQLAPI()

        was_called = []

        @api.type(is_root_type=True)
        class Root:
            @api.field({"test_meta": "hello_meta"})
            def test_query(self, test_string: Optional[str] = None) -> str:
                if test_string == "hello":
                    return "world"
                return "not_possible"

        def _test_middleware(next_, root, info, **args):
            if info.context.field.meta.get("test_meta") == "hello_meta":
                if info.context.request.args.get("test_string") == "hello":
                    was_called.append(True)
                    return next_(root, info, **args)
            return "possible"

        api.middleware = [_test_middleware]

        executor = api.executor()

        test_mutation = """
            query TestMiddlewareQuery {
                testQuery(testString: "hello")
            }
        """

        result = executor.execute(test_mutation)

        assert was_called

        expected = {"testQuery": "world"}
        assert not result.errors
        assert result.data == expected

        test_mutation = """
            query TestMiddlewareQuery {
                testQuery(testString: "not_hello")
            }
        """

        result = executor.execute(test_mutation)

        expected = {"testQuery": "possible"}
        assert not result.errors
        assert result.data == expected

    # noinspection PyUnusedLocal
    def test_input(self):
        api = GraphQLAPI()

        class TestInputObject:
            """
            A calculator
            """

            def __init__(self, a_value: int):
                super().__init__()
                self._value = a_value

            @api.field
            def value_squared(self) -> int:
                return self._value * self._value

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def square(self, value: TestInputObject) -> TestInputObject:
                return value

        executor = api.executor()

        test_input_query = """
            query TestInputQuery {
                square(value: {aValue: 14}){
                    valueSquared
                }
            }
        """

        result = executor.execute(test_input_query)

        expected = {"square": {"valueSquared": 196}}
        assert not result.errors
        assert result.data == expected

    # noinspection PyUnusedLocal
    def test_enum(self):
        api = GraphQLAPI()

        class AnimalType(enum.Enum):
            dog = "dog"
            cat = "cat"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def opposite(self, animal: AnimalType) -> AnimalType:
                assert isinstance(animal, AnimalType)

                if animal == AnimalType.dog:
                    return AnimalType.cat

                return AnimalType.dog

        executor = api.executor()

        test_enum_query = """
            query TestEnum {
                opposite(animal: dog)
            }
        """

        result = executor.execute(test_enum_query)
        expected = {"opposite": "cat"}

        assert result.data == expected

    def test_list(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def a_list(self) -> List[str]:
                return ["a", "b", "c"]

            @api.field
            def a_optional_list(self) -> Optional[List[str]]:
                return None

            @api.field
            def a_list_of_optionals(self) -> List[Optional[str]]:
                return [None, None]

            @api.field
            def a_optional_list_of_optionals(self) -> Optional[List[Optional[str]]]:
                return None

        executor = api.executor()

        test_enum_query = """
            query TestEnum {
                aList
                aOptionalList
                aListOfOptionals
                aOptionalListOfOptionals
            }
        """

        result = executor.execute(test_enum_query)

        assert result.data == {
            "aList": ["a", "b", "c"],
            "aOptionalList": None,
            "aListOfOptionals": [None, None],
            "aOptionalListOfOptionals": None,
        }

    # noinspection PyUnusedLocal
    def test_enum_list(self):
        api = GraphQLAPI()

        class AnimalType(enum.Enum):
            dog = "dog"
            cat = "cat"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def all(self, animals: List[AnimalType]) -> List[AnimalType]:
                assert all(isinstance(animal, AnimalType) for animal in animals)

                return animals

        executor = api.executor()

        test_enum_query = """
            query TestEnum {
                all(animals: [dog, cat])
            }
        """

        result = executor.execute(test_enum_query)
        expected = {"all": ["dog", "cat"]}

        assert result.data == expected

    def test_optional_enum(self):
        api = GraphQLAPI()

        class AnimalType(enum.Enum):
            dog = "dog"
            cat = "cat"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def opposite(
                self, animal: Optional[AnimalType] = None
            ) -> Optional[AnimalType]:
                if animal is None:
                    return None

                if animal == AnimalType.dog:
                    return AnimalType.cat

                return AnimalType.dog

        executor = api.executor()

        test_enum_query = """
                query TestEnum {
                    opposite
                }
            """

        result = executor.execute(test_enum_query)
        expected = {"opposite": None}
        assert not result.errors

        assert result.data == expected

    # noinspection PyUnusedLocal
    def test_functional_enum(self):
        api = GraphQLAPI()

        AnimalType = enum.Enum("AnimalType", ["dog", "cat"])

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def opposite(self, animal: AnimalType) -> AnimalType:
                assert isinstance(animal, AnimalType)

                if animal == AnimalType.dog:
                    return AnimalType.cat

                return AnimalType.dog

        executor = api.executor()

        test_enum_query = """
            query TestEnum {
                opposite(animal: dog)
            }
        """

        result = executor.execute(test_enum_query)
        expected = {"opposite": "cat"}

        assert result.data == expected

    def test_string_enum(self):
        """Test string enum functionality"""
        api = GraphQLAPI()

        class Timeframe(str, enum.Enum):
            """A timeframe."""
            LAST_30_DAYS = "last_30_days"
            ALL_TIME = "all_time"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def get_timeframe(self) -> Timeframe:
                return Timeframe.LAST_30_DAYS

            @api.field
            def echo_timeframe(self, timeframe: Timeframe) -> Timeframe:
                return timeframe

        executor = api.executor()

        # Test return value
        query1 = """
            query {
                getTimeframe
            }
        """
        result1 = executor.execute(query1)
        assert result1.data == {'getTimeframe': 'LAST_30_DAYS'}

        # Test input argument
        query2 = """
            query {
                echoTimeframe(timeframe: ALL_TIME)
            }
        """
        result2 = executor.execute(query2)
        assert result2.data == {'echoTimeframe': 'ALL_TIME'}

    def test_string_enum_with_regular_enum(self):
        """Test that both string enums and regular enums work together"""
        api = GraphQLAPI()

        class StringStatus(str, enum.Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"

        class RegularPriority(enum.Enum):
            LOW = 1
            MEDIUM = 2
            HIGH = 3

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def get_status(self) -> StringStatus:
                return StringStatus.ACTIVE

            @api.field
            def get_priority(self) -> RegularPriority:
                return RegularPriority.HIGH

            @api.field
            def combine(self, status: StringStatus, priority: RegularPriority) -> str:
                return f"{status.value}:{priority.value}"

        executor = api.executor()

        query = """
            query {
                getStatus
                getPriority
                combine(status: ACTIVE, priority: HIGH)
            }
        """

        result = executor.execute(query)
        assert result.data == {
            'getStatus': 'ACTIVE',
            'getPriority': 'HIGH',
            'combine': 'active:3'
        }

    def test_string_enum_optional(self):
        """Test optional string enum"""
        api = GraphQLAPI()

        class Color(str, enum.Enum):
            RED = "red"
            GREEN = "green"
            BLUE = "blue"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def get_color(self, color: Optional[Color] = None) -> str:
                if color:
                    return f"Color is {color.value}"
                return "No color specified"

        executor = api.executor()

        # Test with value
        query1 = """
            query {
                getColor(color: RED)
            }
        """
        result1 = executor.execute(query1)
        assert result1.data == {'getColor': 'Color is red'}

        # Test without value
        query2 = """
            query {
                getColor
            }
        """
        result2 = executor.execute(query2)
        assert result2.data == {'getColor': 'No color specified'}

    def test_string_enum_list(self):
        """Test list of string enums"""
        api = GraphQLAPI()

        class Tag(str, enum.Enum):
            PYTHON = "python"
            JAVASCRIPT = "javascript"
            RUST = "rust"
            GO = "go"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def get_tags(self) -> List[Tag]:
                return [Tag.PYTHON, Tag.RUST]

            @api.field
            def filter_tags(self, tags: List[Tag]) -> List[Tag]:
                # Return only tags that start with 'P' or 'R'
                return [t for t in tags if t.value[0] in ('p', 'r')]

        executor = api.executor()

        # Test returning list
        query1 = """
            query {
                getTags
            }
        """
        result1 = executor.execute(query1)
        assert result1.data == {'getTags': ['PYTHON', 'RUST']}

        # Test list as input
        query2 = """
            query {
                filterTags(tags: [PYTHON, JAVASCRIPT, RUST, GO])
            }
        """
        result2 = executor.execute(query2)
        assert result2.data == {'filterTags': ['PYTHON', 'RUST']}

    def test_string_enum_argument(self):
        api = GraphQLAPI()

        class Tag(str, enum.Enum):
            PYTHON = "python"
            JAVASCRIPT = "javascript"
            RUST = "rust"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def check_tag(self, tag: Tag) -> bool:
                if isinstance(tag, Tag):
                    return True
                return False

        executor = api.executor()

        query = """
            query CheckTag($tag: TagEnum!) {
                checkTag(tag: $tag)
            }
            """
        result = executor.execute(query, variables={'tag': Tag.PYTHON.name})
        assert result.data == {'checkTag': True}

    def test_string_enum_variable_rejects_value_literal(self):
        api = GraphQLAPI()

        class Tag(str, enum.Enum):
            PYTHON = "python"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def check(self, tag: Tag) -> bool:
                return isinstance(tag, Tag)

        executor = api.executor()
        query = """
            query($tag: TagEnum!){
                check(tag: $tag)
            }
        """
        # Variable must be the NAME ("PYTHON"), not the underlying value ("python")
        result = executor.execute(query, variables={"tag": "python"})
        assert result.errors and "does not exist in 'TagEnum'" in result.errors[0].message

    def test_regular_enum_variable(self):
        api = GraphQLAPI()

        class Priority(enum.Enum):
            LOW = 1
            HIGH = 3

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def is_high(self, p: Priority) -> bool:
                return p is Priority.HIGH

        executor = api.executor()
        q = "query($p: PriorityEnum!){ isHigh(p: $p) }"
        result = executor.execute(q, variables={"p": "HIGH"})
        assert result.data == {"isHigh": True}

    def test_input_object_enum_default_and_override(self):
        api = GraphQLAPI()

        class Status(str, enum.Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"

        class Filter:
            def __init__(self, status: Status = Status.ACTIVE):
                self.status = status

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def get_status(self, flt: Filter) -> Status:
                return flt.status

        executor = api.executor()
        # Uses default from InputObject field
        r1 = executor.execute("query{ getStatus(flt: {}) }")
        assert not r1.errors and r1.data == {"getStatus": "ACTIVE"}

        # Override via variable with enum NAME
        q = "query($s: StatusEnum!){ getStatus(flt: {status: $s}) }"
        r2 = executor.execute(q, variables={"s": "INACTIVE"})
        assert r2.data == {"getStatus": "INACTIVE"}

    def test_string_enum_list_variable(self):
        api = GraphQLAPI()

        class Tag(str, enum.Enum):
            PYTHON = "python"
            RUST = "rust"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def echo(self, tags: List[Tag]) -> List[Tag]:
                assert all(isinstance(t, Tag) for t in tags)
                return tags

        executor = api.executor()
        q = "query($tags: [TagEnum!]!){ echo(tags: $tags) }"
        r = executor.execute(q, variables={"tags": ["PYTHON", "RUST"]})
        assert r.data == {"echo": ["PYTHON", "RUST"]}

    def test_optional_enum_undefined_vs_null(self):
        api = GraphQLAPI()

        class Color(str, enum.Enum):
            RED = "red"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def show(self, color: Optional[Color] = None) -> str:
                return "none" if color is None else color.value

        executor = api.executor()
        q = "query($c: ColorEnum){ show(color: $c) }"
        # Undefined variable
        r1 = executor.execute(q, variables={})
        assert r1.data == {"show": "none"}
        # Explicit null
        r2 = executor.execute(q, variables={"c": None})
        assert r2.data == {"show": "none"}

    def test_returning_underlying_value_maps_to_enum_name(self):
        api = GraphQLAPI()

        class Color(str, enum.Enum):
            RED = "red"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def color(self) -> Color:  # type: ignore[override]
                # Returning the underlying value should still serialize to NAME
                return "red"  # type: ignore[return-value]

        executor = api.executor()
        r = executor.execute("query{ color }")
        assert r.data == {"color": "RED"}

    def test_enum_variable_mixed_case_invalid(self):
        api = GraphQLAPI()

        class Tag(str, enum.Enum):
            PYTHON = "python"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def ok(self, tag: Tag) -> bool:
                return True

        executor = api.executor()
        q = "query($t: TagEnum!){ ok(tag: $t) }"
        res = executor.execute(q, variables={"t": "Python"})
        assert res.errors and "does not exist in 'TagEnum'" in res.errors[0].message

    # noinspection PyUnusedLocal
    def test_literal(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def get_count(self, period: Period) -> int:
                if period == "1d":
                    return 365

                return 0

        executor = api.executor()

        test_literal_query = """
            query TestEnum {
                getCount(period: "1d")
            }
        """

        result = executor.execute(test_literal_query)
        expected = {"getCount": 365}

        assert not result.errors
        assert result.data == expected

    # noinspection PyUnusedLocal
    def test_required(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def value(self, a_int: int) -> Optional[int]:
                return a_int

        executor = api.executor()

        test_input_query = """
            query TestOptionalQuery {
                value
            }
        """

        result = executor.execute(test_input_query)

        assert (
            result.errors
            and "is required, but it was not provided" in result.errors[0].message
        )

    # noinspection PyUnusedLocal
    def test_optional(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def value(self, a_int: int = 50) -> int:
                return a_int

        executor = api.executor()

        test_input_query = """
            query TestOptionalQuery {
                value
            }
        """

        result = executor.execute(test_input_query)

        expected = {"value": 50}
        assert not result.errors
        assert result.data == expected

    @pytest.mark.skipif(sys.version_info < (3, 10), reason="requires python3.10")
    def test_optional_311(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def value(self, a_int: Optional[int] = 50) -> Optional[int]:
                return a_int

        executor = api.executor()

        test_input_query = """
            query TestOptionalQuery {
                value
            }
        """

        result = executor.execute(test_input_query)

        expected = {"value": 50}
        assert not result.errors
        assert result.data == expected

    # noinspection PyUnusedLocal
    def test_union(self):
        api = GraphQLAPI()

        class Customer:
            @api.field
            def id(self) -> int:
                return 5

        class Owner:
            @api.field
            def name(self) -> str:
                return "rob"

        @api.type(is_root_type=True)
        class Bank:
            @api.field
            def owner_or_customer(
                self, owner: bool = True, none: bool = False
            ) -> Optional[Union[Owner, Customer]]:
                if owner:
                    return Owner()

                if none:
                    return None

                return Customer()

            @api.field
            def owner(self) -> Union[Owner]:  # type: ignore[type-arg]
                return Owner()

            @api.field
            def optional_owner_or_customer(
                self,
            ) -> List[Optional[Union[Owner, Customer]]]:
                return [None]

            @api.field
            def optional_owner(
                self,
            ) -> List[Optional[Union[Owner]]]:  # type: ignore[type-arg]
                return [None]

        executor = api.executor()

        test_owner_query = """
            query TestOwnerUnion {
                ownerOrCustomer {
                    ... on Owner {
                      name
                    }
                }
            }
        """

        owner_expected = {"ownerOrCustomer": {"name": "rob"}}

        owner_result = executor.execute(test_owner_query)
        assert not owner_result.errors
        assert owner_result.data == owner_expected

        test_customer_query = """
            query TestCustomerUnion {
                ownerOrCustomer(owner: false) {
                    ... on Customer {
                      id
                    }
                }
            }
        """

        customer_expected = {"ownerOrCustomer": {"id": 5}}

        customer_result = executor.execute(test_customer_query)
        assert not customer_result.errors
        assert customer_result.data == customer_expected

        test_none_query = """
            query TestCustomerUnion {
                ownerOrCustomer(owner: false, none: true) {
                    ... on Customer {
                      id
                    }
                }
            }
        """

        none_expected = {"ownerOrCustomer": None}

        none_result = executor.execute(test_none_query)
        assert not none_result.errors
        assert none_result.data == none_expected

        test_union_single_type_query = """
            query TestOwnerUnion {
                owner {
                    ... on Owner {
                      name
                    }
                }
            }
        """

        single_type_query_expected = {"owner": {"name": "rob"}}

        single_type_query_result = executor.execute(test_union_single_type_query)
        assert not single_type_query_result.errors
        assert single_type_query_result.data == single_type_query_expected

        schema, _ = api.build_schema()

        # Check that single type unions was sucesfully created as a union type.
        assert (
            schema is not None
            and schema.query_type is not None
            and schema.query_type.fields["owner"].type.of_type.name == "OwnerUnion"
        )

        test_optional_list_union_query = """
            query TestOwnerUnion {
                optionalOwnerOrCustomer {
                    ... on Owner {
                      name
                    }
                }
            }
        """
        assert (
            schema is not None and schema.query_type is not None
        )  # Add check here as well
        return_type = schema.query_type.fields[
            "optionalOwnerOrCustomer"
        ].type.of_type.of_type
        assert isinstance(return_type, GraphQLUnionType)

        optional_list_union_query_result = executor.execute(
            test_optional_list_union_query
        )
        assert not optional_list_union_query_result.errors
        assert optional_list_union_query_result.data == {
            "optionalOwnerOrCustomer": [None]
        }

    # noinspection PyUnusedLocal
    def test_non_null(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def non_nullable(self) -> int:
                # noinspection PyTypeChecker
                return None  # type: ignore[return-value]

            @api.field
            def nullable(self) -> Optional[int]:
                return None

        executor = api.executor()

        test_non_null_query = """
            query TestNonNullQuery {
                nonNullable
            }
        """

        non_null_result = executor.execute(test_non_null_query)

        assert non_null_result.errors

        test_null_query = """
            query TestNullQuery {
                nullable
            }
        """

        expected = {"nullable": None}

        null_result = executor.execute(test_null_query)
        assert not null_result.errors
        assert null_result.data == expected

    # noinspection PyUnusedLocal
    def test_context(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def has_context(self, context: GraphQLContext) -> bool:
                return bool(context)

        executor = api.executor()

        test_query = """
            query HasContext {
                hasContext
            }
        """

        expected = {"hasContext": True}

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data == expected

    star_wars_api_url = "https://swapi-graphql.netlify.app/.netlify/functions/index"

    # noinspection DuplicatedCode,PyUnusedLocal
    @pytest.mark.skipif(
        not available(star_wars_api_url),
        reason=f"The star wars API '{star_wars_api_url}' is unavailable",
    )
    def test_remote_get(self):
        api = GraphQLAPI()

        RemoteAPI = GraphQLRemoteExecutor(url=self.star_wars_api_url)

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def star_wars(self, context: GraphQLContext) -> RemoteAPI:  # type: ignore[valid-type]
                assert (
                    context.request is not None
                ), "GraphQLContext.request cannot be None"
                assert context.field is not None, "GraphQLContext.field cannot be None"
                operation = context.request.info.operation.operation
                field_query_details = context.field.query
                redirected_query = operation.value + " " + field_query_details
                _result = RemoteAPI.execute(query=redirected_query)

                if _result.errors:
                    raise GraphQLError(str(_result.errors))

                return _result.data

        executor = api.executor()

        test_query = """
            query GetAllFilms {
                starWars {
                  allFilms {
                     totalCount
                  }
                }
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data is not None
        assert (
            result.data.get("starWars", {}).get("allFilms", {}).get("totalCount", {})
            >= 6
        )

    pokemon_graphql_url = "https://graphqlpokemon.favware.tech/v8"

    # noinspection DuplicatedCode
    @pytest.mark.skipif(
        not available(pokemon_graphql_url),
        reason=f"The Pokemon API '{pokemon_graphql_url}' is unavailable",
    )
    def test_remote_post(self):
        api = GraphQLAPI()

        RemoteAPI = GraphQLRemoteExecutor(
            url=self.pokemon_graphql_url, http_method="POST"
        )

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def pokemon(self, context: GraphQLContext) -> RemoteAPI:  # type: ignore[valid-type]
                assert (
                    context.request is not None
                ), "GraphQLContext.request cannot be None"
                assert context.field is not None, "GraphQLContext.field cannot be None"
                operation = context.request.info.operation.operation
                field_query_details = context.field.query
                redirected_query = operation.value + " " + field_query_details

                result_ = RemoteAPI.execute(query=redirected_query)

                if result_.errors:
                    raise GraphQLError(str(result_.errors))

                return result_.data

        executor = api.executor()

        test_query = """
            query getPokemon {
                pokemon {
                    getPokemon(pokemon: pikachu) {
                        types {
                            name
                        }
                    }
                }
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data is not None

        pokemon_data = result.data.get("pokemon")
        assert pokemon_data is not None, "Expected 'pokemon' key in result data"
        pokemon = pokemon_data.get("getPokemon")
        assert pokemon is not None, "Expected 'getPokemon' key in pokemon data"

        assert pokemon.get("types")[0].get("name") == "Electric"

    @pytest.mark.skipif(
        not available(pokemon_graphql_url),
        reason=f"The pokemon API '{pokemon_graphql_url}' is unavailable",
    )
    def test_remote_post_helper(self):
        api = GraphQLAPI()

        RemoteAPI = GraphQLRemoteExecutor(
            url=self.pokemon_graphql_url, http_method="POST"
        )

        # noinspection PyUnusedLocal
        @api.type(is_root_type=True)
        class Root:
            @api.field
            def graphql(self, context: GraphQLContext) -> RemoteAPI:  # type: ignore[valid-type]
                return remote_execute(executor=RemoteAPI, context=context)

        executor = api.executor()

        test_query = """
            query getPokemon {
                graphql {
                    getPokemon(pokemon: pikachu) {
                        types {
                            name
                        }
                    }
                }
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data is not None

        graphql_data = result.data.get("graphql")
        assert graphql_data is not None, "Expected 'graphql' key in result data"
        pokemon = graphql_data.get("getPokemon")
        assert pokemon is not None, "Expected 'getPokemon' key in graphql data"

        assert pokemon.get("types")[0].get("name") == "Electric"

    # noinspection PyUnusedLocal
    def test_executor_to_ast(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def hello(self) -> str:
                return "hello world"

        executor = api.executor()

        schema = executor_to_ast(executor)

        # noinspection PyProtectedMember
        assert schema.type_map.keys() == executor.schema.type_map.keys()

    def test_root_type_delegate(self):
        api = GraphQLAPI()

        updated_schema = GraphQLSchema()

        @api.type(is_root_type=True)
        class Root(GraphQLRootTypeDelegate):
            was_called = False
            input_schema = None

            @classmethod
            def validate_graphql_schema(cls, schema: GraphQLSchema) -> GraphQLSchema:
                cls.was_called = True
                cls.input_schema = schema

                return updated_schema

            @api.field
            def hello(self) -> str:
                return "hello world"

        schema = api.build_schema()[0]

        assert Root.was_called
        assert Root.input_schema
        assert schema == updated_schema

    def test_schema_subclass(self):
        class Interface:
            @field
            def hello(self) -> str:
                raise NotImplementedError()

            @field(mutable=True)
            def hello_mutable(self) -> str:
                raise NotImplementedError()

            @field(mutable=True)
            def hello_changed(self) -> str:
                raise NotImplementedError()

        class Implementation(Interface):
            count = 0

            def hello(self) -> str:
                return "hello world"

            def hello_mutable(self) -> str:
                self.count += 1
                return f"hello {self.count}"

            @field
            def hello_changed(self) -> str:
                return "hello world"

        api = GraphQLAPI(root_type=Implementation)

        executor = api.executor()

        test_query = """
            query {
                hello
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data is not None and result.data["hello"] == "hello world"

        test_query = """
            mutation {
                helloMutable
            }
        """
        result = executor.execute(test_query)
        assert not result.errors
        assert result.data is not None and result.data["helloMutable"] == "hello 1"

        test_query = """
            query {
                helloChanged
            }
        """
        result = executor.execute(test_query)
        assert not result.errors
        assert result.data is not None and result.data["helloChanged"] == "hello world"

    def test_class_update(self):
        @dataclass
        class Person:
            name: str

        class GreetInterface:
            @field
            def hello(self, person: Person) -> str:
                raise NotImplementedError()

        class HashablePerson(Person):
            def __hash__(self):
                return hash(self.name)

        class Implementation(GreetInterface):
            def hello(self, person: HashablePerson) -> str:
                return f"hello {hash(person)}"

        api = GraphQLAPI(root_type=Implementation)

        executor = api.executor()

        test_query = """
            query {
                hello(person:{name:"rob"})
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert (
            result.data is not None and result.data["hello"] == f"hello {hash('rob')}"
        )

    def test_class_update_same_name(self):
        @dataclass
        class PersonInterface:
            name: str

        class GreetInterface:
            @field
            def hello(self, person: PersonInterface) -> str:
                raise NotImplementedError()

        # noinspection PyRedeclaration
        class Person(PersonInterface):
            def __hash__(self):
                return hash(self.name)

        class Implementation(GreetInterface):
            def hello(self, person: Person) -> str:
                return f"hello {hash(person)}"

        api = GraphQLAPI(root_type=Implementation)

        executor = api.executor()

        test_query = """
            query {
                hello(person:{name:"rob"})
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert (
            result.data is not None and result.data["hello"] == f"hello {hash('rob')}"
        )

    def test_debug_root_type_issue(self):
        """
        Debug test to understand why root type isn't being set properly
        """
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class SimpleRoot:
            @api.field
            def hello(self) -> str:
                return "world"

        print("\n=== DEBUG: Root type after decorator ===")
        print("api.root_type:", api.root_type)
        print("SimpleRoot class:", SimpleRoot)

        schema, _ = api.build_schema()
        print(
            "Schema query type:",
            schema.query_type.name if schema.query_type else "None",
        )
        if schema.query_type:
            print("Query fields:", list(schema.query_type.fields.keys()))

        # Test the working pattern
        executor = api.executor()
        result = executor.execute("query { hello }")
        print("Query result:", result.data)
        print("Query errors:", result.errors)

    def test_filter_removes_all_root_fields_causes_placeholder(self):
        """
        Test that when ALL fields in the root type are filtered out,
        the root type name is preserved and a meaningful schema field is provided.
        """

        # Create a root type where ALL fields will be filtered
        class Root:
            @field({"tags": ["admin"]})
            def admin_only_field(self) -> str:
                return "admin data"

            @field({"tags": ["private"]})
            def private_only_field(self) -> str:
                return "private data"

        # Test with filters that remove ALL root fields
        from graphql_api.reduce import TagFilter

        filtered_api = GraphQLAPI(
            root_type=Root, filters=[TagFilter(tags=["admin", "private"])]
        )
        filtered_schema, _ = filtered_api.build_schema()

        # Verify the fix: root type name should be preserved
        assert filtered_schema.query_type is not None
        assert (
            filtered_schema.query_type.name == "Root"
        ), "Root type name should be preserved"
        assert (
            "_schema" in filtered_schema.query_type.fields
        ), "Should have _schema field"

        # Test that the schema field works
        executor = filtered_api.executor()
        result = executor.execute("query { _schema }")

        assert not result.errors, "Schema info query should work"
        assert (
            result.data and "filtered" in result.data["_schema"].lower()
        ), "Should indicate filtered state"

    def test_filter_behavior_comparison(self):
        """
        Test filtering behavior with mixed scenarios:
        - Object types with some fields filtered should remain accessible
        - Object types with all fields filtered should be removed (even in PRESERVE_TRANSITIVE mode due to GraphQL constraints)
        - Parent fields should be handled appropriately
        """

        # Create the types first
        class UserData:
            @field
            def public_info(self) -> str:
                return "This is public"

            @field({"tags": ["private"]})
            def private_info(self) -> str:
                return "This is private"

        # Create an object type where ALL fields will be filtered
        class AdminData:
            @field({"tags": ["admin"]})
            def secret_key(self) -> str:
                return "secret"

            @field({"tags": ["admin"]})
            def admin_token(self) -> str:
                return "token"

        class Root:
            @field
            def user_data(self) -> UserData:
                return UserData()

            @field
            def admin_data(self) -> AdminData:
                return AdminData()

        # Test with filters that remove admin fields using strict mode (preserve_transitive=False)
        from graphql_api.reduce import TagFilter

        filtered_api = GraphQLAPI(
            root_type=Root,
            filters=[TagFilter(tags=["admin"], preserve_transitive=False)],
        )
        filtered_schema, _ = filtered_api.build_schema()
        executor = filtered_api.executor()

        # UserData should work - has remaining fields
        result1 = executor.execute(
            """
            query { userData { publicInfo privateInfo } }
        """
        )
        assert not result1.errors
        assert result1.data == {
            "userData": {
                "publicInfo": "This is public",
                "privateInfo": "This is private",
            }
        }

        # AdminData should be completely removed - all fields filtered and no way to preserve empty types
        result2 = executor.execute(
            """
            query { adminData { secretKey } }
        """
        )
        assert result2.errors
        assert "Cannot query field 'adminData'" in str(result2.errors[0])

        # Verify schema structure
        assert filtered_schema.query_type is not None
        assert filtered_schema.query_type.name == "Root"
        assert "userData" in filtered_schema.query_type.fields
        assert (
            "adminData" not in filtered_schema.query_type.fields
        )  # Removed because AdminData has no fields
        assert "UserData" in filtered_schema.type_map
        assert "AdminData" not in filtered_schema.type_map  # Removed

    def test_filter_should_preserve_object_types_with_remaining_fields(self):
        """
        Test that object types with some fields filtered remain accessible
        with only the filtered fields removed.
        """

        class UserData:
            @field
            def public_info(self) -> str:
                return "This is public"

            @field({"tags": ["private"]})
            def private_info(self) -> str:
                return "This is private"

        class Root:
            @field
            def user_data(self) -> UserData:
                return UserData()

        # Create filtered API
        from graphql_api.reduce import TagFilter

        filtered_api = GraphQLAPI(root_type=Root, filters=[TagFilter(tags=["private"])])

        # Test that the object type with remaining fields should still be accessible
        schema, _ = filtered_api.build_schema()

        # Verify schema structure
        assert schema.query_type is not None
        assert schema.query_type.name == "Root"
        assert "userData" in schema.query_type.fields
        assert "UserData" in schema.type_map

        # Test query execution
        executor = filtered_api.executor()

        # Should work for accessible field
        result = executor.execute(
            """
            query GetUserData {
                userData {
                    publicInfo
                }
            }
        """
        )
        assert not result.errors
        assert result.data == {"userData": {"publicInfo": "This is public"}}

        # Should fail for filtered field
        private_result = executor.execute(
            """
            query GetPrivateData {
                userData {
                    privateInfo
                }
            }
        """
        )
        assert private_result.errors
        assert "Cannot query field 'privateInfo'" in str(private_result.errors[0])

        # Verify UserData type has correct fields
        user_data_type = schema.type_map["UserData"]
        assert isinstance(user_data_type, GraphQLObjectType)
        assert "publicInfo" in user_data_type.fields
        assert "privateInfo" not in user_data_type.fields

    def test_filter_object_type_field_removal_issue(self):
        """
        Test filtering behavior for complex nested object types.
        Verifies that object types with remaining fields are preserved
        and only filtered fields are removed. Types with no remaining fields
        are removed entirely due to GraphQL constraints.
        """

        # Define types without API instance to avoid decorator conflicts
        class UserPreferences:
            @field
            def theme(self) -> str:
                return "dark"

            @field
            def language(self) -> str:
                return "en"

            @field({"tags": ["admin"]})
            def admin_settings(self) -> str:
                return "admin-only-settings"

        class UserProfile:
            @field
            def display_name(self) -> str:
                return "John Doe"

            @field
            def bio(self) -> str:
                return "Software developer"

            @field({"tags": ["private"]})
            def social_security(self) -> str:
                return "123-45-6789"

        class User:
            @field
            def username(self) -> str:
                return "johndoe"

            @field
            def email(self) -> str:
                return "john@example.com"

            @field
            def profile(self) -> UserProfile:
                return UserProfile()

            @field
            def preferences(self) -> UserPreferences:
                return UserPreferences()

        # Object type where ALL fields are filtered
        class AdminOnlyData:
            @field({"tags": ["admin"]})
            def secret_key(self) -> str:
                return "secret"

            @field({"tags": ["admin"]})
            def admin_token(self) -> str:
                return "token"

        class Root:
            @field
            def user(self) -> User:
                return User()

            @field
            def admin_data(self) -> AdminOnlyData:
                return AdminOnlyData()

        # Create filtered API that removes admin and private fields using strict mode (preserve_transitive=False)
        from graphql_api.reduce import TagFilter

        filtered_api = GraphQLAPI(
            root_type=Root,
            filters=[TagFilter(tags=["admin", "private"], preserve_transitive=False)],
        )
        executor = filtered_api.executor()

        # Test nested query with remaining fields
        result = executor.execute(
            """
            query GetUser {
                user {
                    username
                    email
                    profile {
                        displayName
                        bio
                    }
                    preferences {
                        theme
                        language
                    }
                }
            }
        """
        )

        expected = {
            "user": {
                "username": "johndoe",
                "email": "john@example.com",
                "profile": {"displayName": "John Doe", "bio": "Software developer"},
                "preferences": {"theme": "dark", "language": "en"},
            }
        }

        assert not result.errors
        assert result.data == expected

        # Test that filtered fields are not accessible
        result_filtered = executor.execute(
            """
            query GetFilteredData {
                user {
                    profile {
                        socialSecurity
                    }
                }
            }
        """
        )
        assert result_filtered.errors
        assert "Cannot query field 'socialSecurity'" in str(result_filtered.errors[0])

        # Test that object types with ALL fields filtered are completely removed
        result_admin = executor.execute(
            """
            query GetAdminData {
                adminData {
                    secretKey
                }
            }
        """
        )
        assert result_admin.errors
        assert "Cannot query field 'adminData'" in str(result_admin.errors[0])

        # Verify schema structure
        schema, _ = filtered_api.build_schema()
        type_map = schema.type_map

        # Types with remaining fields should exist
        assert "UserProfile" in type_map
        assert "UserPreferences" in type_map

        # Types with all fields filtered should be completely removed
        assert "AdminOnlyData" not in type_map

        # Root should have user field but not adminData field
        assert schema.query_type is not None
        root_fields = schema.query_type.fields
        assert "user" in root_fields
        assert "adminData" not in root_fields

        # Verify filtered fields are removed from types
        user_profile_type = type_map["UserProfile"]
        assert isinstance(user_profile_type, GraphQLObjectType)
        profile_fields = user_profile_type.fields
        assert "displayName" in profile_fields
        assert "bio" in profile_fields
        assert "socialSecurity" not in profile_fields

    def test_graphql_api_enum_behavior(self):
        api = GraphQLAPI()

        class Tag(str, enum.Enum):
            PYTHON = "python"
            JAVASCRIPT = "javascript"
            RUST = "rust"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def check_tag(self, tag: Tag) -> bool:
                return isinstance(tag, Tag)

        executor = api.executor()

        # Using the proper GraphQL Enum variable with the NAME
        query_enum = """
            query CheckTag($tag: TagEnum!) {
                checkTag(tag: $tag)
            }
        """
        result_enum = executor.execute(query_enum, variables={'tag': Tag.PYTHON.name})
        assert result_enum.data == {'checkTag': True}

        # Schema should contain TagEnum
        schema, _ = api.build_schema()
        assert 'TagEnum' in schema.type_map

        # Field argument type should be NonNull(TagEnum)
        assert schema.query_type is not None
        field = schema.query_type.fields['checkTag']
        arg_type = field.args['tag'].type
        from graphql import GraphQLNonNull, GraphQLEnumType
        assert isinstance(arg_type, GraphQLNonNull)
        assert isinstance(arg_type.of_type, GraphQLEnumType)
        assert arg_type.of_type.name == 'TagEnum'

        # Invalid variable using underlying value string should error
        bad = executor.execute(query_enum, variables={'tag': 'python'})
        assert bad.errors and "does not exist in 'TagEnum'" in bad.errors[0].message

    def test_graphql_api_enum_behavior_int(self):
        api = GraphQLAPI()

        class Tag(int, enum.Enum):
            PYTHON = 1
            JAVASCRIPT = 2
            RUST = 3

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def check_tag(self, tag: Tag) -> bool:
                return isinstance(tag, Tag)

        executor = api.executor()

        # Using the proper GraphQL Enum variable with the NAME
        query_enum = """
            query CheckTag($tag: TagEnum!) {
                checkTag(tag: $tag)
            }
        """
        result_enum = executor.execute(query_enum, variables={'tag': Tag.PYTHON.name})
        assert result_enum.data == {'checkTag': True}

        # Schema should contain TagEnum
        schema, _ = api.build_schema()
        assert 'TagEnum' in schema.type_map

        # Field argument type should be NonNull(TagEnum)
        assert schema.query_type is not None
        field = schema.query_type.fields['checkTag']
        arg_type = field.args['tag'].type
        from graphql import GraphQLNonNull, GraphQLEnumType
        assert isinstance(arg_type, GraphQLNonNull)
        assert isinstance(arg_type.of_type, GraphQLEnumType)
        assert arg_type.of_type.name == 'TagEnum'

        # Invalid variable using underlying value string should error
        bad = executor.execute(query_enum, variables={'tag': 'python'})
        assert bad.errors and "does not exist in 'TagEnum'" in bad.errors[0].message

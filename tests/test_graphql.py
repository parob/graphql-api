import enum
import sys

import pytest

from dataclasses import dataclass
from typing import Union, Optional, Literal, List

from graphql import GraphQLSchema
from requests.api import request
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout

# noinspection PyPackageRequirements
from graphql.utilities import print_schema

from graphql_api.utils import executor_to_ast
from graphql_api.error import GraphQLError
from graphql_api.context import GraphQLContext
from graphql_api.api import GraphQLAPI, GraphQLRootTypeDelegate
from graphql_api.reduce import TagFilter
from graphql_api.remote import GraphQLRemoteExecutor, remote_execute
from graphql_api.decorators import field


def available(url, method="GET"):
    try:
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
                person.age = age
                return person

            def __init__(self, name: str):
                self.name = name
                self.age = 20

            @api.field
            def name(self) -> str:
                return self.name

            @api.field
            def age(self) -> int:
                return self.age

        class Root:
            @api.field
            def person_info(self, person: Person) -> str:
                return person.name + " is " + str(person.age)

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

        schema, _ = api.graphql_schema()

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
            def test_query(self, test_string: str = None) -> str:
                if test_string == "hello":
                    return "world"
                return "not_possible"

        def test_middleware(next_, context):
            if context.field.meta.get("test_meta") == "hello_meta":
                if context.request.args.get("test_string") == "hello":
                    was_called.append(True)
                    return next_()
            return "possible"

        api.middleware = [test_middleware]

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

    # noinspection PyUnusedLocal
    def test_literal(self):
        api = GraphQLAPI()

        Period = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y"]

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
            def owner(self) -> Union[Owner]:
                return Owner()

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

        schema, _ = api.graphql_schema()

        # Check that single type unions was sucesfully created as a union type.
        assert schema.query_type.fields["owner"].type.of_type.name == "OwnerUnion"

    # noinspection PyUnusedLocal
    def test_non_null(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def non_nullable(self) -> int:
                # noinspection PyTypeChecker
                return None

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
            def star_wars(self, context: GraphQLContext) -> RemoteAPI:
                operation = context.request.info.operation.operation
                query = context.field.query
                redirected_query = operation.value + " " + query
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
            def pokemon(self, context: GraphQLContext) -> RemoteAPI:
                operation = context.request.info.operation.operation
                query = context.field.query
                redirected_query = operation.value + " " + query

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

        pokemon = result.data.get("pokemon").get("getPokemon")

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
            def graphql(self, context: GraphQLContext) -> RemoteAPI:
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

        pokemon = result.data.get("graphql").get("getPokemon")

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

        schema = api.graphql_schema()[0]

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
        assert result.data["hello"] == "hello world"

        test_query = """
            mutation {
                helloMutable
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data["helloMutable"] == "hello 1"

        test_query = """
            query {
                helloChanged
            }
        """

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data["helloChanged"] == "hello world"

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
        assert result.data["hello"] == f"hello {hash('rob')}"

    def test_class_update_same_name(self):
        @dataclass
        class Person:
            name: str

        class GreetInterface:
            @field
            def hello(self, person: Person) -> str:
                raise NotImplementedError()

        # noinspection PyRedeclaration
        class Person(Person):
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
        assert result.data["hello"] == f"hello {hash('rob')}"

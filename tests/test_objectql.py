import enum
from dataclasses import dataclass

from typing import Union, Optional

import pytest
from objectql.utils import executor_to_ast
from requests.api import request
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout

from objectql.decorators import query, mutation, interface
from objectql.error import ObjectQLError
from objectql.context import ObjectQLContext
from objectql.schema import ObjectQLSchemaBuilder
from objectql.reduce import TagFilter
from objectql.remote import ObjectQLRemoteExecutor


def available(url, method="GET"):
    try:
        request(method, url, timeout=5, verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout):
        return False

    return True


class TestGraphQL:

    def test_deep_query(self):
        api = ObjectQLSchemaBuilder()

        class Math:

            @query
            def test_square(self, number: int) -> int:
                return number * number

        class Root:

            @query
            def math(self) -> Math:
                return Math()

        api.root = Root
        executor = api.executor()

        test_query = '''
            query GetTestSquare {
                math {
                    square: testSquare(number: %d)
                }
            }
        ''' % 5

        result = executor.execute(test_query)

        expected = {
            "math": {
                "square": 25
            }
        }
        assert not result.errors
        assert result.data == expected

    def test_query_input(self):
        api = ObjectQLSchemaBuilder()

        class Person:

            def __init__(self, name: str):
                self.name = name

        class Root:

            @query
            def get_name(self, person: Person) -> str:
                return person.name

        api.root = Root
        executor = api.executor()

        test_query = '''
            query GetTestSquare {
                getName(person: { name: "steve" })
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "getName": "steve"
        }
        assert not result.errors
        assert result.data == expected

    def test_custom_query_input(self):
        api = ObjectQLSchemaBuilder()

        class Person:

            @classmethod
            def graphql_from_input(cls, age: int):
                person = Person(name="hugh")
                person.age = age
                return person

            def __init__(self, name: str):
                self.name = name
                self.age = 20

            @query
            def name(self) -> str:
                return self.name

            @query
            def age(self) -> int:
                return self.age

        class Root:

            @query
            def person_info(self, person: Person) -> str:
                return person.name + " is " + str(person.age)

        api.root = Root
        executor = api.executor()

        test_query = '''
            query GetPersonInfo {
                personInfo(person: { age: 30 })
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "personInfo": "hugh is 30"
        }
        assert not result.errors
        assert result.data == expected

    def test_runtime_field(self):
        api = ObjectQLSchemaBuilder()

        class Person:

            @classmethod
            def graphql_fields(cls):

                @query
                def age(self) -> int:
                    return self.hidden_age

                return [age]

            def __init__(self, age: int):
                self.hidden_age = age

        class Root:

            @query
            def thomas(self) -> Person:
                return Person(age=2)

        api.root = Root
        executor = api.executor()

        test_query = '''
            query GetThomasAge {
                thomas { age }
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "thomas": {
                "age": 2
            }
        }
        assert not result.errors
        assert result.data == expected

    def test_recursive_query(self):
        api = ObjectQLSchemaBuilder()

        class Root:

            @query
            def root(self) -> 'Root':
                return Root()

            @query
            def value(self) -> int:
                return 5

        api.root = Root
        executor = api.executor()

        test_query = '''
            query GetRecursiveRoot {
                root {
                    root {
                        value
                    }
                }
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "root": {
                "root":  {
                    "value": 5
                }
            }
        }
        assert not result.errors
        assert result.data == expected

    def test_field_filter(self):

        class Root:

            @query
            def name(self) -> str:
                return "rob"

            @query({"tags": ["admin"]})
            def social_security_number(self) -> int:
                return 56

        api = ObjectQLSchemaBuilder(root=Root, filters=[TagFilter(tags=["admin"])]).executor()
        admin_api = ObjectQLSchemaBuilder(root=Root).executor()

        test_query = "query GetName { name }"
        test_admin_query = "query GetSocialSecurityNumber { socialSecurityNumber }"

        result = api.execute(test_query)

        assert not result.errors
        assert result.data == {"name": "rob"}

        result = admin_api.execute(test_admin_query)

        assert not result.errors
        assert result.data == {"socialSecurityNumber": 56}

        result = api.execute(test_admin_query)

        assert result.errors

    def test_property(self):
        api = ObjectQLSchemaBuilder()

        class Root:

            def __init__(self):
                self._test_property = 5

            @property
            @query
            def test_property(self) -> int:
                return self._test_property

            # noinspection PyPropertyDefinition
            @test_property.setter
            @mutation
            def test_property(self, value: int) -> int:
                self._test_property = value
                return self._test_property

        api.root = Root
        executor = api.executor()

        test_query = '''
            query GetTestProperty {
                testProperty
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "testProperty": 5
        }
        assert not result.errors
        assert result.data == expected

        test_mutation = '''
            mutation SetTestProperty {
                testProperty(value: 10)
            }
        '''

        result = executor.execute(test_mutation)

        expected = {
            "testProperty": 10
        }
        assert not result.errors
        assert result.data == expected

    def test_interface(self):
        api = ObjectQLSchemaBuilder()

        @interface
        class Animal:

            @query
            def planet(self) -> str:
                return "Earth"

            @query
            def name(self) -> str:
                return "GenericAnimalName"

        class Dog(Animal):

            @query
            def name(self) -> str:
                return "Floppy"

        class Human(Animal):

            @query
            def name(self) -> str:
                return "John"

            @query
            def pet(self) -> Dog:
                return Dog()

        class Root:

            @query
            def best_animal(self, task: str = "bark") -> Animal:
                if task == "bark":
                    return Dog()
                return Human()

        api.root = Root
        executor = api.executor()

        test_query = '''
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
        '''

        result = executor.execute(test_query % "bark")

        expected = {
            "bestAnimal": {
                "planet": "Earth",
                "name": "Floppy"
            }
        }

        assert not result.errors
        assert result.data == expected

        result = executor.execute(test_query % "making a cake")

        expected = {
            "bestAnimal": {
                "planet": "Earth",
                "name": "John",
                "pet": {
                    "name": "Floppy"
                }
            }
        }
        assert not result.errors
        assert result.data == expected

    def test_multiple_interfaces(self):
        api = ObjectQLSchemaBuilder()

        @interface
        class Animal:

            @query
            def name(self) -> str:
                return "GenericAnimalName"

        @interface
        class Object:

            @query
            def weight(self) -> int:
                return 100

        @interface
        class Responds:

            # noinspection PyUnusedLocal
            @query
            def ask_question(self, text: str) -> str:
                return "GenericResponse"

        class BasicRespondMixin(Responds, Animal):

            @query
            def ask_question(self, text: str) -> str:
                return f"Hello, im {self.name()}!"

        class Dog(BasicRespondMixin, Animal, Object):

            @query
            def name(self) -> str:
                return "Floppy"

            @query
            def weight(self) -> int:
                return 20

        class Root:

            @query
            def animal(self) -> Animal:
                return Dog()

        api.root = Root
        executor = api.executor()

        test_query = '''
            query GetDog {
                animal {
                    name
                    ... on Dog {
                        weight
                        response: askQuestion(text: "Whats your name?")
                    }
                }
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "animal": {
                "name": "Floppy",
                "weight": 20,
                "response": "Hello, im Floppy!"
            }
        }

        assert not result.errors
        assert result.data == expected

    def test_dataclass(self):
        api = ObjectQLSchemaBuilder()

        @dataclass
        class Root:
            hello_world: str = "hello world"

        api.root = Root
        executor = api.executor()

        test_query = '''
            query HelloWorld {
                helloWorld
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "helloWorld": "hello world"
        }
        assert not result.errors
        assert result.data == expected

    def test_mutation(self):
        api = ObjectQLSchemaBuilder()

        class Root:

            @mutation
            def hello_world(self) -> str:
                return "hello world"

        api.root = Root
        executor = api.executor()

        test_query = '''
            mutation HelloWorld {
                helloWorld
            }
        '''

        result = executor.execute(test_query)

        expected = {
            "helloWorld": "hello world"
        }
        assert not result.errors
        assert result.data == expected

    def test_deep_mutation(self):
        api = ObjectQLSchemaBuilder()

        class Math:

            @query
            def square(self, number: int) -> int:
                return number * number

            @mutation
            def create_square(self, number: int) -> int:
                return number * number

        class Root:

            @query
            def math(self) -> Math:
                return Math()

        api.root = Root
        executor = api.executor()

        test_query = '''
        mutation GetTestSquare {
            math {
                square: createSquare(number: %d)
            }
        }
        ''' % 5

        result = executor.execute(test_query)

        expected = {
            "math": {
                "square": 25
            }
        }
        assert not result.errors
        assert result.data == expected

    def test_print(self):
        from graphql.utils import schema_printer

        api = ObjectQLSchemaBuilder()

        class Math:

            @query
            def square(self, number: int) -> int:
                return number * number

            @mutation
            def create_square(self, number: int) -> int:
                return number * number

        class Root:

            @query
            def math(self) -> Math:
                return Math()

        api.root = Root

        schema, _, _ = api.schema()

        schema_str = schema_printer.print_schema(schema)
        schema_str = schema_str.strip().replace(" ", "")

        expected_schema_str = '''
            schema {
                query: Root
                mutation: RootMutable
            }
                
            type Math {
                square(number: Int!): Int!
            }
            
            type MathMutable {
                createSquare(number: Int!): Int!
            }
            
            type Root {
                math: Math!
            }
            
            type RootMutable {
                math: MathMutable!
            }
        '''.strip().replace(" ", "")

        assert schema_str == expected_schema_str

    def test_middleware(self):
        api = ObjectQLSchemaBuilder()

        was_called = []

        class Root:
            @query({"test_meta": "hello_meta"})
            def test_query(self, test_string: str = None) -> str:
                if test_string == "hello":
                    return "world"
                return "not_possible"

        def test_middleware(next, context):
            if context.field.meta.get("test_meta") == "hello_meta":
                if context.request.args.get('test_string') == "hello":
                    return next()
            return "possible"

        def test_simple_middleware(next):
            was_called.append(True)
            return next()

        api.middleware.append(test_middleware)
        api.middleware.append(test_simple_middleware)

        api.root = Root
        executor = api.executor()

        test_mutation = '''
            query TestMiddlewareQuery {
                testQuery(testString: "hello")
            }
        '''

        result = executor.execute(test_mutation)

        assert was_called

        expected = {
            "testQuery": "world"
        }
        assert not result.errors
        assert result.data == expected

        test_mutation = '''
            query TestMiddlewareQuery {
                testQuery(testString: "not_hello")
            }
        '''

        result = executor.execute(test_mutation)

        expected = {
            "testQuery": "possible"
        }
        assert not result.errors
        assert result.data == expected

    def test_input(self):
        api = ObjectQLSchemaBuilder()

        class TestInputObject:
            """
            A calculator
            """

            def __init__(self, a_value: int):
                super().__init__()
                self._value = a_value

            @query
            def value_squared(self) -> int:
                return self._value * self._value

        class Root:
            @query
            def square(self, value: TestInputObject) -> TestInputObject:
                return value

        api.root = Root
        executor = api.executor()

        test_input_query = '''
            query TestInputQuery {
                square(value: {aValue: 14}){
                    valueSquared
                }
            }
        '''

        result = executor.execute(test_input_query)

        expected = {
            "square": {
                "valueSquared": 196
            }
        }
        assert not result.errors
        assert result.data == expected

    def test_enum(self):
        api = ObjectQLSchemaBuilder()

        class AnimalType(enum.Enum):
            dog = "dog"
            cat = "cat"

        class Root:

            @query
            def value(self, animal: AnimalType) -> AnimalType:

                assert isinstance(animal, AnimalType)

                if animal == AnimalType.dog:
                    return AnimalType.cat

                return AnimalType.dog

        api.root = Root
        executor = api.executor()

        test_enum_query = '''
            query TestEnum {
                value(animal: dog)
            }
        '''

        result = executor.execute(test_enum_query)
        expected = {"value": "cat"}

        assert result.data == expected

    def test_required(self):
        api = ObjectQLSchemaBuilder()

        class Root:
            @query
            def value(self, a_int: int) -> int:
                return a_int

        api.root = Root
        executor = api.executor()

        test_input_query = '''
            query TestOptionalQuery {
                value
            }
        '''

        result = executor.execute(test_input_query)

        assert result.errors and "is required but not provided" in result.errors[0].message

    def test_optional(self):
        api = ObjectQLSchemaBuilder()

        class Root:
            @query
            def value(self, a_int: int = 50) -> int:
                return a_int

        api.root = Root
        executor = api.executor()

        test_input_query = '''
            query TestOptionalQuery {
                value
            }
        '''

        result = executor.execute(test_input_query)

        expected = {
            "value": 50
        }
        assert not result.errors
        assert result.data == expected

    def test_union(self):
        api = ObjectQLSchemaBuilder()

        class Customer:

            @query
            def id(self) -> int:
                return 5

        class Owner:

            @query
            def name(self) -> str:
                return "rob"

        class Bank:

            @query
            def owner_or_customer(self, owner: bool = True, none: bool = False) -> Optional[Union[Owner, Customer]]:
                if owner:
                    return Owner()

                if none:
                    return None

                return Customer()

        api.root = Bank

        executor = api.executor()

        test_owner_query = '''
            query TestOwnerUnion {
                ownerOrCustomer {
                    ... on Owner {
                      name
                    }
                }
            }
        '''

        owner_expected = {
            "ownerOrCustomer": {
                "name": "rob"
            }
        }

        owner_result = executor.execute(test_owner_query)
        assert not owner_result.errors
        assert owner_result.data == owner_expected

        test_customer_query = '''
            query TestCustomerUnion {
                ownerOrCustomer(owner: false) {
                    ... on Customer {
                      id
                    }
                }
            }
        '''

        customer_expected = {
            "ownerOrCustomer": {
                "id": 5
            }
        }

        customer_result = executor.execute(test_customer_query)
        assert not customer_result.errors
        assert customer_result.data == customer_expected

        test_none_query = '''
            query TestCustomerUnion {
                ownerOrCustomer(owner: false, none: true) {
                    ... on Customer {
                      id
                    }
                }
            }
        '''

        none_expected = {
            "ownerOrCustomer": None
        }

        none_result = executor.execute(test_none_query)
        assert not none_result.errors
        assert none_result.data == none_expected

    def test_non_null(self):
        api = ObjectQLSchemaBuilder()

        class Root:

            @query
            def non_nullable(self) -> int:
                # noinspection PyTypeChecker
                return None

            @query
            def nullable(self) -> Optional[int]:
                return None

        api.root = Root
        executor = api.executor()

        test_non_null_query = '''
            query TestNonNullQuery {
                nonNullable
            }
        '''

        non_null_result = executor.execute(test_non_null_query)

        assert non_null_result.errors

        test_null_query = '''
            query TestNullQuery {
                nullable
            }
        '''

        expected = {
            "nullable": None
        }

        null_result = executor.execute(test_null_query)
        assert not null_result.errors
        assert null_result.data == expected

    def test_context(self):
        api = ObjectQLSchemaBuilder()

        class Root:

            @query
            def has_context(self, context: ObjectQLContext) -> bool:
                return bool(context)

        api.root = Root
        executor = api.executor()

        test_query = '''
            query HasContext {
                hasContext
            }
        '''

        expected = {
            "hasContext": True
        }

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data == expected

    location_api_url = "http://api.graphloc.com/graphql"

    @pytest.mark.skipif(not available(location_api_url),
                        reason=f"The location API '{location_api_url}' is unavailable")
    def test_remote_get(self):
        api = ObjectQLSchemaBuilder()

        RemoteAPI = ObjectQLRemoteExecutor(url=self.location_api_url)

        class Root:

            @query
            def graph_loc(self, context: ObjectQLContext) -> RemoteAPI:
                operation = context.request.info.operation.operation
                query = context.field.query
                redirected_query = operation + " " + query

                result = RemoteAPI.execute(query=redirected_query)

                if result.errors:
                    raise ObjectQLError(result.errors)

                return result.data

        api.root = Root
        executor = api.executor()

        test_query = '''
            query GetIPLocation {
                graphLoc {
                    getLocation(ip: "8.8.8.8") {
                        location {
                            latitude
                            longitude
                        }
                    }
                }
            }
        '''

        result = executor.execute(test_query)

        assert not result.errors
        assert len(result.data.get("graphLoc", {}).get("getLocation", {}).get("location", {})) == 2

    europe_graphql_url = "https://graphql-pokemon.now.sh/"

    @pytest.mark.skipif(not available(europe_graphql_url),
                        reason=f"The graphql-europe API '{europe_graphql_url}' is unavailable")
    def test_remote_post(self):
        api = ObjectQLSchemaBuilder()

        RemoteAPI = ObjectQLRemoteExecutor(url=self.europe_graphql_url, http_method="POST")

        class Root:

            @query
            def graphql(self, context: ObjectQLContext) -> RemoteAPI:
                operation = context.request.info.operation.operation
                query = context.field.query
                redirected_query = operation + " " + query

                result = RemoteAPI.execute(query=redirected_query)

                if result.errors:
                    raise ObjectQLError(result.errors)

                return result.data

        api.root = Root
        executor = api.executor()

        test_query = '''
            query GetConferences {
                graphql {
                    pokemon(name: "Pikachu") {
                        types
                    }
                }
            }
        '''

        result = executor.execute(test_query)

        assert not result.errors
        assert result.data.get("graphql").get("pokemon").get("types") == ["Electric"]

    def test_executor_to_ast(self):
        api = ObjectQLSchemaBuilder()

        class Root:

            @query
            def hello(self) -> str:
                return "hello world"

        api.root = Root
        executor = api.executor()

        schema = executor_to_ast(executor)

        # noinspection PyProtectedMember
        assert schema._type_map.keys() == executor.schema._type_map.keys()

import enum
from dataclasses import dataclass

from typing import Union, Optional

import pytest
from objectql.utils import executor_to_ast
from requests.api import request
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout

from objectql.error import ObjectQLError
from objectql.context import ObjectQLContext
from objectql.schema import ObjectQLSchema
from objectql.reduce import TagFilter
from objectql.remote import ObjectQLRemoteExecutor, remote_execute


def available(url, method="GET"):
    try:
        request(method, url, timeout=5, verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout):
        return False

    return True


class TestGraphQL:

    def test_multiple_apis(self):
        api_1 = ObjectQLSchema()
        api_2 = ObjectQLSchema()

        class Math:

            @api_1.query
            def test_square(self, number: int) -> int:
                return number * number

            @api_2.query
            def test_cube(self, number: int) -> int:
                return number * number * number

        @api_1.root
        @api_2.root
        class Root:

            @api_1.query
            @api_2.query
            def math(self) -> Math:
                return Math()

        result_1 = api_1.execute('''
            query GetTestSquare {
                math {
                    square: testSquare(number: %d)
                }
            }
        ''' % 5)

        expected = {
            "math": {
                "square": 25
            }
        }
        assert not result_1.errors
        assert result_1.data == expected

        result_2 = api_2.execute('''
            query GetTestCube {
                math {
                    square: testCube(number: %d)
                }
            }
        ''' % 5)

        expected = {
            "math": {
                "square": 125
            }
        }
        assert not result_2.errors
        assert result_2.data == expected

        result_3 = api_2.execute('''
            query GetTestSquare {
                math {
                    square: testSquare(number: %d)
                }
            }
        ''' % 5)

        assert result_3.errors

    def test_deep_query(self):
        api = ObjectQLSchema()

        class Math:

            @api.query
            def test_square(self, number: int) -> int:
                return number * number

        @api.root
        class Root:

            @api.query
            def math(self) -> Math:
                return Math()

        result = api.execute('''
            query GetTestSquare {
                math {
                    square: testSquare(number: %d)
                }
            }
        ''' % 5)

        expected = {
            "math": {
                "square": 25
            }
        }
        assert not result.errors
        assert result.data == expected

    def test_query_object_input(self):
        api = ObjectQLSchema()

        class Person:

            def __init__(self, name: str):
                self.name = name

        @api.root
        class Root:

            @api.query
            def get_name(self, person: Person) -> str:
                return person.name

        test_query = '''
            query GetTestSquare {
                getName(person: { name: "steve" })
            }
        '''

        result = api.execute(test_query)

        expected = {
            "getName": "steve"
        }
        assert not result.errors
        assert result.data == expected

    def test_custom_query_input(self):
        api = ObjectQLSchema()

        class Person:

            @classmethod
            def graphql_from_input(cls, age: int):
                person = Person(name="hugh")
                person.age = age
                return person

            def __init__(self, name: str):
                self.name = name
                self.age = 20

            @api.query
            def name(self) -> str:
                return self.name

            @api.query
            def age(self) -> int:
                return self.age

        class Root:

            @api.query
            def person_info(self, person: Person) -> str:
                return person.name + " is " + str(person.age)

        api.root_type = Root
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
        api = ObjectQLSchema()

        class Person:

            @classmethod
            def graphql_fields(cls):

                @api.query
                def age(self) -> int:
                    return self.hidden_age

                return [age]

            def __init__(self, age: int):
                self.hidden_age = age

        class Root:

            @api.query
            def thomas(self) -> Person:
                return Person(age=2)

        api.root_type = Root
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
        api = ObjectQLSchema()

        class Root:

            @api.query
            def root(self) -> 'Root':
                return Root()

            @api.query
            def value(self) -> int:
                return 5

        api.root_type = Root
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

        api = ObjectQLSchema(filters=[TagFilter(tags=["admin"])])
        admin_api = ObjectQLSchema()

        @api.root
        @admin_api.root
        class Root:

            @api.query
            @admin_api.query
            def name(self) -> str:
                return "rob"

            @api.query({"tags": ["admin"]})
            @admin_api.query({"tags": ["admin"]})
            def social_security_number(self) -> int:
                return 56

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
        api = ObjectQLSchema()

        @api.root
        class Root:

            def __init__(self):
                self._test_property = 5

            @property
            @api.query
            def test_property(self) -> int:
                return self._test_property

            # noinspection PyPropertyDefinition
            @test_property.setter
            @api.mutation
            def test_property(self, value: int) -> int:
                self._test_property = value
                return self._test_property

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
        api = ObjectQLSchema()

        @api.interface
        class Animal:

            @api.query
            def planet(self) -> str:
                return "Earth"

            @api.query
            def name(self) -> str:
                return "GenericAnimalName"

        class Dog(Animal):

            @api.query
            def name(self) -> str:
                return "Floppy"

        class Human(Animal):

            @api.query
            def name(self) -> str:
                return "John"

            @api.query
            def pet(self) -> Dog:
                return Dog()

        class Root:

            @api.query
            def best_animal(self, task: str = "bark") -> Animal:
                if task == "bark":
                    return Dog()
                return Human()

        api.root_type = Root
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
        api = ObjectQLSchema()

        @api.interface
        class Animal:

            @api.query
            def name(self) -> str:
                return "GenericAnimalName"

        @api.interface
        class Object:

            @api.query
            def weight(self) -> int:
                return 100

        @api.interface
        class Responds:

            # noinspection PyUnusedLocal
            @api.query
            def ask_question(self, text: str) -> str:
                return "GenericResponse"

        class BasicRespondMixin(Responds, Animal):

            @api.query
            def ask_question(self, text: str) -> str:
                return f"Hello, im {self.name()}!"

        class Dog(BasicRespondMixin, Animal, Object):

            @api.query
            def name(self) -> str:
                return "Floppy"

            @api.query
            def weight(self) -> int:
                return 20

        @api.root
        class Root:

            @api.query
            def animal(self) -> Animal:
                return Dog()

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
        api = ObjectQLSchema()

        @api.root
        @dataclass
        class Root:
            hello_world: str = "hello world"

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
        api = ObjectQLSchema()

        @api.root
        class Root:

            @api.mutation
            def hello_world(self) -> str:
                return "hello world"

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
        api = ObjectQLSchema()

        class Math:

            @api.query
            def square(self, number: int) -> int:
                return number * number

            @api.mutation
            def create_square(self, number: int) -> int:
                return number * number

        @api.root
        class Root:

            @api.query
            def math(self) -> Math:
                return Math()

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

        api = ObjectQLSchema()

        class Math:

            @api.query
            def square(self, number: int) -> int:
                return number * number

            @api.mutation
            def create_square(self, number: int) -> int:
                return number * number

        @api.root
        class Root:

            @api.query
            def math(self) -> Math:
                return Math()

        schema, _, _ = api.graphql_schema()

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
        api = ObjectQLSchema()

        was_called = []

        @api.root
        class Root:

            @api.query({"test_meta": "hello_meta"})
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

        middleware = [
            test_middleware,
            test_simple_middleware
        ]

        executor = api.executor(middleware=middleware)

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
        api = ObjectQLSchema()

        class TestInputObject:
            """
            A calculator
            """

            def __init__(self, a_value: int):
                super().__init__()
                self._value = a_value

            @api.query
            def value_squared(self) -> int:
                return self._value * self._value

        @api.root
        class Root:

            @api.query
            def square(self, value: TestInputObject) -> TestInputObject:
                return value

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
        api = ObjectQLSchema()

        class AnimalType(enum.Enum):
            dog = "dog"
            cat = "cat"

        @api.root
        class Root:

            @api.query
            def value(self, animal: AnimalType) -> AnimalType:

                assert isinstance(animal, AnimalType)

                if animal == AnimalType.dog:
                    return AnimalType.cat

                return AnimalType.dog

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
        api = ObjectQLSchema()

        @api.root
        class Root:
            @api.query
            def value(self, a_int: int) -> int:
                return a_int

        executor = api.executor()

        test_input_query = '''
            query TestOptionalQuery {
                value
            }
        '''

        result = executor.execute(test_input_query)

        assert result.errors and "is required but not provided" in result.errors[0].message

    def test_optional(self):
        api = ObjectQLSchema()

        @api.root
        class Root:

            @api.query
            def value(self, a_int: int = 50) -> int:
                return a_int

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
        api = ObjectQLSchema()

        class Customer:

            @api.query
            def id(self) -> int:
                return 5

        class Owner:

            @api.query
            def name(self) -> str:
                return "rob"

        @api.root
        class Bank:

            @api.query
            def owner_or_customer(self, owner: bool = True, none: bool = False) -> Optional[Union[Owner, Customer]]:
                if owner:
                    return Owner()

                if none:
                    return None

                return Customer()

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
        api = ObjectQLSchema()

        @api.root
        class Root:

            @api.query
            def non_nullable(self) -> int:
                # noinspection PyTypeChecker
                return None

            @api.query
            def nullable(self) -> Optional[int]:
                return None

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
        api = ObjectQLSchema()

        @api.root
        class Root:

            @api.query
            def has_context(self, context: ObjectQLContext) -> bool:
                return bool(context)

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
        api = ObjectQLSchema()

        RemoteAPI = ObjectQLRemoteExecutor(url=self.location_api_url)

        @api.root
        class Root:

            @api.query
            def graph_loc(self, context: ObjectQLContext) -> RemoteAPI:
                operation = context.request.info.operation.operation
                query = context.field.query
                redirected_query = operation + " " + query

                result = RemoteAPI.execute(query=redirected_query)

                if result.errors:
                    raise ObjectQLError(result.errors)

                return result.data

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
        api = ObjectQLSchema()

        RemoteAPI = ObjectQLRemoteExecutor(url=self.europe_graphql_url, http_method="POST")

        @api.root
        class Root:

            @api.query
            def graphql(self, context: ObjectQLContext) -> RemoteAPI:
                operation = context.request.info.operation.operation
                query = context.field.query
                redirected_query = operation + " " + query

                result = RemoteAPI.execute(query=redirected_query)

                if result.errors:
                    raise ObjectQLError(result.errors)

                return result.data

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

    @pytest.mark.skipif(not available(europe_graphql_url),
                        reason=f"The graphql-europe API '{europe_graphql_url}' is unavailable")
    def test_remote_post_helper(self):
        api = ObjectQLSchema()

        RemoteAPI = ObjectQLRemoteExecutor(url=self.europe_graphql_url, http_method="POST")

        @api.root
        class Root:

            @api.query
            def graphql(self, context: ObjectQLContext) -> RemoteAPI:
                return remote_execute(executor=RemoteAPI, context=context)

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
        api = ObjectQLSchema()

        @api.root
        class Root:

            @api.query
            def hello(self) -> str:
                return "hello world"

        executor = api.executor()

        schema = executor_to_ast(executor)

        # noinspection PyProtectedMember
        assert schema._type_map.keys() == executor.schema._type_map.keys()

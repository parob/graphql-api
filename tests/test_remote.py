
from typing import Optional, List

import pytest

from objectql.decorators import query, mutation
from objectql.error import GraphQLError
from objectql.mapper import GraphQLMetaKey
from objectql.schema import GraphQLSchemaBuilder
from objectql.remote import GraphQLRemoteObject


class TestGraphQLRemote:

    def test_remote_query(self):
        api = GraphQLSchemaBuilder()

        class House:

            @query
            def number_of_doors(self) -> int:
                return 5

        api.root = House

        house: House = GraphQLRemoteObject(executor=api.executor(), python_type=House)

        assert house.number_of_doors() == 5

    def test_remote_query_list(self):
        api = GraphQLSchemaBuilder()

        class Door:

            def __init__(self, height: int):
                self._height = height

            @query
            def height(self) -> int:
                return self._height

            @property
            @query
            def wood(self) -> str:
                return "oak"

        class House:

            @query
            def doors(self) -> List[Door]:
                return [Door(height=3), Door(height=5)]

        api.root = House

        house: House = GraphQLRemoteObject(executor=api.executor(), python_type=House)

        doors = house.doors()
        heights = {door.height() for door in doors}

        assert heights == {3, 5}

        doors_2 = house.doors()
        heights_2 = {door_2.height() for door_2 in doors_2}
        woods_2 = {door_2.wood for door_2 in doors_2}

        assert heights_2 == {3, 5}
        assert woods_2 == {"oak"}

    def test_remote_query_list_nested(self):
        api = GraphQLSchemaBuilder()

        class Person:

            def __init__(self, name: str):
                self._name = name

            @query
            def name(self) -> str:
                return self._name

        class Door:

            def __init__(self, height: int):
                self._height = height

            @query
            def height(self) -> int:
                return self._height

            @query
            def owner(self) -> Person:
                return Person(name="Rob")

        class House:

            @query
            def doors(self) -> List[Door]:
                return [Door(height=3), Door(height=5)]

        api.root = House

        house: House = GraphQLRemoteObject(executor=api.executor(), python_type=House)

        doors = house.doors()

        with pytest.raises(ValueError, match="can only contain scalar values"):
            owner_names = {door.owner().name() for door in doors}

    def test_remote_mutation(self):
        api = GraphQLSchemaBuilder()

        class Counter:

            def __init__(self):
                self._value = 0

            @mutation
            def increment(self) -> int:
                self._value += 1
                return self._value

            @property
            @query
            def value(self) -> int:
                return self._value

        api.root = Counter

        counter: Counter = GraphQLRemoteObject(executor=api.executor(), python_type=Counter)

        assert counter.value == 0
        assert counter.increment() == 1
        assert counter.value == 1

        for x in range(10):
            counter.increment()

        assert counter.value == 11

    def test_remote_positional_args(self):
        api = GraphQLSchemaBuilder()

        class Multiplier:

            @query
            def calculate(self, value_one: int = 1, value_two: int = 1) -> int:
                return value_one * value_two

        api.root = Multiplier

        multiplier: Multiplier = GraphQLRemoteObject(executor=api.executor(), python_type=Multiplier)

        assert multiplier.calculate(4, 2) == 8

    def test_remote_query_optional(self):
        api = GraphQLSchemaBuilder()

        class Person:

            @property
            @query
            def age(self) -> int:
                return 25

            @query
            def name(self) -> str:
                return "rob"

        class Bank:

            @query
            def owner(self, respond_none: bool = False) -> Optional[Person]:
                if respond_none:
                    return None

                return Person()

        api.root = Bank

        bank: Bank = GraphQLRemoteObject(executor=api.executor(), python_type=Bank)

        assert bank.owner().age == 25
        assert bank.owner().name() == 'rob'
        assert bank.owner(respond_none=True) is None

    def test_remote_mutation_with_input(self):
        api = GraphQLSchemaBuilder()

        class Counter:

            def __init__(self):
                self.value = 0

            @mutation
            def add(self, value: int = 0) -> int:
                self.value += value
                return self.value

        api.root = Counter

        counter: Counter = GraphQLRemoteObject(executor=api.executor(), python_type=Counter)

        assert counter.add(value=5) == 5
        assert counter.add(value=10) == 15

    def test_remote_query_with_input(self):
        api = GraphQLSchemaBuilder()

        class Calculator:

            @query
            def square(self, value: int) -> int:
                return value * value

        api.root = Calculator

        calculator: Calculator = GraphQLRemoteObject(executor=api.executor(), python_type=Calculator)

        assert calculator.square(value=5) == 25

    def test_remote_query_with_enumerable_input(self):
        api = GraphQLSchemaBuilder()

        class Calculator:

            @query
            def add(self, values: List[int]) -> int:
                total = 0

                for value in values:
                    total += value

                return total

        api.root = Calculator

        calculator: Calculator = GraphQLRemoteObject(executor=api.executor(), python_type=Calculator)

        assert calculator.add(values=[5, 2, 7]) == 14

    def test_remote_input_object(self):
        api = GraphQLSchemaBuilder()

        class Garden:

            def __init__(self, size: int):
                self._size = size

            @property
            @query
            def size(self) -> int:
                return self._size

        class House:

            @query
            def value(self, garden: Garden, rooms: int = 7) -> int:
                return (garden.size * 2) + (rooms * 10)

        api.root = House

        house: House = GraphQLRemoteObject(executor=api.executor(), python_type=House)
        assert house.value(garden=Garden(size=10)) == 90

    def test_remote_input_object_nested(self):
        api = GraphQLSchemaBuilder()

        class Animal:

            def __init__(self, age: int):
                self._age = age

            @property
            @query
            def age(self) -> int:
                return self._age

        class Garden:

            def __init__(self, size: int, animal: Animal, set_animal: bool = False):
                self.set_animal = set_animal
                if set_animal:
                    self.animal = animal
                self._size = size

            @property
            @query
            def size(self) -> int:
                return self._size

            @property
            @query
            def animal_age(self) -> int:
                return self.animal.age

        class House:

            @query
            def value(self, garden: Garden, rooms: int = 7) -> int:
                return ((garden.size * 2) + (rooms * 10)) - garden.animal_age

        api.root = House

        house: House = GraphQLRemoteObject(executor=api.executor(), python_type=House)

        with pytest.raises(GraphQLError, match="nested inputs must have matching attribute to field names"):
            assert house.value(garden=Garden(animal=Animal(age=5), size=10)) == 85

        assert house.value(garden=Garden(animal=Animal(age=5), set_animal=True, size=10)) == 85

    def test_remote_recursive_mutated(self):
        api = GraphQLSchemaBuilder()

        class Flopper:

            def __init__(self):
                self._flop = True

            @query
            def value(self) -> bool:
                return self._flop

            @mutation
            def flop(self) -> 'Flopper':
                self._flop = not self._flop
                return self

        global_flopper = Flopper()

        class Flipper:

            def __init__(self):
                self._flip = True

            @query
            def value(self) -> bool:
                return self._flip

            @mutation
            def flip(self) -> 'Flipper':
                self._flip = not self._flip
                return self

            @query
            def flopper(self) -> Flopper:
                return global_flopper

            @mutation({GraphQLMetaKey.resolve_to_self: False})
            def flagged_flip(self) -> 'Flipper':
                self._flip = not self._flip
                return self

        api.root = Flipper

        flipper: Flipper = GraphQLRemoteObject(executor=api.executor(), python_type=Flipper)

        assert flipper.value()
        flipped_flipper = flipper.flagged_flip()
        assert not flipped_flipper.value()

        with pytest.raises(GraphQLError, match="mutated objects cannot be refetched"):
            flipped_flipper.flagged_flip()

        safe_flipped_flipper = flipper.flip()

        assert safe_flipped_flipper.value()

        safe_flipped_flipper.flip()

        assert not safe_flipped_flipper.value()
        assert not flipper.value()

        flopper = flipper.flopper()
        assert flopper.value()

        assert not flopper.flop().value()
        assert flopper.flop().value()

        mutated_flopper = flopper.flop()

        assert not mutated_flopper.value()
        mutated_mutated_flopper = mutated_flopper.flop()
        assert mutated_flopper.value()
        assert mutated_mutated_flopper.value()

    def test_remote_nested(self):
        api = GraphQLSchemaBuilder()

        class Person:

            def __init__(self, name: str, age: int, height: float):
                self._name = name
                self._age = age
                self._height = height

            @query
            def age(self) -> int:
                return self._age

            @query
            def name(self) -> str:
                return self._name

            @property
            @query
            def height(self) -> float:
                return self._height

            @mutation
            def update(self, name: str = None, height: float = None) -> 'Person':

                if name:
                    self._name = name

                if height:
                    self._height = height

                return self

        class Root:

            def __init__(self):
                self._rob = Person(name="rob", age=10, height=183.0)
                self._counter = 0

            @query
            def rob(self) -> Person:
                return self._rob

        api.root = Root

        root: Root = GraphQLRemoteObject(executor=api.executor(), python_type=Root)

        person: Person = root.rob()

        assert person.name() == "rob"
        assert person.age() == 10
        assert person.height == 183.0

        assert person.update(name="tom").name() == "tom"
        assert person.name() == "tom"

        assert person.update(name="james", height=184.0).name() == "james"
        assert person.name() == "james"
        assert person.age() == 10
        assert person.height == 184.0

        person.update(name="pete").name()
        assert person.name() == "pete"

    def test_remote_with_local_property(self):
        api = GraphQLSchemaBuilder()

        class Person:

            @query
            def age(self) -> int:
                return 50

            @property
            def height(self):
                return 183

        api.root = Person

        person: Person = GraphQLRemoteObject(executor=api.executor(), python_type=Person)

        assert person.age() == 50
        assert person.height == 183

    def test_remote_with_local_method(self):
        api = GraphQLSchemaBuilder()

        class Person:

            @query
            def age(self) -> int:
                return 50

            def hello(self):
                return "hello"

        api.root = Person

        person: Person = GraphQLRemoteObject(executor=api.executor(), python_type=Person)

        assert person.age() == 50
        assert person.hello() == "hello"

    def test_remote_with_local_static_method(self):
        api = GraphQLSchemaBuilder()

        class Person:

            @query
            def age(self) -> int:
                return 50

            @staticmethod
            def hello():
                return "hello"

        api.root = Person

        person: Person = GraphQLRemoteObject(executor=api.executor(), python_type=Person)

        assert person.age() == 50
        assert person.hello() == "hello"

    def test_remote_with_local_class_method(self):
        api = GraphQLSchemaBuilder()

        class Person:

            @query
            def age(self) -> int:
                return 50

            @classmethod
            def hello(cls):
                assert cls == Person
                return "hello"

        api.root = Person

        person: Person = GraphQLRemoteObject(executor=api.executor(), python_type=Person)

        assert person.age() == 50
        assert person.hello() == "hello"

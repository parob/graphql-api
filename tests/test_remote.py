import asyncio
import enum
import random
import uuid
from dataclasses import dataclass

from typing import Optional, List
from uuid import UUID

import time
import pytest

from graphql_api.error import GraphQLError
from graphql_api.mapper import GraphQLMetaKey
from graphql_api.api import GraphQLAPI
from graphql_api.remote import GraphQLRemoteObject, GraphQLRemoteExecutor

# noinspection PyTypeChecker
from tests.test_graphql import available


class TestGraphQLRemote:
    def test_remote_query(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class House:
            @api.field
            def number_of_doors(self) -> int:
                return 5

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert house.number_of_doors() == 5

    def test_remote_query_list(self):
        api = GraphQLAPI()

        class Door:
            def __init__(self, height: int):
                self._height = height

            @api.field
            def height(self) -> int:
                return self._height

            @property
            @api.field
            def wood(self) -> str:
                return "oak"

            @property
            @api.field
            def tags(self) -> List[str]:
                return ["oak", "white", "solid"]

        @api.type(is_root_type=True)
        class House:
            @api.field
            def doors(self) -> List[Door]:
                return [Door(height=3), Door(height=5)]

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)

        doors = house.doors()
        heights = {door.height() for door in doors}

        assert heights == {3, 5}

        doors_2 = house.doors()
        heights_2 = {door_2.height() for door_2 in doors_2}
        woods_2 = {door_2.wood for door_2 in doors_2}

        tags_2 = [door_2.tags for door_2 in doors_2]

        assert heights_2 == {3, 5}
        assert woods_2 == {"oak"}
        assert tags_2 == [["oak", "white", "solid"], ["oak", "white", "solid"]]

    def test_remote_query_list_nested(self):
        api = GraphQLAPI()

        class Person:
            def __init__(self, name: str):
                self._name = name

            @api.field
            def name(self) -> str:
                return self._name

        class Door:
            def __init__(self, height: int):
                self._height = height

            @api.field
            def height(self) -> int:
                return self._height

            @api.field
            def owner(self) -> Person:
                return Person(name="Rob")

        @api.type(is_root_type=True)
        class House:
            @api.field
            def doors(self) -> List[Door]:
                return [Door(height=3), Door(height=5)]

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)

        doors = house.doors()

        with pytest.raises(ValueError, match="can only contain scalar values"):
            assert {door.owner().name() for door in doors}

    def test_remote_query_enum(self):
        api = GraphQLAPI()

        class HouseType(enum.Enum):
            bungalow = "bungalow"
            flat = "flat"

        @api.type(is_root_type=True)
        class House:
            @api.field
            def type(self) -> HouseType:
                return HouseType.bungalow

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert house.type() == HouseType.bungalow

    def test_remote_query_send_enum(self):
        api = GraphQLAPI()

        class RoomType(enum.Enum):
            bedroom = "bedroom"
            kitchen = "kitchen"

        class Room:
            def __init__(self, name: str, room_type: RoomType):
                self._name = name
                self._room_type = room_type

            @api.field
            def name(self) -> str:
                return self._name

            @api.field
            def room_type(self) -> RoomType:
                return self._room_type

        @api.type(is_root_type=True)
        class House:
            @api.field
            def get_room(self) -> Room:
                return Room(name="robs_room", room_type=RoomType.bedroom)

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert house.get_room().room_type() == RoomType.bedroom

    def test_remote_query_uuid(self):
        api = GraphQLAPI()

        person_id = uuid.uuid4()

        @api.type(is_root_type=True)
        class Person:
            @api.field
            def id(self) -> UUID:
                return person_id

        person: Person = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert person.id() == person_id

    def test_query_bytes(self):
        api = GraphQLAPI()

        a_value = b"hello "
        b_value = b"world"

        @api.type(is_root_type=True)
        class BytesUtils:
            @api.field
            def add_bytes(self, a: bytes, b: bytes) -> bytes:
                return b"".join([a, b])

        executor = api.executor()

        bytes_utils: BytesUtils = GraphQLRemoteObject(executor=executor, api=api)
        test_bytes = bytes_utils.add_bytes(a_value, b_value)

        assert test_bytes == b"".join([a_value, b_value])

    def test_remote_query_list_parameter(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Tags:
            @api.field
            def join_tags(self, tags: List[str] = None) -> str:
                return "".join(tags) if tags else ""

        tags: Tags = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert tags.join_tags() == ""
        assert tags.join_tags(tags=[]) == ""
        assert tags.join_tags(tags=["a", "b"]) == "ab"

    def test_remote_mutation(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Counter:
            def __init__(self):
                self._value = 0

            @api.field(mutable=True)
            def increment(self) -> int:
                self._value += 1
                return self._value

            @property
            @api.field
            def value(self) -> int:
                return self._value

        counter: Counter = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert counter.value == 0
        assert counter.increment() == 1
        assert counter.value == 1

        for x in range(10):
            counter.increment()

        assert counter.value == 11

    def test_remote_positional_args(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Multiplier:
            @api.field
            def calculate(self, value_one: int = 1, value_two: int = 1) -> int:
                return value_one * value_two

        multiplier: Multiplier = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert multiplier.calculate(4, 2) == 8

    def test_remote_query_optional(self):
        api = GraphQLAPI()

        class Person:
            @property
            @api.field
            def age(self) -> int:
                return 25

            @api.field
            def name(self) -> str:
                return "rob"

        @api.type(is_root_type=True)
        class Bank:
            @api.field
            def owner(self, respond_none: bool = False) -> Optional[Person]:
                if respond_none:
                    return None

                return Person()

        bank: Bank = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert bank.owner().age == 25
        assert bank.owner().name() == "rob"
        assert bank.owner(respond_none=True) is None

    def test_remote_mutation_with_input(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Counter:
            def __init__(self):
                self.value = 0

            @api.field(mutable=True)
            def add(self, value: int = 0) -> int:
                self.value += value
                return self.value

        counter: Counter = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert counter.add(value=5) == 5
        assert counter.add(value=10) == 15

    def test_remote_query_with_input(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Calculator:
            @api.field
            def square(self, value: int) -> int:
                return value * value

        calculator: Calculator = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert calculator.square(value=5) == 25

    def test_remote_query_with_enumerable_input(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Calculator:
            @api.field
            def add(self, values: List[int]) -> int:
                total = 0

                for value in values:
                    total += value

                return total

        calculator: Calculator = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert calculator.add(values=[5, 2, 7]) == 14

    def test_remote_input_object(self):
        api = GraphQLAPI()

        class Garden:
            def __init__(self, size: int):
                self._size = size

            @property
            @api.field
            def size(self) -> int:
                return self._size

        @api.type(is_root_type=True)
        class House:
            @api.field
            def value(self, garden: Garden, rooms: int = 7) -> int:
                return (garden.size * 2) + (rooms * 10)

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)
        assert house.value(garden=Garden(size=10)) == 90

    def test_remote_input_object_nested(self):
        api = GraphQLAPI()

        class Animal:
            def __init__(self, age: int):
                self._age = age

            @property
            @api.field
            def age(self) -> int:
                return self._age

        class Garden:
            def __init__(self, size: int, animal: Animal, set_animal: bool = False):
                self.set_animal = set_animal
                if set_animal:
                    self.animal = animal
                self._size = size

            @property
            @api.field
            def size(self) -> int:
                return self._size

            @property
            @api.field
            def animal_age(self) -> int:
                return self.animal.age

        @api.type(is_root_type=True)
        class House:
            @api.field
            def value(self, garden: Garden, rooms: int = 7) -> int:
                return ((garden.size * 2) + (rooms * 10)) - garden.animal_age

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)

        with pytest.raises(
            GraphQLError,
            match="nested inputs must have matching attribute to field names",
        ):
            assert house.value(garden=Garden(animal=Animal(age=5), size=10)) == 85

        assert (
            house.value(garden=Garden(animal=Animal(age=5), set_animal=True, size=10))
            == 85
        )

    def test_remote_return_object(self):
        api = GraphQLAPI()

        @dataclass
        class Door:
            height: int

        @api.type(is_root_type=True)
        class House:
            @api.field
            def doors(self) -> List[Door]:
                return [Door(height=180), Door(height=204)]

            @api.field
            def front_door(self) -> Door:
                return Door(height=204)

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert house.doors()[0].height == 180
        assert house.front_door().height == 204

    def test_remote_return_object_call_count(self):
        api = GraphQLAPI()

        @dataclass
        class Door:
            height: int
            weight: int

        @api.type(is_root_type=True)
        class House:
            def __init__(self):
                self.api_calls = 0

            @api.field
            def number(self) -> int:
                self.api_calls += 1
                return 18

            @api.field
            def front_door(self) -> Door:
                self.api_calls += 1
                return Door(height=204, weight=70)

        root_house = House()

        house: House = GraphQLRemoteObject(
            executor=api.executor(root_value=root_house),
            api=api,
        )

        front_door = house.front_door()
        assert root_house.api_calls == 0

        assert front_door.height == 204
        assert front_door.weight == 70

        assert root_house.api_calls == 2

        assert front_door.height == 204

        assert root_house.api_calls == 2

        front_door = house.front_door()
        assert root_house.api_calls == 2

        assert front_door.height == 204

        assert root_house.api_calls == 3
        root_house.api_calls = 0

        assert root_house.number() == 18
        assert root_house.number() == 18
        assert root_house.api_calls == 2

    def test_remote_return_object_cache(self):
        api = GraphQLAPI()

        @dataclass
        class Door:
            id: str

            @api.field
            def rand(self, max: int = 100) -> int:
                return random.randint(0, max)

        @api.type(is_root_type=True)
        class House:
            @api.field
            def front_door(self, id: str) -> Door:
                return Door(id=id)

        root_house = House()

        house: House = GraphQLRemoteObject(
            executor=api.executor(root_value=root_house),
            api=api,
        )

        front_door = house.front_door(id="door_a")
        random_int = front_door.rand()
        assert random_int == front_door.rand()
        assert random_int != front_door.rand(max=200)
        assert random_int == front_door.rand()

        front_door = house.front_door(id="door_a")
        assert random_int != front_door.rand()

        front_door = house.front_door(id="door_b")
        assert random_int != front_door.rand()

    def test_remote_recursive_mutated(self):
        api = GraphQLAPI()

        class Flopper:
            def __init__(self):
                self._flop = True

            @api.field
            def value(self) -> bool:
                return self._flop

            @api.field(mutable=True)
            def flop(self) -> "Flopper":
                self._flop = not self._flop
                return self

        global_flopper = Flopper()

        @api.type(is_root_type=True)
        class Flipper:
            def __init__(self):
                self._flip = True

            @api.field
            def value(self) -> bool:
                return self._flip

            @api.field(mutable=True)
            def flip(self) -> "Flipper":
                self._flip = not self._flip
                return self

            @api.field
            def flopper(self) -> Flopper:
                return global_flopper

            @api.field({GraphQLMetaKey.resolve_to_self: False}, mutable=True)
            def flagged_flip(self) -> "Flipper":
                self._flip = not self._flip
                return self

        flipper: Flipper = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert flipper.value()
        flipped_flipper = flipper.flagged_flip()
        assert not flipped_flipper.value()

        with pytest.raises(GraphQLError, match="mutated objects cannot be re-fetched"):
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
        api = GraphQLAPI()

        class Person:
            def __init__(self, name: str, age: int, height: float):
                self._name = name
                self._age = age
                self._height = height

            @api.field
            def age(self) -> int:
                return self._age

            @api.field
            def name(self) -> str:
                return self._name

            @property
            @api.field
            def height(self) -> float:
                return self._height

            @api.field(mutable=True)
            def update(self, name: str = None, height: float = None) -> "Person":
                if name:
                    self._name = name

                if height:
                    self._height = height

                return self

        @api.type(is_root_type=True)
        class Root:
            def __init__(self):
                self._rob = Person(name="rob", age=10, height=183.0)
                self._counter = 0

            @api.field
            def rob(self) -> Person:
                return self._rob

        root: Root = GraphQLRemoteObject(executor=api.executor(), api=api)

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
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Person:
            @api.field
            def age(self) -> int:
                return 50

            @property
            def height(self):
                return 183

        person: Person = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert person.age() == 50
        assert person.height == 183

    def test_remote_with_local_method(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Person:
            @api.field
            def age(self) -> int:
                return 50

            # noinspection PyMethodMayBeStatic
            def hello(self):
                return "hello"

        person: Person = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert person.age() == 50
        assert person.hello() == "hello"

    def test_remote_with_local_static_method(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Person:
            @api.field
            def age(self) -> int:
                return 50

            @staticmethod
            def hello():
                return "hello"

        person: Person = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert person.age() == 50
        assert person.hello() == "hello"

    def test_remote_with_local_class_method(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Person:
            @api.field
            def age(self) -> int:
                return 50

            @classmethod
            def hello(cls):
                assert cls == Person
                return "hello"

        person: Person = GraphQLRemoteObject(executor=api.executor(), api=api)

        assert person.age() == 50
        assert person.hello() == "hello"

    utc_time_api_url = "https://europe-west2-parob-297412.cloudfunctions.net/utc_time"

    # noinspection DuplicatedCode,PyUnusedLocal
    @pytest.mark.skipif(
        not available(utc_time_api_url),
        reason=f"The UTCTime API '{utc_time_api_url}' is unavailable",
    )
    def test_remote_get_async(self):
        utc_time_api = GraphQLAPI()

        remote_executor = GraphQLRemoteExecutor(url=self.utc_time_api_url)

        @utc_time_api.type(is_root_type=True)
        class UTCTimeAPI:
            @utc_time_api.field
            def now(self) -> str:
                pass

        api: UTCTimeAPI = GraphQLRemoteObject(
            executor=remote_executor, api=utc_time_api
        )

        request_count = 100

        # Async test
        async_start = time.time()

        async def fetch():
            tasks = []
            for _ in range(0, request_count):
                tasks.append(api.call_async("now"))
            return await asyncio.gather(*tasks)

        async_utc_now_list = asyncio.run(fetch())

        async_time = time.time() - async_start
        assert len(set(async_utc_now_list)) == request_count

        # Sync test
        sync_start = time.time()
        sync_utc_now_list = []

        for _ in range(0, request_count):
            sync_utc_now_list.append(api.now())
            api.clear_cache()  # Clear the API cache so that it re-fetches the request.
        sync_time = time.time() - sync_start

        assert len(set(sync_utc_now_list)) == request_count

        assert sync_time >= 1.2 * async_time

    # noinspection DuplicatedCode,PyUnusedLocal
    @pytest.mark.skipif(
        not available(utc_time_api_url),
        reason=f"The UTCTime API '{utc_time_api_url}' is unavailable",
    )
    def test_remote_get_async_await(self):
        utc_time_api = GraphQLAPI()

        remote_executor = GraphQLRemoteExecutor(url=self.utc_time_api_url)

        @utc_time_api.type(is_root_type=True)
        class UTCTimeAPI:
            @utc_time_api.field
            def now(self) -> str:
                pass

        api: UTCTimeAPI = GraphQLRemoteObject(
            executor=remote_executor, api=utc_time_api
        )

        async def fetch():
            return await api.call_async("now")

        async_utc_now = asyncio.run(fetch())

        assert async_utc_now

    # Fix a bug calling fetch() with string list
    def test_remote_query_fetch_str_list(self):
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class StudentRoll:
            @api.field
            def students(self) -> List[str]:
                return ["alice", "bob"]

        roll: StudentRoll = GraphQLRemoteObject(executor=api.executor(), api=api)
        roll.fetch()

        assert roll.students() == ["alice", "bob"]

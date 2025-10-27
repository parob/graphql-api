import asyncio
import enum
import random
import time
import uuid
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

import pytest

from graphql_api.api import GraphQLAPI
from graphql_api.error import GraphQLError
from graphql_api.mapper import GraphQLMetaKey
from graphql_api.remote import GraphQLRemoteExecutor, GraphQLRemoteObject

# noinspection PyTypeChecker


from tests.test_graphql import available


class TestGraphQLRemote:
    def test_remote_query(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class House:
            @api.field
            def number_of_doors(self) -> int:
                return 5

        # type: ignore[reportIncompatibleMethodOverride]
        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert house.number_of_doors() == 5

    def test_remote_query_list(self) -> None:
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

        # type: ignore[reportIncompatibleMethodOverride]
        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

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

    def test_remote_query_list_nested(self) -> None:
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

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        doors = house.doors()

        with pytest.raises(ValueError, match="can only contain scalar values"):
            assert {door.owner().name() for door in doors}

    def test_remote_query_enum(self) -> None:
        api = GraphQLAPI()

        class HouseType(enum.Enum):
            bungalow = "bungalow"
            flat = "flat"

        @api.type(is_root_type=True)
        class House:
            @api.field
            def type(self) -> HouseType:
                return HouseType.bungalow

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert house.type() == HouseType.bungalow

    def test_remote_query_send_enum(self) -> None:
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

        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert house.get_room().room_type() == RoomType.bedroom

    def test_remote_query_uuid(self) -> None:
        api = GraphQLAPI()

        person_id = uuid.uuid4()

        @api.type(is_root_type=True)
        class Person:
            @api.field
            def id(self) -> UUID:
                return person_id

        person: Person = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert person.id() == person_id

    def test_query_bytes(self) -> None:
        api = GraphQLAPI()

        a_value = b"hello "
        b_value = b"world"

        @api.type(is_root_type=True)
        class BytesUtils:
            @api.field
            def add_bytes(self, a: bytes, b: bytes) -> bytes:
                return b"".join([a, b])

        executor = api.executor()

        bytes_utils: BytesUtils = GraphQLRemoteObject(
            executor=executor, api=api)  # type: ignore[reportIncompatibleMethodOverride]
        test_bytes = bytes_utils.add_bytes(a_value, b_value)

        assert test_bytes == b"".join([a_value, b_value])

    def test_remote_query_list_parameter(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Tags:
            @api.field
            def join_tags(self, tags: Optional[List[str]] = None) -> str:
                return "".join(tags) if tags else ""

        tags: Tags = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert tags.join_tags() == ""
        assert tags.join_tags(tags=[]) == ""
        assert tags.join_tags(tags=["a", "b"]) == "ab"

    def test_remote_mutation(self) -> None:
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

        counter: Counter = GraphQLRemoteObject(
            executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert counter.value == 0
        assert counter.increment() == 1
        assert counter.value == 1

        for x in range(10):
            counter.increment()

        assert counter.value == 11

    def test_remote_positional_args(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Multiplier:
            @api.field
            def calculate(self, value_one: int = 1, value_two: int = 1) -> int:
                return value_one * value_two

        multiplier: Multiplier = GraphQLRemoteObject(
            executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert multiplier.calculate(4, 2) == 8

    def test_remote_query_optional(self) -> None:
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

        bank: Bank = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        owner = bank.owner()
        assert owner is not None
        assert owner.age == 25
        assert owner.name() == "rob"
        assert bank.owner(respond_none=True) is None

    def test_remote_mutation_with_input(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Counter:
            def __init__(self):
                self.value = 0

            @api.field(mutable=True)
            def add(self, value: int = 0) -> int:
                self.value += value
                return self.value

        counter: Counter = GraphQLRemoteObject(
            executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert counter.add(value=5) == 5
        assert counter.add(value=10) == 15

    def test_remote_query_with_input(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Calculator:
            @api.field
            def square(self, value: int) -> int:
                return value * value

        calculator: Calculator = GraphQLRemoteObject(
            executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert calculator.square(value=5) == 25

    def test_remote_query_with_enumerable_input(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Calculator:
            @api.field
            def add(self, values: List[int]) -> int:
                total = 0

                for value in values:
                    total += value

                return total

        # type: ignore[reportIncompatibleMethodOverride]
        calculator: Calculator = GraphQLRemoteObject(
            executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert calculator.add(values=[5, 2, 7]) == 14

    def test_remote_input_object(self) -> None:
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

        # type: ignore[reportIncompatibleMethodOverride]
        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]
        assert house.value(garden=Garden(size=10)) == 90

    def test_remote_input_object_nested(self) -> None:
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

        # type: ignore[reportIncompatibleMethodOverride]
        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        with pytest.raises(
            GraphQLError,
            match="nested inputs must have matching attribute to field names",
        ):
            assert house.value(garden=Garden(
                animal=Animal(age=5), size=10)) == 85

        assert (
            house.value(garden=Garden(animal=Animal(
                age=5), set_animal=True, size=10))
            == 85
        )

    def test_remote_return_object(self) -> None:
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

        # type: ignore[reportIncompatibleMethodOverride]
        house: House = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert house.doors()[0].height == 180
        assert house.front_door().height == 204

    def test_remote_return_object_call_count(self) -> None:
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

        house: House = GraphQLRemoteObject(executor=api.executor(
            # type: ignore[reportIncompatibleMethodOverride]
            root_value=root_house), api=api)  # type: ignore[reportIncompatibleMethodOverride]

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

    def test_remote_return_object_cache(self) -> None:
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

        house: House = GraphQLRemoteObject(executor=api.executor(
            # type: ignore[reportIncompatibleMethodOverride]
            root_value=root_house), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        front_door = house.front_door(id="door_a")
        random_int = front_door.rand()
        assert random_int == front_door.rand()
        assert random_int != front_door.rand(max=200)

        # This should be cached
        assert random_int == front_door.rand()

        # This should not be cached
        front_door_2 = house.front_door(id="door_b")
        assert random_int != front_door_2.rand()

    def test_remote_recursive_mutated(self) -> None:
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

        # type: ignore[reportIncompatibleMethodOverride]
        flipper: Flipper = GraphQLRemoteObject(
            executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

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

    def test_remote_nested(self) -> None:
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
            def update(
                self, name: Optional[str] = None, height: Optional[float] = None
            ) -> "Person":
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

        # type: ignore[reportIncompatibleMethodOverride]
        root: Root = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

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

    def test_remote_with_local_property(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Person:
            @api.field
            def age(self) -> int:
                return 50

            @property
            def height(self):
                return 183

        # type: ignore[reportIncompatibleMethodOverride]
        person: Person = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert person.age() == 50
        assert person.height == 183

    def test_remote_with_local_method(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Person:
            @api.field
            def age(self) -> int:
                return 50

            # noinspection PyMethodMayBeStatic
            def hello(self):
                return "hello"

        # type: ignore[reportIncompatibleMethodOverride]
        person: Person = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert person.age() == 50
        assert person.hello() == "hello"

    def test_remote_with_local_static_method(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Person:
            @api.field
            def age(self) -> int:
                return 50

            @staticmethod
            def hello():
                return "hello"

        person: Person = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert person.age() == 50
        assert person.hello() == "hello"

    def test_remote_with_local_class_method(self) -> None:
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

        person: Person = GraphQLRemoteObject(executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]

        assert person.age() == 50
        assert person.hello() == "hello"

    def test_async_concurrency_performance(self) -> None:
        """
        Tests that async requests execute concurrently (in parallel) by mocking
        the executor with controlled delays. This proves async is faster than sync
        when multiple requests are made.
        """
        from unittest.mock import patch

        api = GraphQLAPI()

        class Person:
            @api.field
            def name(self, id: int) -> str:
                return f"Person {id}"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def person(self, id: int) -> Person:
                return Person()

        # Mock executor that simulates 0.1 second delay per request
        request_delay = 0.1
        request_count = 5

        # Create a real executor and mock its execute methods
        executor = api.executor()

        # Track number of concurrent requests
        concurrent_count = {"current": 0, "max": 0}

        async def mock_execute_async(query, **kwargs):
            concurrent_count["current"] += 1
            concurrent_count["max"] = max(concurrent_count["max"], concurrent_count["current"])

            await asyncio.sleep(request_delay)

            # Parse the query to extract the id
            import re
            id_match = re.search(r'id:(\d+)', query)
            person_id = id_match.group(1) if id_match else "1"

            concurrent_count["current"] -= 1

            return type('obj', (object,), {
                'data': {'person': {'name': f'Person {person_id}'}},
                'errors': None
            })()

        def mock_execute(query, **kwargs):
            # Sync version just runs async in a new loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(mock_execute_async(query, **kwargs))
            finally:
                loop.close()

        # Patch the executor methods
        with patch.object(executor, 'execute', side_effect=mock_execute), \
             patch.object(executor, 'execute_async', side_effect=mock_execute_async):

            remote_obj: Query = GraphQLRemoteObject(
                executor=executor, api=api
            )  # type: ignore[reportIncompatibleMethodOverride]

            # Test synchronous requests (should take request_count * request_delay)
            sync_start = time.time()
            for i in range(1, request_count + 1):
                remote_obj.person(id=i).name()
                remote_obj.clear_cache()  # type: ignore[reportIncompatibleMethodOverride]
            sync_time = time.time() - sync_start

            # Reset concurrent counter
            concurrent_count["current"] = 0
            concurrent_count["max"] = 0

            # Test asynchronous requests (should take approximately request_delay if concurrent)
            async def fetch_async():
                tasks = []
                for i in range(1, request_count + 1):
                    person = remote_obj.person(id=i)
                    tasks.append(person.name(aio=True))  # type: ignore[reportIncompatibleMethodOverride]
                return await asyncio.gather(*tasks)

            async_start = time.time()
            results = asyncio.run(fetch_async())
            async_time = time.time() - async_start

            # Verify results
            assert len(results) == request_count
            assert "Person 1" in results

            # Verify concurrent execution: max concurrent should be > 1
            assert concurrent_count["max"] > 1, \
                f"Expected concurrent requests, but max concurrent was {concurrent_count['max']}"

            # Verify timing: async should be significantly faster
            # Sync time should be ~= request_count * request_delay
            # Async time should be ~= request_delay (all running concurrently)
            expected_sync_time = request_count * request_delay
            expected_async_time = request_delay

            # Allow some overhead (50% margin)
            assert sync_time >= expected_sync_time * 0.8, \
                f"Sync time {sync_time:.2f}s should be close to {expected_sync_time:.2f}s"
            assert async_time <= expected_async_time * 2.0, \
                f"Async time {async_time:.2f}s should be close to {expected_async_time:.2f}s"

            # The key assertion: async should be much faster than sync
            speedup = sync_time / async_time
            assert speedup >= 2.0, \
                f"Async should be at least 2x faster, got {speedup:.2f}x speedup " \
                f"(sync: {sync_time:.2f}s, async: {async_time:.2f}s)"

    def test_async_with_nested_objects(self) -> None:
        """
        Tests that async works correctly with nested objects and complex queries.
        """
        from unittest.mock import patch

        api = GraphQLAPI()

        class Address:
            @api.field
            def street(self) -> str:
                return "123 Main St"

            @api.field
            def city(self) -> str:
                return "Springfield"

        class Person:
            @api.field
            def name(self) -> str:
                return "John Doe"

            @api.field
            def address(self) -> Address:
                return Address()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def person(self, id: int) -> Person:
                return Person()

        executor = api.executor()
        call_count = {"count": 0}

        async def mock_execute_async(query, **kwargs):
            call_count["count"] += 1
            await asyncio.sleep(0.05)

            # Parse query to determine response
            if "address" in query:
                return type('obj', (object,), {
                    'data': {'person': {'name': 'John Doe', 'address': {'street': '123 Main St', 'city': 'Springfield'}}},
                    'errors': None
                })()
            else:
                return type('obj', (object,), {
                    'data': {'person': {'name': 'John Doe'}},
                    'errors': None
                })()

        with patch.object(executor, 'execute_async', side_effect=mock_execute_async):
            remote_obj: Query = GraphQLRemoteObject(
                executor=executor, api=api
            )  # type: ignore[reportIncompatibleMethodOverride]

            async def fetch_nested():
                person = remote_obj.person(id=1)
                # This should work with nested field access
                name = await person.name(aio=True)  # type: ignore[reportIncompatibleMethodOverride]
                return name

            result = asyncio.run(fetch_nested())
            assert result == "John Doe"
            assert call_count["count"] == 1

    def test_async_error_handling(self) -> None:
        """
        Tests that async requests properly handle and propagate errors.
        """
        from unittest.mock import patch

        api = GraphQLAPI()

        class Person:
            @api.field
            def name(self) -> str:
                return "Test"

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def person(self, id: int) -> Person:
                return Person()

        executor = api.executor()

        async def mock_execute_async_with_error(query, **kwargs):
            await asyncio.sleep(0.01)
            return type('obj', (object,), {
                'data': None,
                'errors': [{'message': 'Person not found'}]
            })()

        with patch.object(executor, 'execute_async', side_effect=mock_execute_async_with_error):
            remote_obj: Query = GraphQLRemoteObject(
                executor=executor, api=api
            )  # type: ignore[reportIncompatibleMethodOverride]

            async def fetch_with_error():
                person = remote_obj.person(id=999)
                return await person.name(aio=True)  # type: ignore[reportIncompatibleMethodOverride]

            # Should raise an error
            with pytest.raises(Exception):  # GraphQLRemoteError
                asyncio.run(fetch_with_error())

    rick_and_morty_api_url = "https://rickandmortyapi.com/graphql"

    @pytest.mark.skipif(
        not available(rick_and_morty_api_url, is_graphql=True),
        reason=f"The Rick and Morty API '{rick_and_morty_api_url}' is unavailable",
    )
    def test_remote_get_async(self) -> None:
        """
        Tests that a remote GraphQL API can be queried asynchronously.
        This test depends on an external API and may be flaky due to network
        issues, rate limiting, or API downtime. For a more reliable test of
        async concurrency, see test_async_concurrency_performance.
        """
        rick_and_morty_api = GraphQLAPI()
        remote_executor = GraphQLRemoteExecutor(
            url=self.rick_and_morty_api_url, verify=False
        )

        class Character:
            @rick_and_morty_api.field
            def name(self) -> str:
                ...

        @rick_and_morty_api.type(is_root_type=True)
        class RickAndMortyAPI:
            @rick_and_morty_api.field
            def character(self, id: int) -> Character:
                ...

        # Add Character to the local namespace to allow for type hint resolution
        locals()["Character"] = Character

        api: RickAndMortyAPI = GraphQLRemoteObject(
            executor=remote_executor, api=rick_and_morty_api
        )  # type: ignore[reportIncompatibleMethodOverride]

        # Test that async requests work (without strict timing requirements)
        request_count = 3  # Reduced count to minimize API load

        async def fetch():
            tasks = []
            for i in range(1, request_count + 1):
                character = api.character(id=i)
                # type: ignore[reportIncompatibleMethodOverride]
                tasks.append(character.name(aio=True))  # type: ignore[reportIncompatibleMethodOverride]
            return await asyncio.gather(*tasks)

        results = asyncio.run(fetch())

        # Just verify the async requests work, without timing assertions
        assert len(results) == request_count
        assert "Rick Sanchez" in results

    @pytest.mark.skipif(
        not available(rick_and_morty_api_url, is_graphql=True),
        reason=f"The Rick and Morty API '{rick_and_morty_api_url}' is unavailable",
    )
    def test_remote_get_async_await(self) -> None:
        """
        Tests that a remote GraphQL API can be queried asynchronously with awaits.
        """
        rick_and_morty_api = GraphQLAPI()
        remote_executor = GraphQLRemoteExecutor(
            url=self.rick_and_morty_api_url, verify=False
        )

        class Character:
            @rick_and_morty_api.field
            def name(self) -> str:
                ...

        # noinspection PyTypeChecker
        @rick_and_morty_api.type(is_root_type=True)
        class RickAndMortyAPI:
            @rick_and_morty_api.field
            def character(self, id: int) -> Character:
                ...

        # Add Character to the local namespace to allow for type hint resolution
        locals()["Character"] = Character

        rick_and_morty: RickAndMortyAPI = GraphQLRemoteObject(
            executor=remote_executor, api=rick_and_morty_api
        )  # type: ignore[reportIncompatibleMethodOverride]

        async def fetch():
            character = rick_and_morty.character(id=1)
            # type: ignore[reportIncompatibleMethodOverride]
            return await character.name(aio=True)  # type: ignore[reportIncompatibleMethodOverride]

        assert asyncio.run(fetch()) == "Rick Sanchez"

    def test_remote_field_call_async(self) -> None:
        """
        Tests that a remote field can be invoked with call_async.
        """
        rick_and_morty_api = GraphQLAPI()
        remote_executor = GraphQLRemoteExecutor(
            url=self.rick_and_morty_api_url, verify=False
        )

        class Character:
            @rick_and_morty_api.field
            def name(self) -> str:
                ...

        @rick_and_morty_api.type(is_root_type=True)
        class RickAndMortyAPI:
            @rick_and_morty_api.field
            def character(self, id: int) -> Character:
                ...

        # Add Character to the local namespace to allow for type hint resolution
        locals()["Character"] = Character

        rick_and_morty: RickAndMortyAPI = GraphQLRemoteObject(
            executor=remote_executor, api=rick_and_morty_api
        )  # type: ignore[reportIncompatibleMethodOverride]

        async def fetch():
            character = rick_and_morty.character(id=1)
            # noinspection PyUnresolvedReferences
            return await character.name.call_async()

        assert asyncio.run(fetch()) == "Rick Sanchez"

    def test_remote_query_fetch_str_list(self) -> None:
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class StudentRoll:
            @api.field
            def students(self) -> List[str]:
                return ["alice", "bob"]

        roll: StudentRoll = GraphQLRemoteObject(
            executor=api.executor(), api=api)  # type: ignore[reportIncompatibleMethodOverride]
        roll.fetch()  # type: ignore[reportIncompatibleMethodOverride]

        assert roll.students() == ["alice", "bob"]

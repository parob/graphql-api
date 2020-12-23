import uuid
from datetime import datetime, timedelta
from uuid import UUID

from graphql_api.api import GraphQLAPI


class TestCustomTypes:

    def test_uuid_type(self):
        api = GraphQLAPI()

        user_id = uuid.uuid4()

        # noinspection PyUnusedLocal
        @api.type(root=True)
        class Root:

            @api.field
            def name(self, id: UUID) -> str:
                assert isinstance(id, UUID)
                assert id == user_id
                return "rob"

            @api.field
            def id(self) -> UUID:
                return user_id

        executor = api.executor()

        test_name_query = f"query GetName {{ name(id: \"{user_id}\") }}"

        result = executor.execute(test_name_query)

        expected = {
            "name": "rob"
        }
        assert not result.errors
        assert result.data == expected

        test_id_query = "query GetId { id }"

        result = executor.execute(test_id_query)

        expected = {
            "id": str(user_id)
        }

        assert not result.errors
        assert result.data == expected

    def test_datetime_type(self):
        api = GraphQLAPI()

        now = datetime.now()

        @api.type(root=True)
        class Root:

            @api.field
            def add_one_hour(self, time: datetime) -> datetime:
                return time + timedelta(hours=1)

        executor = api.executor()

        test_time_query = f"query GetTimeInOneHour {{ addOneHour(time: \"{now}\") }}"

        result = executor.execute(test_time_query)

        expected = {
            "addOneHour": str(now + timedelta(hours=1))
        }
        assert not result.errors
        assert result.data == expected

    def test_json_type(self):
        api = GraphQLAPI()

        @api.type(root=True)
        class Root:

            @api.field
            def adapt_profile(self, profile: dict) -> dict:
                return {**profile, "location": "london"}

            @api.field
            def add_number(self, numbers: list) -> list:
                return [*numbers, 5]

        executor = api.executor()

        test_profile_query = r'query GetAdaptProfile {' \
                             r'     adaptProfile(profile: "{ \"name\": \"rob\", \"age\": 26 }") ' \
                             r'}'

        result = executor.execute(test_profile_query)

        expected = {
            "adaptProfile": '{"name": "rob", "age": 26, "location": "london"}'
        }
        assert not result.errors
        assert result.data == expected

        test_number_query = r'query GetAddNumber {' \
                            r'     addNumber(numbers: "[1, 2, 3, 4]") ' \
                            r'}'

        result = executor.execute(test_number_query)

        expected = {
            "addNumber": '[1, 2, 3, 4, 5]'
        }
        assert not result.errors
        assert result.data == expected

    def test_bytes_type(self):
        api = GraphQLAPI()

        data_input = b'input_bytes'
        data_output = b'output_bytes'

        @api.type(root=True)
        class Root:

            @api.field
            def byte_data(self, value: bytes) -> bytes:
                assert value == data_input
                return data_output

        executor = api.executor()

        test_bytes_query = f"query GetByteData {{ byteData(value: \"{data_input.decode('utf-8')}\") }}"

        result = executor.execute(test_bytes_query)

        expected = {
            "byteData": data_output.decode('utf-8')
        }
        assert not result.errors
        assert result.data == expected

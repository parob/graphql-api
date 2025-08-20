from dataclasses import dataclass
from enum import Enum
from typing import Optional

from pydantic import BaseModel
from graphql_api.api import GraphQLAPI


class TestGraphQL:
    def test_basic_docstring(self):
        api = GraphQLAPI()

        class Node:
            """
            NODE_DOCSTRING
            """

            @api.field
            def node_field(self, test: int) -> int:
                """
                NODE_FIELD_DOCSTRING
                """
                return test * test

        @api.type(is_root_type=True)
        class Root:
            """
            ROOT_DOCSTRING
            """

            @api.field
            def root_field(self) -> Node:
                """
                ROOT_FIELD_DOCSTRING
                """
                return Node()

        schema = api.build_schema()[0]

        assert schema.query_type.description == "ROOT_DOCSTRING"

        root_field = schema.query_type.fields["rootField"]

        assert root_field.description == "ROOT_FIELD_DOCSTRING"

        root_field_type = root_field.type.of_type

        assert root_field_type.description == "NODE_DOCSTRING"

        node_field = root_field_type.fields["nodeField"]

        assert node_field.description == "NODE_FIELD_DOCSTRING"

    def test_enum_docstring(self):
        api = GraphQLAPI()

        class TestEnumA(Enum):
            VALUE_A = "value_a"
            VALUE_B = "value_b"

        class TestEnumB(Enum):
            """
            TEST_ENUM_B_DOCSTRING
            """

            VALUE_A = "value_a"
            VALUE_B = "value_b"

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def enum_field_a(self) -> TestEnumA:
                return TestEnumA.VALUE_A

            @api.field
            def enum_field_b(self) -> TestEnumB:
                return TestEnumB.VALUE_A

        schema = api.build_schema()[0]

        enum_field = schema.query_type.fields["enumFieldA"]

        assert enum_field.type.of_type.description == "A TestEnumAEnum."

        enum_field_b = schema.query_type.fields["enumFieldB"]

        assert enum_field_b.type.of_type.description == "TEST_ENUM_B_DOCSTRING"

    def test_basic_dataclass_docstring(self):
        api = GraphQLAPI()

        @dataclass
        class Node:
            """
            NODE_DOCSTRING
            """

            string_field: Optional[str] = None
            int_field: Optional[int] = None

            @api.field
            def node_field(self, test: int) -> int:
                """
                NODE_FIELD_DOCSTRING
                """
                return test * test

        @api.type(is_root_type=True)
        class Root:
            """
            ROOT_DOCSTRING
            """

            @api.field
            def root_field(self) -> Node:
                """
                ROOT_FIELD_DOCSTRING
                """
                return Node()

        schema = api.build_schema()[0]

        assert schema.query_type.description == "ROOT_DOCSTRING"

        root_field = schema.query_type.fields["rootField"]

        assert root_field.description == "ROOT_FIELD_DOCSTRING"

        root_field_type = root_field.type.of_type

        assert root_field_type.description == "NODE_DOCSTRING"

        node_field = root_field_type.fields["nodeField"]

        assert node_field.description == "NODE_FIELD_DOCSTRING"

    def test_parsed_dataclass_docstring(self):
        api = GraphQLAPI()

        @dataclass
        class Node:
            """
            NODE_DOCSTRING
            """

            string_field: Optional[str] = None
            """STRING_FIELD_DOCSTRING"""
            int_field: Optional[int] = None
            """INT_FIELD_DOCSTRING"""

            @api.field
            def node_field(self, test: int) -> int:
                """
                NODE_FIELD_DOCSTRING
                """
                return test * test

        @api.type(is_root_type=True)
        class Root:
            """
            ROOT_DOCSTRING
            """

            @api.field
            def root_field(self) -> Node:
                """
                ROOT_FIELD_DOCSTRING
                """
                return Node()

        schema = api.build_schema()[0]

        assert schema.query_type.description == "ROOT_DOCSTRING"

        root_field = schema.query_type.fields["rootField"]

        assert root_field.description == "ROOT_FIELD_DOCSTRING"

        root_field_type = root_field.type.of_type

        assert root_field_type.description == "NODE_DOCSTRING"

        string_field = root_field_type.fields["stringField"]
        int_field = root_field_type.fields["intField"]
        node_field = root_field_type.fields["nodeField"]

        assert string_field.description == "STRING_FIELD_DOCSTRING"
        assert int_field.description == "INT_FIELD_DOCSTRING"
        assert node_field.description == "NODE_FIELD_DOCSTRING"

    def test_pydantic_docstring_filtering(self):
        api = GraphQLAPI()

        class PydanticModelNoDocstring(BaseModel):
            name: str
            age: int

        class PydanticModelWithDocstring(BaseModel):
            """Custom docstring for this Pydantic model."""
            name: str
            age: int

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def model_no_docstring(self) -> PydanticModelNoDocstring:
                return PydanticModelNoDocstring(name="test", age=25)

            @api.field
            def model_with_docstring(self) -> PydanticModelWithDocstring:
                return PydanticModelWithDocstring(name="test", age=25)

        schema = api.build_schema()[0]

        # Model without custom docstring should have None description (filtered out default)
        no_docstring_field = schema.query_type.fields["modelNoDocstring"]
        no_docstring_type = no_docstring_field.type.of_type
        assert no_docstring_type.description is None

        # Model with custom docstring should preserve it
        with_docstring_field = schema.query_type.fields["modelWithDocstring"]
        with_docstring_type = with_docstring_field.type.of_type
        assert with_docstring_type.description == "Custom docstring for this Pydantic model."

    def test_dataclass_docstring_filtering(self):
        api = GraphQLAPI()

        @dataclass
        class DataclassNoDocstring:
            name: str
            age: int

        @dataclass
        class DataclassWithDocstring:
            """Custom docstring for this dataclass."""
            name: str
            age: int

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def dataclass_no_docstring(self) -> DataclassNoDocstring:
                return DataclassNoDocstring(name="test", age=25)

            @api.field
            def dataclass_with_docstring(self) -> DataclassWithDocstring:
                return DataclassWithDocstring(name="test", age=25)

        schema = api.build_schema()[0]

        # Dataclass without custom docstring should have None description (filtered out auto-generated constructor)
        no_docstring_field = schema.query_type.fields["dataclassNoDocstring"]
        no_docstring_type = no_docstring_field.type.of_type
        assert no_docstring_type.description is None

        # Dataclass with custom docstring should preserve it
        with_docstring_field = schema.query_type.fields["dataclassWithDocstring"]
        with_docstring_type = with_docstring_field.type.of_type
        assert with_docstring_type.description == "Custom docstring for this dataclass."

    def test_google_dataclass_docstring(self):
        api = GraphQLAPI()

        @dataclass
        class Node:
            """
            NODE_DOCSTRING

            Args:
                string_field: STRING_FIELD_DOCSTRING
                int_field: INT_FIELD_DOCSTRING
            """

            string_field: Optional[str] = None
            int_field: Optional[int] = None

            @api.field
            def node_field(self, test: int) -> int:
                """
                NODE_FIELD_DOCSTRING
                """
                return test * test

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def root_field(self) -> Node:
                return Node()

        schema = api.build_schema()[0]
        root_field = schema.query_type.fields["rootField"]
        root_field_type = root_field.type.of_type

        string_field = root_field_type.fields["stringField"]
        int_field = root_field_type.fields["intField"]
        node_field = root_field_type.fields["nodeField"]

        assert string_field.description == "STRING_FIELD_DOCSTRING"
        assert int_field.description == "INT_FIELD_DOCSTRING"
        assert node_field.description == "NODE_FIELD_DOCSTRING"

    def test_pydantic_docstring_filtering(self):
        api = GraphQLAPI()

        class PydanticModelNoDocstring(BaseModel):
            name: str
            age: int

        class PydanticModelWithDocstring(BaseModel):
            """Custom docstring for this Pydantic model."""
            name: str
            age: int

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def model_no_docstring(self) -> PydanticModelNoDocstring:
                return PydanticModelNoDocstring(name="test", age=25)

            @api.field
            def model_with_docstring(self) -> PydanticModelWithDocstring:
                return PydanticModelWithDocstring(name="test", age=25)

        schema = api.build_schema()[0]

        # Model without custom docstring should have None description (filtered out default)
        no_docstring_field = schema.query_type.fields["modelNoDocstring"]
        no_docstring_type = no_docstring_field.type.of_type
        assert no_docstring_type.description is None

        # Model with custom docstring should preserve it
        with_docstring_field = schema.query_type.fields["modelWithDocstring"]
        with_docstring_type = with_docstring_field.type.of_type
        assert with_docstring_type.description == "Custom docstring for this Pydantic model."

    def test_dataclass_docstring_filtering(self):
        api = GraphQLAPI()

        @dataclass
        class DataclassNoDocstring:
            name: str
            age: int

        @dataclass
        class DataclassWithDocstring:
            """Custom docstring for this dataclass."""
            name: str
            age: int

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def dataclass_no_docstring(self) -> DataclassNoDocstring:
                return DataclassNoDocstring(name="test", age=25)

            @api.field
            def dataclass_with_docstring(self) -> DataclassWithDocstring:
                return DataclassWithDocstring(name="test", age=25)

        schema = api.build_schema()[0]

        # Dataclass without custom docstring should have None description (filtered out auto-generated constructor)
        no_docstring_field = schema.query_type.fields["dataclassNoDocstring"]
        no_docstring_type = no_docstring_field.type.of_type
        assert no_docstring_type.description is None

        # Dataclass with custom docstring should preserve it
        with_docstring_field = schema.query_type.fields["dataclassWithDocstring"]
        with_docstring_type = with_docstring_field.type.of_type
        assert with_docstring_type.description == "Custom docstring for this dataclass."

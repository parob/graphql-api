from dataclasses import dataclass
from enum import Enum
from typing import Optional

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

        query_type = schema.query_type
        assert query_type is not None, "query_type should not be None"
        assert query_type.description == "ROOT_DOCSTRING"

        root_field = query_type.fields.get("rootField")
        assert root_field is not None, "rootField should exist"
        assert root_field.description == "ROOT_FIELD_DOCSTRING"

        # Assuming root_field.type is GraphQLNonNull or similar wrapper
        root_field_type_wrapper = root_field.type
        assert hasattr(root_field_type_wrapper, "of_type"), "root_field.type should be a wrapper type"
        root_field_type = root_field_type_wrapper.of_type
        assert root_field_type is not None, "root_field_type (unwrapped) should not be None"
        assert root_field_type.description == "NODE_DOCSTRING"

        assert hasattr(root_field_type, "fields"), "root_field_type should have fields"
        node_field = root_field_type.fields.get("nodeField")
        assert node_field is not None, "nodeField should exist"
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

        query_type_b = schema.query_type
        assert query_type_b is not None, "query_type_b should not be None"

        enum_field = query_type_b.fields.get("enumFieldA")
        assert enum_field is not None, "enum_fieldA should exist"
        assert hasattr(enum_field.type, "of_type"), "enum_field.type should be a wrapper type"
        enum_field_type_a = enum_field.type.of_type
        assert enum_field_type_a is not None, "enum_field_type_a unwrapped should not be None"
        assert enum_field_type_a.description == "A TestEnumAEnum."

        enum_field_b = query_type_b.fields.get("enumFieldB")
        assert enum_field_b is not None, "enum_field_b should exist"
        assert hasattr(enum_field_b.type, "of_type"), "enum_field_b.type should be a wrapper type"
        enum_field_type_b = enum_field_b.type.of_type
        assert enum_field_type_b is not None, "enum_field_type_b unwrapped should not be None"
        assert enum_field_type_b.description == "TEST_ENUM_B_DOCSTRING"

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

        query_type_c = schema.query_type
        assert query_type_c is not None, "query_type_c should not be None"
        assert query_type_c.description == "ROOT_DOCSTRING"

        root_field = query_type_c.fields.get("rootField")
        assert root_field is not None, "root_field in dataclass test should exist"
        assert root_field.description == "ROOT_FIELD_DOCSTRING"

        assert hasattr(root_field.type, "of_type"), "root_field.type in dataclass test should be a wrapper"
        root_field_type = root_field.type.of_type
        assert root_field_type is not None, "root_field_type unwrapped in dataclass test should not be None"
        assert root_field_type.description == "NODE_DOCSTRING"

        assert hasattr(root_field_type, "fields"), "root_field_type in dataclass test should have fields"
        node_field = root_field_type.fields.get("nodeField")
        assert node_field is not None, "nodeField in dataclass test should exist"
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

        query_type_d = schema.query_type
        assert query_type_d is not None, "query_type_d should not be None"
        assert query_type_d.description == "ROOT_DOCSTRING"

        root_field = query_type_d.fields.get("rootField")
        assert root_field is not None, "root_field in parsed dataclass test should exist"
        assert root_field.description == "ROOT_FIELD_DOCSTRING"

        assert hasattr(root_field.type, "of_type"), "root_field.type in parsed dataclass test should be a wrapper"
        root_field_type = root_field.type.of_type
        assert root_field_type is not None, "root_field_type unwrapped in parsed dataclass test should not be None"
        assert root_field_type.description == "NODE_DOCSTRING"

        assert hasattr(root_field_type, "fields"), "root_field_type in parsed dataclass test should have fields"
        string_field = root_field_type.fields.get("stringField")
        int_field = root_field_type.fields.get("intField")
        node_field = root_field_type.fields.get("nodeField")

        assert string_field.description == "STRING_FIELD_DOCSTRING"
        assert int_field.description == "INT_FIELD_DOCSTRING"
        assert node_field.description == "NODE_FIELD_DOCSTRING"

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

        query_type_e = schema.query_type
        assert query_type_e is not None, "query_type_e should not be None"

        root_field = query_type_e.fields.get("rootField")
        assert root_field is not None, "root_field in google dataclass test should exist"

        assert hasattr(root_field.type, "of_type"), "root_field.type in google dataclass test should be a wrapper"
        root_field_type = root_field.type.of_type
        assert root_field_type is not None, "root_field_type unwrapped in google dataclass test should not be None"

        assert hasattr(root_field_type, "fields"), "root_field_type in google dataclass test should have fields"
        string_field = root_field_type.fields.get("stringField")
        int_field = root_field_type.fields.get("intField")
        node_field = root_field_type.fields.get("nodeField")

        assert string_field.description == "STRING_FIELD_DOCSTRING"
        assert int_field.description == "INT_FIELD_DOCSTRING"
        assert node_field.description == "NODE_FIELD_DOCSTRING"

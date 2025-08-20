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

    def test_builtin_inheritance_docstring_filtering(self):
        # Test the _get_class_description function directly since the GraphQL mapping
        # may not work well with Exception subclasses
        from graphql_api.mapper import _get_class_description

        # Test inheritance from Exception (common base class with verbose docstring)
        class ExceptionSubclass(Exception):
            pass

        class ExceptionSubclassWithDoc(Exception):
            """Custom exception subclass docstring."""
            pass

        # Test inheritance from built-in types
        class DictSubclass(dict):
            pass

        class DictSubclassWithDoc(dict):
            """Custom dict subclass docstring."""
            pass

        # Test inheritance from a verbose base class (>200 chars)
        class VerboseBase:
            """
            This is a very long base class docstring that goes on and on and on.
            It has multiple paragraphs and sections and is definitely too verbose
            for a GraphQL API description. This should be filtered out when inherited
            by subclasses because it's longer than 200 characters and likely auto-generated.
            """
            pass

        class InheritsVerbose(VerboseBase):
            pass

        class InheritsVerboseWithDoc(VerboseBase):
            """Custom docstring for verbose inheritance."""
            pass

        # Test the filtering logic directly
        assert _get_class_description(ExceptionSubclass) is None  # Inherited from Exception
        assert _get_class_description(ExceptionSubclassWithDoc) == "Custom exception subclass docstring."

        assert _get_class_description(DictSubclass) is None  # Inherited from dict
        assert _get_class_description(DictSubclassWithDoc) == "Custom dict subclass docstring."

        assert _get_class_description(InheritsVerbose) is None  # Verbose inherited docstring
        assert _get_class_description(InheritsVerboseWithDoc) == "Custom docstring for verbose inheritance."

    def test_long_user_docstrings_preserved(self):
        api = GraphQLAPI()
        from graphql_api.mapper import _get_class_description

        # Test a long user-written docstring that should be preserved
        class ClassWithLongUserDocstring:
            """
            This is a very long user-written docstring that provides detailed documentation
            about this class. It explains the purpose, usage patterns, and important details
            that developers need to know. This is intentional documentation written by the
            developer to help other developers understand how to use this class effectively.

            The class handles complex business logic and provides multiple methods for different
            use cases. Each method is carefully designed to work together as part of a cohesive
            API that makes the developer's life easier.

            Examples:
                obj = ClassWithLongUserDocstring()
                result = obj.process_data(input_data)

            Note: This docstring is intentionally long to test that user-written documentation
            is preserved even when it exceeds the typical length thresholds we use to filter
            out auto-generated or inherited docstrings from built-in types.
            """
            def __init__(self, name: str):
                self.name = name

        # Test Pydantic model with long user docstring
        class PydanticModelWithLongDocstring(BaseModel):
            """
            This is a comprehensive Pydantic model that represents complex business data.

            It includes multiple fields that work together to provide a complete picture
            of the entity being modeled. The validation rules ensure data integrity
            while the serialization capabilities make it easy to work with JSON APIs.

            Field Descriptions:
                - name: The primary identifier for this entity
                - description: Detailed information about the entity
                - metadata: Additional key-value pairs for extensibility
                - created_at: Timestamp when this entity was first created
                - updated_at: Timestamp of the most recent modification

            This model is designed to be flexible enough to handle various use cases
            while maintaining strict type safety and validation rules.
            """
            name: str
            description: str

        # Test dataclass with long user docstring
        @dataclass
        class DataclassWithLongDocstring:
            """
            A comprehensive dataclass representing a complex domain entity.

            This dataclass encapsulates all the important properties and behaviors
            needed to work with this particular type of domain object. It provides
            a clean, type-safe interface while maintaining good performance characteristics.

            The design follows domain-driven design principles, ensuring that the
            data structure accurately reflects the business concepts it represents.
            All fields are carefully chosen to provide the necessary information
            without introducing unnecessary complexity.

            Usage patterns include creation, modification, serialization, and
            integration with various persistence layers and external APIs.
            """
            name: str
            value: int

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def regular_class(self) -> ClassWithLongUserDocstring:
                return ClassWithLongUserDocstring(name="test")

            @api.field
            def pydantic_model(self) -> PydanticModelWithLongDocstring:
                return PydanticModelWithLongDocstring(name="test", description="test desc")

            @api.field
            def dataclass_model(self) -> DataclassWithLongDocstring:
                return DataclassWithLongDocstring(name="test", value=42)

        schema = api.build_schema()[0]

        # Check that long user-written docstrings are preserved in Pydantic models
        pydantic_field = schema.query_type.fields["pydanticModel"]
        pydantic_type = pydantic_field.type.of_type
        assert pydantic_type.description is not None
        assert len(pydantic_type.description) > 200  # Should be the full user docstring
        assert "comprehensive Pydantic model" in pydantic_type.description

        # Check that long user-written docstrings are preserved in dataclasses
        dataclass_field = schema.query_type.fields["dataclassModel"]
        dataclass_type = dataclass_field.type.of_type
        assert dataclass_type.description is not None
        assert len(dataclass_type.description) > 200  # Should be the full user docstring
        assert "comprehensive dataclass" in dataclass_type.description

        # Test the filtering function directly on regular classes
        long_user_docstring = _get_class_description(ClassWithLongUserDocstring, None)
        assert long_user_docstring is not None
        assert len(long_user_docstring) > 500  # Should be the full docstring
        assert "intentional documentation" in long_user_docstring

    def test_docstring_truncation_feature(self):
        """Test that docstrings are truncated when max_docstring_length is set."""

        # Test Pydantic model with long docstring
        class PydanticModelWithLongDocstring(BaseModel):
            """
            This is a comprehensive Pydantic model that represents complex business data.

            It includes multiple fields that work together to provide a complete picture
            of the entity being modeled. The validation rules ensure data integrity
            while the serialization capabilities make it easy to work with JSON APIs.

            Field Descriptions:
                - name: The primary identifier for this entity
                - description: Detailed information about the entity
                - metadata: Additional key-value pairs for extensibility
                - created_at: Timestamp when this entity was first created
                - updated_at: Timestamp of the most recent modification

            This model is designed to be flexible enough to handle various use cases
            while maintaining strict type safety and validation rules.
            """
            name: str
            description: str

        # Test dataclass with long docstring
        @dataclass
        class DataclassWithLongDocstring:
            """
            A comprehensive dataclass representing a complex domain entity.

            This dataclass encapsulates all the important properties and behaviors
            needed to work with this particular type of domain object. It provides
            a clean, type-safe interface while maintaining good performance characteristics.

            The design follows domain-driven design principles, ensuring that the
            data structure accurately reflects the business concepts it represents.
            All fields are carefully chosen to provide the necessary information
            without introducing unnecessary complexity.

            Usage patterns include creation, modification, serialization, and
            integration with various persistence layers and external APIs.
            """
            name: str
            value: int

        # Test with truncation enabled (300 chars)
        api_with_truncation = GraphQLAPI(max_docstring_length=300)

        @api_with_truncation.type(is_root_type=True)
        class Root:
            @api_with_truncation.field
            def pydantic_model(self) -> PydanticModelWithLongDocstring:
                return PydanticModelWithLongDocstring(name="test", description="test desc")

            @api_with_truncation.field
            def dataclass_model(self) -> DataclassWithLongDocstring:
                return DataclassWithLongDocstring(name="test", value=42)

        schema = api_with_truncation.build_schema()[0]

        # Check that Pydantic docstring is truncated
        pydantic_field = schema.query_type.fields["pydanticModel"]
        pydantic_type = pydantic_field.type.of_type
        assert pydantic_type.description is not None
        assert len(pydantic_type.description) <= 303  # 300 + "..."
        assert pydantic_type.description.endswith("...")
        assert "comprehensive Pydantic model" in pydantic_type.description

        # Check that dataclass docstring is truncated
        dataclass_field = schema.query_type.fields["dataclassModel"]
        dataclass_type = dataclass_field.type.of_type
        assert dataclass_type.description is not None
        assert len(dataclass_type.description) <= 303  # 300 + "..."
        assert dataclass_type.description.endswith("...")
        assert "comprehensive dataclass" in dataclass_type.description

        # Test with no truncation (None/unlimited)
        api_no_truncation = GraphQLAPI(max_docstring_length=None)

        @api_no_truncation.type(is_root_type=True)
        class RootNoTruncation:
            @api_no_truncation.field
            def pydantic_model(self) -> PydanticModelWithLongDocstring:
                return PydanticModelWithLongDocstring(name="test", description="test desc")

        schema_no_truncation = api_no_truncation.build_schema()[0]

        # Check that docstring is not truncated
        pydantic_field_no_truncation = schema_no_truncation.query_type.fields["pydanticModel"]
        pydantic_type_no_truncation = pydantic_field_no_truncation.type.of_type
        assert pydantic_type_no_truncation.description is not None
        assert len(pydantic_type_no_truncation.description) > 500  # Should be full length
        assert not pydantic_type_no_truncation.description.endswith("...")
        assert "validation rules" in pydantic_type_no_truncation.description  # Text that would be cut off

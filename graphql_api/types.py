import binascii
import collections.abc
import datetime
import json
import uuid
import enum

from typing import Any, Dict, List, Optional, Type, Union

from graphql import (
    GraphQLEnumType,
    GraphQLScalarType,
    StringValueNode,
    Undefined,
    ValueNode,
)
from graphql.pyutils import UndefinedType
from graphql.language import ast


class GraphQLMappedEnumType(GraphQLEnumType):
    """A GraphQL enum backed by a Python Enum.

    Inputs (inline literals and variables) are coerced to the Python Enum member,
    and outputs accept either the member or its value.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enum_type: Optional[Type[enum.Enum]] = None

    def _to_enum_member(self, result):
        if result is not Undefined and result is not None and self.enum_type is not None:
            try:
                return self.enum_type(result)
            except (ValueError, KeyError, TypeError):
                # Invalid enum value or type casting error
                return Undefined
        return result

    def coerce_input_literal(self, value_node, hide_suggestions=False):
        return self._to_enum_member(
            super().coerce_input_literal(value_node, hide_suggestions)
        )

    def coerce_input_value(self, input_value, hide_suggestions=False):
        return self._to_enum_member(
            super().coerce_input_value(input_value, hide_suggestions)
        )

    def coerce_output_value(self, output_value) -> Union[str, None, UndefinedType]:
        if output_value and isinstance(output_value, collections.abc.Hashable):
            # For enums, always return the enum name (which matches the GraphQL enum value)
            if isinstance(output_value, enum.Enum):
                return output_value.name
            # For non-enum values, try to look them up in the value lookup.
            # This handles cases where the value might be a string representation.
            lookup_value = self._value_lookup.get(output_value)
            if lookup_value:
                return lookup_value
            # If lookup fails, the value is invalid
            return Undefined

        return None


def parse_uuid_literal(
    value_node: ValueNode, _variables: Any = None
) -> Optional[uuid.UUID]:
    """Parse a UUID from a GraphQL literal value node.

    Returns a UUID object if valid, Undefined if invalid format, or None for non-string nodes.
    """
    if isinstance(value_node, StringValueNode):
        try:
            return uuid.UUID(value_node.value)
        except ValueError:
            return Undefined
    return Undefined


def parse_uuid_value(value: Any) -> uuid.UUID:
    """Parse a UUID from a GraphQL variable value.

    Accepts both string and uuid.UUID inputs, returns a uuid.UUID object.
    """
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise ValueError(f"Invalid UUID value: {value!r}")


GraphQLUUID = GraphQLScalarType(
    name="UUID",
    description="The `UUID` scalar type represents a unique identifer.",
    coerce_output_value=str,
    coerce_input_value=parse_uuid_value,
    coerce_input_literal=parse_uuid_literal,
)


def serialize_datetime(dt):
    return dt.isoformat(sep=" ")


def parse_datetime_value(value):
    # Handle ISO 8601 Z suffix - replace with +00:00 for fromisoformat
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    # Try Python's built-in ISO 8601 parser first (handles timezone offsets)
    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        pass

    # Fallback to legacy formats for backward compatibility
    datetime_formats = [
        "%Y-%m-%dT%H:%M:%S.%f",  # ISO 8601 with microseconds
        "%Y-%m-%dT%H:%M:%S",     # ISO 8601 without microseconds
        "%Y-%m-%d %H:%M:%S.%f",  # Space separator with microseconds
        "%Y-%m-%d %H:%M:%S",     # Space separator without microseconds
    ]

    for datetime_format in datetime_formats:
        try:
            return datetime.datetime.strptime(value, datetime_format)
        except ValueError:
            pass

    raise ValueError(
        f"Datetime {value} did not fit any of the formats {datetime_formats}."
    )


def parse_datetime_literal(value_node: ValueNode, _variables: Any = None):
    if isinstance(value_node, StringValueNode):
        return parse_datetime_value(value_node.value)


GraphQLDateTime = GraphQLScalarType(
    name="DateTime",
    description="The `DateTime` scalar type represents a datetime, "
    "the datetime should be in the format `2018-01-22 17:46:32`",
    coerce_output_value=serialize_datetime,
    coerce_input_value=parse_datetime_value,
    coerce_input_literal=parse_datetime_literal,
)


def serialize_date(dt: datetime.date):
    return dt.isoformat()


def parse_date_value(value):
    date_formats = ["%Y-%m-%d"]

    for date_format in date_formats:
        try:
            return datetime.datetime.strptime(value, date_format).date()
        except ValueError:
            pass

    raise ValueError(
        f"Date{value} did not fit any " f"of the formats {date_formats}.")


def parse_date_literal(value_node: ValueNode, _variables: Any = None):
    if isinstance(value_node, StringValueNode):
        return parse_date_value(value_node.value)


GraphQLDate = GraphQLScalarType(
    name="Date",
    description="The `Date` scalar type represents a datetime, "
    "the datetime should be in the format `2018-01-22`",
    coerce_output_value=serialize_date,
    coerce_input_value=parse_date_value,
    coerce_input_literal=parse_date_literal,
)


JsonType = Union[None, int, float, str, bool, List, Dict]


def serialize_json(data: JsonType) -> JsonType:
    return data


def parse_json_value(value: Union[str, JsonType]) -> JsonType:
    # If it's already a dict/list/etc (from GraphQL variables), return as-is
    if isinstance(value, (dict, list, bool, int, float, type(None))):
        return value
    # If it's a string, parse it as JSON
    if isinstance(value, str):
        return json.loads(value)
    # Fallback: try to parse as JSON string
    return json.loads(value)


def parse_json_literal(value_node: ValueNode, _variables: Any = None) -> JsonType:
    if isinstance(value_node, ast.StringValueNode):
        return parse_json_value(value_node.value)
    if isinstance(value_node, ast.BooleanValueNode):
        return value_node.value
    if isinstance(value_node, ast.FloatValueNode):
        return value_node.value


GraphQLJSON = GraphQLScalarType(
    name="JSON",
    description="The `JSON` scalar type represents JSON values as specified by"
    " [ECMA-404](http://www.ecma-international.org/"
    "publications/files/ECMA-ST/ECMA-404.pdf).",
    coerce_output_value=serialize_json,
    coerce_input_value=parse_json_value,
    coerce_input_literal=parse_json_literal,
)


def serialize_bytes(bytes: bytes) -> str:
    try:
        data = bytes.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, Exception):
        data = "UTF-8 ENCODED PREVIEW: " + \
            bytes.decode("utf-8", errors="ignore")
    return data


def parse_bytes_value(value: str) -> bytes:
    data = bytes(value, "utf-8")
    return data


def parse_bytes_literal(value_node: ValueNode, _variables: Any = None):
    if isinstance(value_node, ast.StringValueNode):
        return parse_bytes_value(value_node.value)


GraphQLBytes = GraphQLScalarType(
    name="Bytes",
    description="The `Bytes` scalar type expects and returns a "
    "Byte array in UTF-8 string format that represents the Bytes. "
    "If the data is not UTF-encodable the errors will be ignored",
    coerce_output_value=serialize_bytes,
    coerce_input_value=parse_bytes_value,
    coerce_input_literal=parse_bytes_literal,
)

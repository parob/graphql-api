import binascii
import datetime
import json
import uuid
import enum

from typing import Any, Dict, List, Optional, Type, Union, cast

from graphql import (
    GraphQLEnumType,
    GraphQLScalarType,
    StringValueNode,
    Undefined,
    ValueNode,
)
from graphql.language import ast


class GraphQLMappedEnumType(GraphQLEnumType):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enum_type: Optional[Type[enum.Enum]] = None

    def parse_literal(self, *args, **kwargs):
        result = super().parse_literal(*args, **kwargs)
        if result is not Undefined and result is not None and getattr(self, "enum_type", None):
            try:
                enum_type: Optional[Type[enum.Enum]] = self.enum_type
                if enum_type is None:
                    return result
                return cast(Type[enum.Enum], enum_type)(result)
            except Exception:
                return Undefined
        return result

    def parse_value(self, value):
        """Coerce incoming variable values to the mapped Python Enum instance.

        GraphQL variables use `parse_value`, while inline literals use
        `parse_literal`. Ensure both paths produce the Python Enum.
        """
        result = super().parse_value(value)
        if result is not Undefined and result is not None and getattr(self, "enum_type", None):
            try:
                enum_type: Optional[Type[enum.Enum]] = self.enum_type
                if enum_type is None:
                    return result
                return cast(Type[enum.Enum], enum_type)(result)
            except Exception:
                return Undefined
        return result


def parse_uuid_literal(
    value_node: ValueNode, _variables: Any = None
) -> Optional[uuid.UUID | ValueError]:
    if isinstance(value_node, StringValueNode):
        try:
            return uuid.UUID(value_node.value)
        except ValueError:
            return Undefined


GraphQLUUID = GraphQLScalarType(
    name="UUID",
    description="The `UUID` scalar type represents a unique identifer.",
    serialize=str,
    parse_value=str,
    parse_literal=parse_uuid_literal,
)


def serialize_datetime(dt):
    return dt.isoformat(sep=" ")


def parse_datetime_value(value):
    datetime_formats = ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f"]

    for datetime_format in datetime_formats:
        try:
            return datetime.datetime.strptime(value, datetime_format)
        except ValueError:
            pass

    raise ValueError(
        f"Datetime {value} did not fit any " f"of the formats {datetime_formats}."
    )


def parse_datetime_literal(value_node: ValueNode, _variables: Any = None):
    if isinstance(value_node, StringValueNode):
        return parse_datetime_value(value_node.value)


GraphQLDateTime = GraphQLScalarType(
    name="DateTime",
    description="The `DateTime` scalar type represents a datetime, "
    "the datetime should be in the format `2018-01-22 17:46:32`",
    serialize=serialize_datetime,
    parse_value=parse_datetime_value,
    parse_literal=parse_datetime_literal,
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

    raise ValueError(f"Date{value} did not fit any " f"of the formats {date_formats}.")


def parse_date_literal(value_node: ValueNode, _variables: Any = None):
    if isinstance(value_node, StringValueNode):
        return parse_date_value(value_node.value)


GraphQLDate = GraphQLScalarType(
    name="Date",
    description="The `Date` scalar type represents a datetime, "
    "the datetime should be in the format `2018-01-22`",
    serialize=serialize_date,
    parse_value=parse_date_value,
    parse_literal=parse_date_literal,
)


JsonType = Union[None, int, float, str, bool, List, Dict]


def serialize_json(data: JsonType) -> str:
    return json.dumps(data)


def parse_json_value(value: str) -> JsonType:
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
    serialize=serialize_json,
    parse_value=parse_json_value,
    parse_literal=parse_json_literal,
)


def serialize_bytes(bytes: bytes) -> str:
    try:
        data = bytes.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, Exception):
        data = "UTF-8 ENCODED PREVIEW: " + bytes.decode("utf-8", errors="ignore")
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
    "If the data is not UTF-encodable the erros will be ignored",
    serialize=serialize_bytes,
    parse_value=parse_bytes_value,
    parse_literal=parse_bytes_literal,
)

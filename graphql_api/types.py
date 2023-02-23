import binascii
import datetime
import json
import uuid
from typing import Dict, Union, List

from graphql import GraphQLScalarType, StringValueNode, Undefined
from graphql.language import ast


def parse_uuid_literal(ast):
    if isinstance(ast, StringValueNode):
        try:
            return uuid.UUID(ast.value)
        except ValueError:
            return Undefined


GraphQLUUID = GraphQLScalarType(
    name='UUID',
    description='The `UUID` scalar type represents a unique identifer.',
    serialize=str,
    parse_value=str,
    parse_literal=parse_uuid_literal)


def serialize_datetime(dt):
    return dt.isoformat(sep=" ")


def parse_datetime_value(value):
    datetime_formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f"
    ]

    for datetime_format in datetime_formats:
        try:
            return datetime.datetime.strptime(value, datetime_format)
        except ValueError:
            pass

    raise ValueError(f"Datetime {value} did not fit any "
                     f"of the formats {datetime_formats}.")


def parse_datetime_literal(node):
    if isinstance(node, StringValueNode):
        return parse_datetime_value(node.value)


GraphQLDateTime = GraphQLScalarType(
    name='DateTime',
    description='The `DateTime` scalar type represents a datetime, '
                'the datetime should be in the format `2018-01-22 17:46:32`',
    serialize=serialize_datetime,
    parse_value=parse_datetime_value,
    parse_literal=parse_datetime_literal)


JsonType = Union[None, int, float, str, bool, List, Dict]


def serialize_json(data: JsonType) -> str:
    return json.dumps(data)


def parse_json_value(value: str) -> JsonType:
    return json.loads(value)


def parse_json_literal(node) -> JsonType:
    if isinstance(node, ast.StringValueNode):
        return parse_json_value(node.value)
    if isinstance(node, ast.BooleanValueNode):
        return node.value
    if isinstance(node, ast.FloatValueNode):
        return node.value


GraphQLJSON = GraphQLScalarType(
    name='JSON',
    description='The `JSON` scalar type represents JSON values as specified by'
                ' [ECMA-404](http://www.ecma-international.org/'
                'publications/files/ECMA-ST/ECMA-404.pdf).',
    serialize=serialize_json,
    parse_value=parse_json_value,
    parse_literal=parse_json_literal)


def serialize_bytes(bytes: bytes) -> str:
    try:
        data = bytes.decode('utf-8')
    except (binascii.Error, UnicodeDecodeError, Exception):
        data = "UTF-8 ENCODED PREVIEW: " + \
               bytes.decode('utf-8', errors="ignore")
    return data


def parse_bytes_value(value: str) -> bytes:
    data = bytes(value, 'utf-8')
    return data


def parse_bytes_literal(node):
    if isinstance(node, ast.StringValueNode):
        return parse_bytes_value(node.value)


GraphQLBytes = GraphQLScalarType(
    name='Bytes',
    description='The `Bytes` scalar type expects and returns a '
                'Byte array in UTF-8 string format that represents the Bytes. '
                'If the data is not UTF-encodable the erros will be ignored',
    serialize=serialize_bytes,
    parse_value=parse_bytes_value,
    parse_literal=parse_bytes_literal
)

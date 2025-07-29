from graphql import GraphQLEnumType, GraphQLEnumValue, GraphQLScalarType

from graphql_api.types import parse_json_literal, parse_json_value, serialize_json

_Any = GraphQLScalarType(
    name="_Any",
    description="The `_Any` scalar type can represent any JSON-based value.",
    serialize=serialize_json,
    parse_value=parse_json_value,
    parse_literal=parse_json_literal,
)
FieldSet = GraphQLScalarType(
    name="FieldSet",
    description="The `FieldSet` scalar type represents a set of fields "
    "(used in Federation).",
)
LinkImport = GraphQLScalarType(
    name="link__Import",
    description="The `link__Import` scalar type represents an import specification for"
    " the @link directive (used in Federation).",
)
FederationContextFieldValue = GraphQLScalarType(
    name="federation__ContextFieldValue",
    description="Represents a field value extracted from a GraphQL context "
    "(used in Federation).",
)
FederationScope = GraphQLScalarType(
    name="federation__Scope",
    description="Represents an OAuth (or similar) scope (used in Federation).",
)
FederationPolicy = GraphQLScalarType(
    name="federation__Policy",
    description="Represents a policy definition in Federation.",
)
LinkPurposeEnum = GraphQLEnumType(
    name="link__Purpose",
    values={
        "SECURITY": GraphQLEnumValue(
            value="SECURITY",
            description="`SECURITY` features provide metadata necessary to securely "
            "resolve fields (used in Federation).",
        ),
        "EXECUTION": GraphQLEnumValue(
            value="EXECUTION",
            description="`EXECUTION` features provide metadata necessary for operation"
            " execution (used in Federation).",
        ),
    },
)
federation_types = [
    _Any,
    FieldSet,
    LinkImport,
    FederationContextFieldValue,
    FederationScope,
    FederationPolicy,
    LinkPurposeEnum,
]

from graphql_api.decorators import type, field
from graphql_api.context import GraphQLContext
from graphql_api.directives import SchemaDirective

from graphql import (
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLString,
    GraphQLList,
    GraphQLNonNull,
    DirectiveLocation,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLScalarType,
)

from graphql_api.print_directives import (
    print_filtered_schema,
    is_defined_type,
    is_specified_directive,
)
from graphql_api.types import serialize_json, parse_json_value, parse_json_literal


# scalar _Any
_Any = GraphQLScalarType(
    name="_Any",
    description="The `_Any` scalar type can represent any JSON-based value.",
    serialize=serialize_json,
    parse_value=parse_json_value,
    parse_literal=parse_json_literal,
)


# scalar FieldSet
FieldSet = GraphQLScalarType(
    name="FieldSet",
    description="The `FieldSet` scalar type represents a set of fields "
    "(used in Federation).",
)


# scalar link__Import
LinkImport = GraphQLScalarType(
    name="link__Import",
    description="The `link__Import` scalar type represents an import specification for"
    " the @link directive (used in Federation).",
)


# scalar federation__ContextFieldValue
FederationContextFieldValue = GraphQLScalarType(
    name="federation__ContextFieldValue",
    description="Represents a field value extracted from a GraphQL context "
    "(used in Federation).",
)


# scalar federation__Scope
FederationScope = GraphQLScalarType(
    name="federation__Scope",
    description="Represents an OAuth (or similar) scope (used in Federation).",
)


# scalar federation__Policy
FederationPolicy = GraphQLScalarType(
    name="federation__Policy",
    description="Represents a policy definition in Federation.",
)

# enum link__Purpose {
# """
# `SECURITY` features provide metadata necessary to securely resolve fields.
# """
# SECURITY
#
# """
# `EXECUTION` features provide metadata necessary for operation execution.
# """
# EXECUTION
# }
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


# @external on FIELD_DEFINITION | OBJECT
external = SchemaDirective(
    name="external",
    locations=[DirectiveLocation.FIELD_DEFINITION, DirectiveLocation.OBJECT],
    description="Marks a field or type as defined in another service",
)


# @requires(fields: FieldSet!) on FIELD_DEFINITION
requires = SchemaDirective(
    name="requires",
    locations=[DirectiveLocation.FIELD_DEFINITION],
    description="Specifies required input fieldset from base type for a resolver",
    args={
        "fields": GraphQLArgument(
            GraphQLNonNull(FieldSet),
            description="Field set required from the parent type",
        )
    },
)


# @provides(fields: FieldSet!) on FIELD_DEFINITION
provides = SchemaDirective(
    name="provides",
    locations=[DirectiveLocation.FIELD_DEFINITION],
    description="Used to indicate which fields a resolver can provide to other "
    "subgraphs (used in Federation).",
    args={
        "fields": GraphQLArgument(
            GraphQLNonNull(FieldSet),
            description="Field set that this field or resolver provides",
        )
    },
)


# @key(fields: FieldSet!, resolvable: Boolean = true) repeatable on OBJECT | INTERFACE
key = SchemaDirective(
    name="key",
    locations=[DirectiveLocation.OBJECT, DirectiveLocation.INTERFACE],
    description="Designates a combination of fields that uniquely identifies an "
    "entity object (used in Federation).",
    args={
        "fields": GraphQLArgument(
            GraphQLNonNull(FieldSet),
            description="Field set that uniquely identifies this type",
        ),
        "resolvable": GraphQLArgument(
            GraphQLBoolean,
            default_value=True,
            description="Indicates if the key fields are resolvable by the subgraph",
        ),
    },
    is_repeatable=True,
)


# @link(url: String!, as: String, for: link__Purpose, import: [link__Import])
#    repeatable on SCHEMA
link = SchemaDirective(
    name="link",
    locations=[DirectiveLocation.SCHEMA],
    description="Provides a way to link to and import definitions from external "
    "schemas (used in Federation).",
    args={
        "url": GraphQLArgument(
            GraphQLNonNull(GraphQLString),
            description="Specifies the URL of the schema to link",
        ),
        # 'as' is optional
        "as": GraphQLArgument(
            GraphQLString, description="Override the namespace for the linked schema"
        ),
        # 'for' is typically a custom enum (link__Purpose).
        "for": GraphQLArgument(
            LinkPurposeEnum, description="Specifies the purpose for linking"
        ),
        # 'import' is typically a list of references from the external schema
        "import": GraphQLArgument(
            GraphQLList(LinkImport),
            description="Elements to import from the linked schema",
        ),
    },
    is_repeatable=True,
)


# @shareable repeatable on OBJECT | FIELD_DEFINITION
shareable = SchemaDirective(
    name="shareable",
    locations=[DirectiveLocation.OBJECT, DirectiveLocation.FIELD_DEFINITION],
    description="Indicates the field or type can safely be resolved by multiple "
    "subgraphs (used in Federation).",
    is_repeatable=True,
)


# @inaccessible on FIELD_DEFINITION | OBJECT | INTERFACE | UNION
#                | ARGUMENT_DEFINITION | SCALAR | ENUM | ENUM_VALUE
#                | INPUT_OBJECT | INPUT_FIELD_DEFINITION
inaccessible = SchemaDirective(
    name="inaccessible",
    locations=[
        DirectiveLocation.FIELD_DEFINITION,
        DirectiveLocation.OBJECT,
        DirectiveLocation.INTERFACE,
        DirectiveLocation.UNION,
        DirectiveLocation.ARGUMENT_DEFINITION,
        DirectiveLocation.SCALAR,
        DirectiveLocation.ENUM,
        DirectiveLocation.ENUM_VALUE,
        DirectiveLocation.INPUT_OBJECT,
        DirectiveLocation.INPUT_FIELD_DEFINITION,
    ],
    description="Excludes the annotated schema element from the public API",
)


# @tag(name: String!) repeatable on FIELD_DEFINITION | INTERFACE | OBJECT
#                     | UNION | ARGUMENT_DEFINITION | SCALAR | ENUM
#                     | ENUM_VALUE | INPUT_OBJECT | INPUT_FIELD_DEFINITION
tag = SchemaDirective(
    name="tag",
    locations=[
        DirectiveLocation.FIELD_DEFINITION,
        DirectiveLocation.INTERFACE,
        DirectiveLocation.OBJECT,
        DirectiveLocation.UNION,
        DirectiveLocation.ARGUMENT_DEFINITION,
        DirectiveLocation.SCALAR,
        DirectiveLocation.ENUM,
        DirectiveLocation.ENUM_VALUE,
        DirectiveLocation.INPUT_OBJECT,
        DirectiveLocation.INPUT_FIELD_DEFINITION,
    ],
    description="Used to label or tag schema elements (used in Federation).",
    args={
        "name": GraphQLArgument(
            GraphQLNonNull(GraphQLString), description="The tag name"
        )
    },
    is_repeatable=True,
)


# @override(from: String!) on FIELD_DEFINITION
override = SchemaDirective(
    name="override",
    locations=[DirectiveLocation.FIELD_DEFINITION],
    description="Indicates that this field overrides a field with the same name "
    "in another subgraph (used in Federation).",
    args={
        "from": GraphQLArgument(
            GraphQLNonNull(GraphQLString),
            description="The subgraph name from which the field is overridden",
        )
    },
)


# @composeDirective(name: String!) repeatable on SCHEMA
composeDirective = SchemaDirective(
    name="composeDirective",
    locations=[DirectiveLocation.SCHEMA],
    description="Used to signal that a directive should be composed across "
    "subgraphs (used in Federation).",
    args={
        "name": GraphQLArgument(
            GraphQLNonNull(GraphQLString),
            description="Name of the directive to compose",
        )
    },
    is_repeatable=True,
)


# @interfaceObject on OBJECT
interfaceObject = SchemaDirective(
    name="interfaceObject",
    locations=[DirectiveLocation.OBJECT],
    description="Marks an object type as an interface object (used in Federation).",
)


# @authenticated on FIELD_DEFINITION | OBJECT | INTERFACE | SCALAR | ENUM
authenticated = SchemaDirective(
    name="authenticated",
    locations=[
        DirectiveLocation.FIELD_DEFINITION,
        DirectiveLocation.OBJECT,
        DirectiveLocation.INTERFACE,
        DirectiveLocation.SCALAR,
        DirectiveLocation.ENUM,
    ],
    description="Marks that an authentication check is required (used in Federation).",
)


# @requiresScopes(scopes: [[federation__Scope!]!]!)
#     on FIELD_DEFINITION | OBJECT | INTERFACE | SCALAR | ENUM
requiresScopes = SchemaDirective(
    name="requiresScopes",
    locations=[
        DirectiveLocation.FIELD_DEFINITION,
        DirectiveLocation.OBJECT,
        DirectiveLocation.INTERFACE,
        DirectiveLocation.SCALAR,
        DirectiveLocation.ENUM,
    ],
    description="Indicates that certain OAuth scopes are required to access this"
    " schema element (used in Federation).",
    args={
        "scopes": GraphQLArgument(
            GraphQLNonNull(
                GraphQLList(
                    GraphQLNonNull(GraphQLList(GraphQLNonNull(FederationScope)))
                )
            ),
            description="List of lists of required scopes",
        )
    },
)


# @policy(policies: [[federation__Policy!]!]!)
#     on FIELD_DEFINITION | OBJECT | INTERFACE | SCALAR | ENUM
policy = SchemaDirective(
    name="policy",
    locations=[
        DirectiveLocation.FIELD_DEFINITION,
        DirectiveLocation.OBJECT,
        DirectiveLocation.INTERFACE,
        DirectiveLocation.SCALAR,
        DirectiveLocation.ENUM,
    ],
    description="Associates custom policy objects that apply to this schema "
    "element(used in Federation).",
    args={
        "policies": GraphQLArgument(
            # Similarly treat as nested lists or custom scalar if needed
            GraphQLNonNull(
                GraphQLList(
                    GraphQLNonNull(GraphQLList(GraphQLNonNull(FederationPolicy)))
                )
            ),
            description="List of lists of policies",
        )
    },
)


# @context(name: String!) repeatable on INTERFACE | OBJECT | UNION
context = SchemaDirective(
    name="context",
    locations=[
        DirectiveLocation.INTERFACE,
        DirectiveLocation.OBJECT,
        DirectiveLocation.UNION,
    ],
    description="Indicates that a particular context is applied to this type "
    "(used in Federation).",
    args={
        "name": GraphQLArgument(
            GraphQLNonNull(GraphQLString), description="The name of the context"
        )
    },
    is_repeatable=True,
)


# @fromContext(field: ContextFieldValue) on ARGUMENT_DEFINITION
#  or
# @fromContext(field: federation__ContextFieldValue) on ARGUMENT_DEFINITION
fromContext = SchemaDirective(
    name="fromContext",
    locations=[DirectiveLocation.ARGUMENT_DEFINITION],
    description="Specifies that an argument is sourced from a context field (used in "
    "Federation).",
    args={
        "field": GraphQLArgument(
            # Typically a custom scalar or input object
            FederationContextFieldValue,
            description="The path or name of the context field",
        )
    },
)


# @extends on OBJECT | INTERFACE
#    (Only needed if your library doesn't support the built-in `extend` keyword)
extends = SchemaDirective(
    name="extends",
    locations=[DirectiveLocation.OBJECT, DirectiveLocation.INTERFACE],
    description="Indicates that this type is an extension of a type defined elsewhere "
    "(used in Federation).",
)

federation_directives = [
    external,
    requires,
    provides,
    key,
    link,
    shareable,
    inaccessible,
    tag,
    override,
    composeDirective,
    interfaceObject,
    authenticated,
    requiresScopes,
    policy,
    context,
    fromContext,
    extends,
]


@type
class _Service:
    @field
    def sdl(self, context: GraphQLContext) -> str:
        def directive_filter(n):
            return not is_specified_directive(n) and n not in federation_directives

        def type_filter(n):
            return (
                is_defined_type(n)
                and n not in federation_types
                and not n.name == "_Service"
            )

        printed_directives = []

        schema = print_filtered_schema(
            context.schema, directive_filter, type_filter, printed_directives
        )

        schema = schema.replace(" _service: _Service!\n", "")
        imported_directives = str(
            ["@" + directive.directive.name for directive in printed_directives]
        ).replace("'", '"')

        extends_schema = (f'\n\nextend schema @link(url: '
                          f'"https://specs.apollo.dev/federation/v2.3", '
                          f'import: {imported_directives})')

        return schema + extends_schema


@field
def _service(self) -> _Service:
    return _Service()

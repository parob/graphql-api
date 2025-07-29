from graphql import (
    DirectiveLocation,
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLList,
    GraphQLNonNull,
    GraphQLString,
)

from graphql_api.directives import SchemaDirective
from graphql_api.federation.types import (
    FederationContextFieldValue,
    FederationPolicy,
    FederationScope,
    FieldSet,
    LinkImport,
    LinkPurposeEnum,
)

external = SchemaDirective(
    name="external",
    locations=[DirectiveLocation.FIELD_DEFINITION, DirectiveLocation.OBJECT],
    description="Marks a field or type as defined in another service",
)
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
shareable = SchemaDirective(
    name="shareable",
    locations=[DirectiveLocation.OBJECT, DirectiveLocation.FIELD_DEFINITION],
    description="Indicates the field or type can safely be resolved by multiple "
    "subgraphs (used in Federation).",
    is_repeatable=True,
)
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
interfaceObject = SchemaDirective(
    name="interfaceObject",
    locations=[DirectiveLocation.OBJECT],
    description="Marks an object type as an interface object (used in Federation).",
)
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

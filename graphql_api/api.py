from typing import Any, Dict, List, Optional, Tuple, Type, Union, Callable

# noinspection PyPackageRequirements
from graphql import (
    ExecutionResult,
    GraphQLDirective,
    GraphQLField,
    GraphQLNamedType,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
    is_named_type,
    specified_directives,
)

from graphql_api.error import GraphQLError
from graphql_api.directives import SchemaDirective
from graphql_api.executor import GraphQLBaseExecutor, GraphQLExecutor
from graphql_api.mapper import GraphQLTypeMapper
from graphql_api.reduce import GraphQLFilter, GraphQLSchemaReducer
from graphql_api.schema import add_applied_directives, get_applied_directives


class GraphQLFieldContext:
    def __init__(self, meta, query=None):
        self.meta = meta
        self.query = query

    def __str__(self):
        query_str = ""
        if self.query:
            query_str = f", query: {query_str}" if self.query else ""
        return f"<Node meta: {self.meta}{query_str}>"


class GraphQLRequestContext:
    def __init__(self, args, info):
        self.args = args
        self.info = info


# Workaround to allow GraphQLScalarType to be used in typehints in Python 3.10


def _disable_scalar_type_call(*args, **kwargs):
    """
    A no-op placeholder to allow calling GraphQLScalarType
    as if it were a function in Python 3.10+ type hints.
    """
    raise NotImplementedError("GraphQLScalarType cannot be called.")


# Attach the no-op to the GraphQLScalarType class
setattr(GraphQLScalarType, "__call__", _disable_scalar_type_call)


# noinspection PyShadowingBuiltins
def tag_value(
    value,
    graphql_type: str,
    schema: Optional["GraphQLAPI"] = None,
    meta: Optional[Dict] = None,
    directives: Optional[List] = None,
    is_root_type: bool = False,
):
    if not hasattr(value, "_graphql"):
        value._graphql = True

    if not hasattr(value, "_defined_on"):
        value._defined_on = value

    if not hasattr(value, "_schemas"):
        value._schemas = {}

    if hasattr(value, "_schemas"):
        # noinspection PyProtectedMember
        value._schemas[schema] = {
            "defined_on": value,
            "meta": meta or {},
            "graphql_type": graphql_type,
            "schema": schema,
        }

    from graphql_api.schema import add_applied_directives

    add_applied_directives(value, directives or [])

    if is_root_type:
        if graphql_type != "object":
            raise TypeError(f"Cannot set '{value}' of type '{graphql_type}' as a root.")

        if schema:
            schema.set_root_type(value)

    return value


def build_decorator(
    arg1: Any,
    arg2: Any,
    graphql_type: str,
    mutable: bool = False,
    interface: bool = False,
    abstract: bool = False,
    directives: Optional[List] = None,
    is_root_type: bool = False,
):
    """
    Creates a decorator that tags a function or class with GraphQL metadata.

    :param arg1: Possibly a function, a dict of metadata, or a `GraphQLAPI` instance.
    :param arg2: Possibly a function, a dict of metadata, or a `GraphQLAPI` instance.
    :param graphql_type: The type of the GraphQL element (e.g. "object", "field", etc.).
    :param mutable: Whether this field should be considered "mutable_field".
    :param interface: If True, treat as a GraphQL interface.
    :param abstract: If True, treat as an abstract type.
    :param directives: Any directives to be added.
    :param is_root_type: Whether this should be the root (query) type in the schema.
    """
    # Adjust the graphql_type for interface or abstract usage
    if graphql_type == "object":
        if interface:
            graphql_type = "interface"
        elif abstract:
            graphql_type = "abstract"

    # Adjust the graphql_type if 'mutable' is requested
    if graphql_type == "field" and mutable:
        graphql_type = "mutable_field"

    # Figure out which args are which
    func = arg1 if callable(arg1) else (arg2 if callable(arg2) else None)
    meta_dict = (
        arg1 if isinstance(arg1, dict) else (arg2 if isinstance(arg2, dict) else None)
    )
    schema_obj = (
        arg1
        if isinstance(arg1, GraphQLAPI)
        else (arg2 if isinstance(arg2, GraphQLAPI) else None)
    )

    # If a function is directly provided
    if func:
        return tag_value(
            value=func,
            graphql_type=graphql_type,
            schema=schema_obj,
            meta=meta_dict,
            directives=directives,
            is_root_type=is_root_type,
        )

    # Otherwise, return a decorator
    def _decorator(f):
        return tag_value(
            value=f,
            graphql_type=graphql_type,
            schema=schema_obj,
            meta=meta_dict,
            directives=directives,
            is_root_type=is_root_type,
        )

    return _decorator


class GraphQLRootTypeDelegate:
    infer_subclass_fields = True

    @classmethod
    def validate_graphql_schema(cls, schema: GraphQLSchema) -> GraphQLSchema:
        """
        This method is called whenever a schema is created with this
        class as the root type.
        :param schema: The GraphQL schema that is generated by
        :return:schema: The validated and updated GraphQL schema.
        """
        return schema


class GraphQLAPI(GraphQLBaseExecutor):
    """
    Main GraphQL API class. Creates a schema from root types, decorators, etc.,
    and provides an interface for query execution.
    """

    def __init__(
        self,
        root_type=None,
        middleware: Optional[List[Callable]] = None,
        directives: Optional[List[GraphQLDirective]] = None,
        types: Optional[List[Union[GraphQLNamedType, Type]]] = None,
        filters: Optional[List[GraphQLFilter]] = None,
        error_protection: bool = True,
        federation: bool = False,
        max_docstring_length: Optional[int] = 500,
        subscription_type: Optional[Type] = None,
    ):
        """
        Initialize a new GraphQL API instance.

        Args:
            root_type: The root query type class to use for the schema
            middleware: List of middleware functions to apply to queries
            directives: List of custom GraphQL directives to include in the schema
            types: List of additional types to explicitly include in the schema
            filters: List of filters to apply when building the schema (removes matching fields).
                Each filter can specify cleanup_types=False to prevent automatic removal of
                unreferenced types after filtering.
            error_protection: Whether to enable error protection during execution
            federation: Whether to enable GraphQL federation support
            max_docstring_length: Maximum length for docstrings before truncation (None for no limit)
        """
        super().__init__()
        self.root_type = root_type
        self.subscription_type = subscription_type
        self.middleware = middleware or []
        self.directives = [*specified_directives] + (directives or [])
        self.types = set(types or [])
        self.filters = filters
        self.query_mapper: Optional[GraphQLTypeMapper] = None
        self.mutation_mapper: Optional[GraphQLTypeMapper] = None
        self.subscription_mapper: Optional[GraphQLTypeMapper] = None
        self.error_protection = error_protection
        self.federation = federation
        self._cached_schema: Optional[Tuple[GraphQLSchema, Dict]] = None
        self.max_docstring_length = max_docstring_length

    # --------------------------------------------------------------------------
    # DECORATORS
    # --------------------------------------------------------------------------
    def field(
        self=None,
        meta=None,
        mutable: bool = False,
        directives: Optional[List] = None,
    ):
        """
        Marks a function or method as a GraphQL field.
        Example usage:
            @api.field(mutable=True)
            def update_something(...):
                ...
        """
        return build_decorator(
            arg1=self,
            arg2=meta,
            graphql_type="field",
            mutable=mutable,
            directives=directives,
        )

    def type(
        self=None,
        meta=None,
        abstract: bool = False,
        interface: bool = False,
        is_root_type: bool = False,
        directives: Optional[List] = None,
    ):
        """
        Marks a class or function as a GraphQL type (object, interface, or abstract).
        Example usage:
            @api.type(abstract=True)
            class MyBase:
                ...
        """
        return build_decorator(
            arg1=self,
            arg2=meta,
            graphql_type="object",
            abstract=abstract,
            interface=interface,
            directives=directives,
            is_root_type=is_root_type,
        )

    def set_root_type(self, root_type):
        """
        Explicitly sets the root query type for this API instance.
        """
        self.root_type = root_type
        return root_type

    # --------------------------------------------------------------------------
    # SCHEMA BUILDING & EXECUTION
    # --------------------------------------------------------------------------
    def build_schema(self, ignore_cache: bool = False) -> Tuple[GraphQLSchema, Dict]:
        """
        Builds the GraphQL schema using decorators, directives, filters, etc.
        :param ignore_cache: If True, force rebuild the schema even if cached.
        :return: (GraphQLSchema, metadata_dict)
        """
        if not ignore_cache and self._cached_schema:
            return self._cached_schema

        # Federation support
        if self.federation:
            from graphql_api.federation.federation import add_federation_types

            add_federation_types(self)

        meta: Dict = {}
        query: Optional[GraphQLObjectType] = None
        mutation: Optional[GraphQLObjectType] = None
        subscription: Optional[GraphQLObjectType] = None
        collected_types: Optional[List[GraphQLNamedType]] = None

        if self.root_type:
            # Build root Query
            query_mapper = GraphQLTypeMapper(schema=self, max_docstring_length=self.max_docstring_length)
            _query = query_mapper.map(self.root_type)

            # Map additional types that aren't native GraphQLNamedType
            for typ in list(self.types):
                if not is_named_type(typ):
                    query_mapper.map(typ)

            if not isinstance(_query, GraphQLObjectType):
                raise GraphQLError(f"Query {_query} was not a valid GraphQLObjectType.")

            # Filter the Query
            filtered_query = GraphQLSchemaReducer.reduce_query(
                query_mapper, _query, filters=self.filters
            )

            # Check if filtering removed all fields from the root query type
            query_has_fields = False
            try:
                query_has_fields = len(filtered_query.fields) > 0
            except (AssertionError, AttributeError):
                query_has_fields = False

            # For filtered schemas, we need to handle empty query types gracefully
            if self.filters and not query_has_fields:
                # All query fields were filtered out - create a minimal query type
                # that preserves the original name and indicates the filtered state
                query = GraphQLObjectType(
                    name=filtered_query.name,
                    fields={
                        "_schema": GraphQLField(
                            type_=GraphQLString,
                            resolve=lambda *_: f"Schema '{filtered_query.name}' has all fields filtered",
                            description="Indicates that all fields in this schema have been filtered out",
                        )
                    },
                    description=f"Filtered version of {filtered_query.name} with no accessible fields",
                )
                query_types = query_mapper.types()
                registry = query_mapper.registry
            elif query_mapper.validate(filtered_query, evaluate=True):
                query = filtered_query
                query_types = query_mapper.types()
                registry = query_mapper.registry
            else:
                # Query failed validation for reasons other than filtering
                query_types = set()
                registry = None

            # Build root Mutation - use a copy of the registry to avoid polluting the shared registry
            mutation_registry = registry.copy() if registry else {}
            mutation_mapper = GraphQLTypeMapper(
                as_mutable=True, suffix="Mutable", registry=mutation_registry, schema=self, max_docstring_length=self.max_docstring_length
            )
            _mutation = mutation_mapper.map(self.root_type)

            if not isinstance(_mutation, GraphQLObjectType):
                raise GraphQLError(
                    f"Mutation {_mutation} was not a valid GraphQLObjectType."
                )

            # Filter the Mutation
            filtered_mutation = GraphQLSchemaReducer.reduce_mutation(
                mutation_mapper, _mutation, filters=self.filters
            )

            if mutation_mapper.validate(filtered_mutation, evaluate=True):
                mutation = filtered_mutation
                mutation_types = mutation_mapper.types()
            else:
                mutation = None
                mutation_types = set()  # Don't include any mutation types when validation fails

            # Clean up unreferenced types after filtering (only when filters are applied and any filter has cleanup enabled)
            should_cleanup_types = False
            if self.filters:
                should_cleanup_types = any(getattr(f, 'cleanup_types', True) for f in self.filters)
            if self.filters and should_cleanup_types and (query_mapper or mutation_mapper):
                if query_mapper and query:
                    GraphQLSchemaReducer._remove_unreferenced_types(query_mapper, query)
                if mutation_mapper and mutation:
                    GraphQLSchemaReducer._remove_unreferenced_types(mutation_mapper, mutation)

                # Recalculate types after cleanup
                if query_mapper:
                    query_types = query_mapper.types()
                if mutation_mapper:
                    mutation_types = mutation_mapper.types()

            # Build root Subscription (optional)
            subscription_types = set()
            if self.subscription_type:
                subscription_mapper = GraphQLTypeMapper(
                    as_mutable=False,
                    suffix="Subscription",
                    registry=registry,
                    schema=self,
                    max_docstring_length=self.max_docstring_length,
                    as_subscription=True,
                )
                _subscription = subscription_mapper.map(self.subscription_type)
                if not isinstance(_subscription, GraphQLObjectType):
                    raise GraphQLError(
                        f"Subscription {_subscription} was not a valid GraphQLObjectType."
                    )
                subscription = _subscription
                subscription_types = subscription_mapper.types()
                self.subscription_mapper = subscription_mapper

            # Collect all types
            all_types = query_types | subscription_types | self.types
            if mutation:  # Only include mutation types if mutation is valid
                all_types = all_types | mutation_types

            collected_types = [  # type: ignore[assignment]
                t
                for t in list(all_types)
                if is_named_type(t)
            ]

            # Gather meta info from all mappers
            meta = {**query_mapper.meta}
            if mutation_mapper and mutation:  # Only include mutation meta if mutation is valid
                meta.update(mutation_mapper.meta)
            if self.subscription_mapper:
                meta.update(self.subscription_mapper.meta)
            self.query_mapper = query_mapper
            self.mutation_mapper = mutation_mapper

        # If there's no query, create a placeholder (this should now only happen for non-filtered cases)
        if not query:
            query = GraphQLObjectType(
                name="PlaceholderQuery",
                fields={
                    "placeholder": GraphQLField(
                        type_=GraphQLString, resolve=lambda *_: ""
                    )
                },
            )

        # Include directives that may have been attached through the mappers
        if self.query_mapper:
            applied_directives_list = [self.query_mapper.applied_schema_directives]
            if self.mutation_mapper and mutation:  # Only include mutation directives if mutation is valid
                applied_directives_list.append(self.mutation_mapper.applied_schema_directives)
            if self.subscription_mapper:
                applied_directives_list.append(self.subscription_mapper.applied_schema_directives)

            for applied_directives in applied_directives_list:
                for _, _, directives in applied_directives:
                    for d in directives:
                        if d.directive not in self.directives:
                            self.directives.append(d.directive)

        # Create the schema
        schema = GraphQLSchema(
            query=query,
            mutation=mutation,
            subscription=subscription,
            types=collected_types,
            directives=[
                d.directive if isinstance(d, SchemaDirective) else d
                for d in self.directives
            ],
        )

        api_directives = get_applied_directives(self)
        if api_directives:
            add_applied_directives(schema, api_directives)

        # Post-federation modifications
        if self.federation:
            from graphql_api.federation.federation import (
                add_entity_type,
                link_directives,
            )

            add_entity_type(self, schema)
            link_directives(schema)

        # If root type implements GraphQLRootTypeDelegate, allow a final check
        if self.root_type and issubclass(self.root_type, GraphQLRootTypeDelegate):
            schema = self.root_type.validate_graphql_schema(schema)

        self._cached_schema = (schema, meta)

        return schema, meta

    def execute(
        self,
        query,
        variables=None,
        operation_name=None,
        root_value: Any = None,
    ) -> ExecutionResult:
        return self.executor(root_value=root_value).execute(
            query=query,
            variables=variables,
            operation_name=operation_name,
        )

    def executor(
        self,
        root_value: Any = None,
    ) -> GraphQLExecutor:
        schema, meta = self.build_schema()

        if callable(self.root_type) and root_value is None:
            root_value = self.root_type()

        return GraphQLExecutor(
            schema=schema,
            meta=meta,
            root_value=root_value,
            middleware=self.middleware,
            error_protection=self.error_protection,
        )

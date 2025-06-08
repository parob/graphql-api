from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union, cast

# noinspection PyPackageRequirements
from graphql import (ExecutionResult, GraphQLDirective, GraphQLField,
                     GraphQLNamedType, GraphQLObjectType, GraphQLScalarType,
                     GraphQLSchema, GraphQLString, Middleware, is_named_type,
                     specified_directives)

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


T = TypeVar('T')

# noinspection PyShadowingBuiltins
def tag_value(
    value: T,
    graphql_type: str,
    schema: Optional["GraphQLAPI"] = None,
    meta: Optional[Dict] = None,
    directives: Optional[List] = None,
    is_root_type: bool = False,
) -> T:
    # Ensure attributes exist before assignment, then use setattr
    if not hasattr(value, "_graphql"):
        setattr(value, "_graphql", False) # Default initialization
    setattr(value, "_graphql", True)

    if not hasattr(value, "_defined_on"):
        setattr(value, "_defined_on", None) # Default initialization
    setattr(value, "_defined_on", value)

    if not hasattr(value, "_schemas"):
        setattr(value, "_schemas", {}) # Default initialization

    # For nested assignment, getattr -> modify -> setattr might be needed if type checker complains
    current_schemas = getattr(value, "_schemas", {})
    current_schemas[schema] = {
        "defined_on": value,
        "meta": meta or {},
        "graphql_type": graphql_type,
        "schema": schema,
    }
    setattr(value, "_schemas", current_schemas)

    from graphql_api.schema import add_applied_directives

    add_applied_directives(value, directives or [])

    if is_root_type:
        if graphql_type != "object":
            raise TypeError(f"Cannot set '{value}' of type '{graphql_type}' as a root.")

        if schema:
            schema.set_root_type(value)

    return value


WrapperCallable = Callable[[T], T]
DecoratorResult = Union[T, WrapperCallable[T]]

def build_decorator(
    arg1: Any,
    arg2: Any,
    graphql_type: str,
    mutable: bool = False,
    interface: bool = False,
    abstract: bool = False,
    directives: Optional[List] = None,
    is_root_type: bool = False,
) -> DecoratorResult: # More precise would need ParamSpec & more TypeVars
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
        middleware: Optional[Middleware] = None,
        directives: Optional[List[GraphQLDirective]] = None,
        types: Optional[List[Union[GraphQLNamedType, Type]]] = None,
        filters: Optional[List[GraphQLFilter]] = None,
        error_protection: bool = True,
        federation: bool = False,
    ):
        super().__init__()
        self.root_type = root_type
        self.middleware = middleware or []
        self.directives = [*specified_directives] + (directives or [])
        self.types = set(types or [])
        self.filters = filters
        self.query_mapper: Optional[GraphQLTypeMapper] = None
        self.mutation_mapper: Optional[GraphQLTypeMapper] = None
        self.error_protection = error_protection
        self.federation = federation
        self._cached_schema: Optional[Tuple[GraphQLSchema, Dict]] = None

    # --------------------------------------------------------------------------
    # DECORATORS
    # --------------------------------------------------------------------------
    def field(
        self=None, # Actually 'fn_or_self' due to decorator pattern
        meta=None, # Actually 'api_or_meta'
        mutable: bool = False,
        directives: Optional[List] = None,
    ) -> DecoratorResult:
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
        self=None, # Actually 'fn_or_self'
        meta=None, # Actually 'api_or_meta'
        abstract: bool = False,
        interface: bool = False,
        is_root_type: bool = False,
        directives: Optional[List] = None,
    ) -> DecoratorResult:
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
        collected_types: Optional[List[GraphQLNamedType]] = None

        if self.root_type:
            # Build root Query
            query_mapper = GraphQLTypeMapper(schema=self)
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

            if query_mapper.validate(filtered_query, evaluate=True):
                query = filtered_query
                query_types = query_mapper.types()
                registry = query_mapper.registry
            else:
                query_types = set()
                registry = None

            # Build root Mutation
            mutation_mapper = GraphQLTypeMapper(
                as_mutable=True, suffix="Mutable", registry=registry, schema=self
            )
            _mutation = mutation_mapper.map(self.root_type)

            if not isinstance(_mutation, GraphQLObjectType):
                raise GraphQLError(
                    f"Mutation {_mutation} was not a valid GraphQLObjectType."
                )

            # Filter the Mutation
            filtered_mutation = GraphQLSchemaReducer.reduce_mutation(
                mutation_mapper, _mutation
            )

            if mutation_mapper.validate(filtered_mutation, evaluate=True):
                mutation = filtered_mutation
                mutation_types = mutation_mapper.types()
            else:
                mutation = None
                mutation_types = set()

            # Collect all types
            # Ensure query_types and mutation_types are sets of GraphQLNamedType
            # Ensure self.types is set[Union[GraphQLNamedType, Type]]

            # --- START DEBUG LOGGING ---
            print(f"\n[BuildSchema] --- Query Mapper Types ({len(query_types)}) ---")
            for qt in sorted(list(query_types), key=lambda x: x.name if hasattr(x, 'name') and x.name else ''):
                if hasattr(qt, 'name') and qt.name:
                    print(f"[BuildSchema] QueryType: {qt.name} - {repr(qt)}")
                    if qt.name in ["Person", "PersonMutable"] and hasattr(qt, 'fields'):
                        try: print(f"[BuildSchema] QueryType fields for {qt.name}: {list(qt.fields.keys())}")
                        except Exception as e: print(f"[BuildSchema] QueryType fields for {qt.name} - Error accessing fields: {e}")


            print(f"\n[BuildSchema] --- Mutation Mapper Types ({len(mutation_types)}) ---")
            for mt in sorted(list(mutation_types), key=lambda x: x.name if hasattr(x, 'name') and x.name else ''):
                if hasattr(mt, 'name') and mt.name:
                    print(f"[BuildSchema] MutationType: {mt.name} - {repr(mt)}")
                    if mt.name in ["Person", "PersonMutable"] and hasattr(mt, 'fields'):
                        try: print(f"[BuildSchema] MutationType fields for {mt.name}: {list(mt.fields.keys())}")
                        except Exception as e: print(f"[BuildSchema] MutationType fields for {mt.name} - Error accessing fields: {e}")


            print(f"\n[BuildSchema] --- Explicit API Types (self.types) ({len(self.types)}) ---")
            # self.types are Python classes, need mapping if not already in query/mutation mappers
            # These are already incorporated into query_mapper.types() if they were mapped.
            # For logging, let's see what GraphQL types they correspond to using query_mapper.
            for t_class_api in self.types:
                if not is_named_type(t_class_api): # if it's a Python class
                    mapped_t_api = query_mapper.map(t_class_api)
                    if mapped_t_api and hasattr(mapped_t_api, 'name'):
                        print(f"[BuildSchema] ExplicitAPIType (Python class {t_class_api.__name__} mapped to): {mapped_t_api.name} - {repr(mapped_t_api)}")
                elif hasattr(t_class_api, 'name'): # if it's already a GraphQLNamedType
                     print(f"[BuildSchema] ExplicitAPIType (GraphQL type): {t_class_api.name} - {repr(t_class_api)}")


            # Original collection logic
            # query_types and mutation_types are already sets of GraphQLNamedType objects (or None)
            # self.types might contain Python classes, which map() handles and query_mapper.types() would then include.
            # The key is that query_mapper.types() and mutation_mapper.types() should reflect all mapped types.

            # Let's reconstruct collected_types carefully for logging, similar to original logic
            # The original temp_list combined sets, which de-duplicates by object identity.
            # Then it filters for is_named_type.

            # Log contents of query_mapper.registry and mutation_mapper.registry for Person/PersonMutable
            if query_mapper:
                for py_type, gql_type in query_mapper.registry.items(): # registry is str_key -> gql_type in current mapper
                    if gql_type and hasattr(gql_type, 'name') and gql_type.name in ["Person", "PersonMutable"]:
                        print(f"[BuildSchema] query_mapper.registry has {gql_type.name} ({repr(gql_type)}) from key {py_type}")
            if mutation_mapper:
                 for py_type, gql_type in mutation_mapper.registry.items():
                    if gql_type and hasattr(gql_type, 'name') and gql_type.name in ["Person", "PersonMutable"]:
                        print(f"[BuildSchema] mutation_mapper.registry has {gql_type.name} ({repr(gql_type)}) from key {py_type}")

            # The actual types passed to GraphQLSchema constructor comes from this logic:
            temp_list_for_schema: list[Any] = list(query_types | mutation_types | self.types)
            collected_types_for_schema: list[GraphQLNamedType] = []

            # De-duplication by name for the final list to GraphQLSchema
            # This is the critical step matching the subtask prompt's suggestion
            unique_types_by_name: Dict[str, GraphQLNamedType] = {}
            print(f"\n[BuildSchema] --- Building unique_types_by_name from query_types, mutation_types, self.types ---")

            # Process query_mapper types
            for t in query_types:
                if t and hasattr(t, 'name') and t.name:
                    if t.name not in unique_types_by_name:
                        unique_types_by_name[t.name] = t
                        print(f"[BuildSchema] From query_mapper: ADDING {t.name} ({repr(t)}) to unique_types_by_name")
                    elif unique_types_by_name[t.name] is not t:
                        print(f"[BuildSchema] From query_mapper: DUPLICATE NAME {t.name} ({repr(t)}). Kept existing: {repr(unique_types_by_name[t.name])}")

            # Process mutation_mapper types
            if mutation_types: # mutation_types can be None if no root_type
                for t in mutation_types:
                    if t and hasattr(t, 'name') and t.name:
                        if t.name not in unique_types_by_name:
                            unique_types_by_name[t.name] = t
                            print(f"[BuildSchema] From mutation_mapper: ADDING {t.name} ({repr(t)}) to unique_types_by_name")
                        elif unique_types_by_name[t.name] is not t:
                            print(f"[BuildSchema] From mutation_mapper: DUPLICATE NAME {t.name} ({repr(t)}). Kept existing: {repr(unique_types_by_name[t.name])}")
                            if t.name == "PersonMutable": # If we are about to skip the mutable_mapper's version
                                print(f"[BuildSchema] Discarded PersonMutable ({repr(t)}) fields: {list(t.fields.keys()) if hasattr(t,'fields') else 'N/A'}")
                                kept_pm = unique_types_by_name[t.name]
                                print(f"[BuildSchema] Kept PersonMutable ({repr(kept_pm)}) fields: {list(kept_pm.fields.keys()) if hasattr(kept_pm,'fields') else 'N/A'}")


            # Process self.types (these are Python classes, need mapping)
            # These should ideally already be in unique_types_by_name if they were reachable from root_type
            # or explicitly mapped by query_mapper.map(typ) earlier.
            # This loop is more for types that might not have been hit by query_mapper/mutation_mapper yet.
            for t_class_api in self.types:
                # Map it, preferably with query_mapper as a default context
                # The caching in the mapper should return existing instances if already mapped
                mapped_t_api = query_mapper.map(t_class_api) if query_mapper else None
                if mapped_t_api and hasattr(mapped_t_api, 'name') and mapped_t_api.name:
                    if mapped_t_api.name not in unique_types_by_name:
                        unique_types_by_name[mapped_t_api.name] = mapped_t_api
                        print(f"[BuildSchema] From self.types (mapped): ADDING {mapped_t_api.name} ({repr(mapped_t_api)}) to unique_types_by_name")
                    elif unique_types_by_name[mapped_t_api.name] is not mapped_t_api:
                         print(f"[BuildSchema] From self.types (mapped): DUPLICATE NAME {mapped_t_api.name} ({repr(mapped_t_api)}). Kept existing: {repr(unique_types_by_name[mapped_t_api.name])}")


            collected_types = list(unique_types_by_name.values())

            print(f"\n[BuildSchema] --- Final list of types for GraphQLSchema constructor ({len(collected_types)}) ---")
            for t in sorted(collected_types, key=lambda x: x.name if hasattr(x, 'name') and x.name else ''):
                 if hasattr(t, 'name') and t.name in ["Person", "PersonMutable"]:
                    print(f"[BuildSchema] Final type: {t.name} - {repr(t)} - Fields: {list(t.fields.keys()) if hasattr(t,'fields') else 'N/A'}")
            # --- END DEBUG LOGGING ---

            # Gather meta info from both mappers
            meta = {**query_mapper.meta, **mutation_mapper.meta} # query_mapper can be None
            self.query_mapper = query_mapper
            self.mutation_mapper = mutation_mapper

        # If there's no query, create a placeholder
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
        if self.query_mapper and self.mutation_mapper:
            for _, _, applied_directives_list in (
                self.query_mapper.applied_schema_directives
                + self.mutation_mapper.applied_schema_directives
            ):
                for d_item in applied_directives_list: # Iterate over the list of AppliedDirective objects
                    if d_item.directive not in self.directives: # Access 'directive' attribute
                        directive_to_add = d_item.directive
                        # assert isinstance(directive_to_add, GraphQLDirective) # Optional: for runtime check
                        self.directives.append(cast(GraphQLDirective, directive_to_add))


        schema = GraphQLSchema(
            query=query,
            mutation=mutation,
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
            from graphql_api.federation.federation import (add_entity_type,
                                                           link_directives)

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

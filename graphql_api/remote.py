import asyncio
import enum
import inspect
import json
import sys
import uuid
from dataclasses import fields as dataclasses_fields
from dataclasses import is_dataclass
from typing import Dict, List, Optional, Tuple, Type

from graphql import (
    GraphQLBoolean,
    GraphQLEnumType,
    GraphQLFloat,
    GraphQLID,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLString,
    GraphQLUnionType,
    GraphQLNamedType,
)
from graphql.execution import ExecutionResult
from graphql.language import ast
from graphql.type.definition import (
    GraphQLField,
    GraphQLList,
    GraphQLNonNull,
    GraphQLScalarType,
    GraphQLType,
    get_named_type,
    is_wrapping_type,
)
from requests.exceptions import RequestException

from graphql_api.api import GraphQLAPI
from graphql_api.error import GraphQLError
from graphql_api.executor import GraphQLBaseExecutor
from graphql_api.mapper import GraphQLMetaKey, GraphQLTypeMapper
from graphql_api.types import serialize_bytes
from graphql_api.utils import http_query, to_camel_case, to_snake_case, url_to_ast


class NullResponse(Exception):
    """
    Raised when a remote response is null or empty in an unexpected context.
    """

    pass


class GraphQLRemoteError(GraphQLError):
    """
    Represents an error originating from a remote GraphQL service.
    """

    def __init__(self, query=None, result=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        self.result = result


class GraphQLAsyncStub:
    """
    Placeholder/Stub for an asynchronous GraphQL functionality.
    Currently not used, but retained as requested.
    """

    async def call_async(self, name, *args, **kwargs):
        pass


def remote_execute(executor: GraphQLBaseExecutor, context):
    """
    Placeholder function for remote execution. Currently not used,
    but retained as requested.
    """
    assert context.request is not None, "GraphQLContext.request cannot be None"
    assert context.field is not None, "GraphQLContext.field cannot be None"
    operation = context.request.info.operation.operation
    query = context.field.query
    redirected_query = operation.value + " " + query

    result = executor.execute(query=redirected_query)

    if result.errors:
        raise GraphQLError(str(result.errors))

    return result.data


def is_list(graphql_type: GraphQLType) -> bool:
    """Return True if the GraphQLType is a list (potentially nested)."""
    current_type: GraphQLType = graphql_type
    while is_wrapping_type(current_type):
        if isinstance(current_type, GraphQLList):
            return True
        current_type = current_type.of_type  # type: ignore
    return isinstance(current_type, GraphQLList)


def is_scalar(graphql_type: GraphQLType) -> bool:
    """
    Return True if the final unwrapped GraphQLType is a scalar or an enum.
    (ID, String, Float, Boolean, Int, or Enum).
    """
    named_type = get_named_type(graphql_type)
    return isinstance(named_type, (GraphQLScalarType, GraphQLEnumType))


def is_nullable(graphql_type: GraphQLType) -> bool:
    """Return False if the type is NonNull at any level, otherwise True."""
    current_type: GraphQLType = graphql_type
    while is_wrapping_type(current_type):
        if isinstance(current_type, GraphQLNonNull):
            return False
        current_type = current_type.of_type  # type: ignore
    return True


def is_static_method(klass, attr, value=None) -> bool:
    """Check if a given attribute of a class is a staticmethod."""
    if value is None:
        value = getattr(klass, attr)
    for cls in inspect.getmro(klass):
        if inspect.isroutine(value) and attr in cls.__dict__:
            bound_value = cls.__dict__[attr]
            if isinstance(bound_value, staticmethod):
                return True
    return False


def to_ast_value(value, graphql_type: GraphQLType):
    """Convert a Python scalar to the corresponding GraphQL AST node."""
    if value is None:
        return None

    if isinstance(value, bool):
        return ast.BooleanValueNode(value=value)
    if isinstance(value, int):
        return ast.IntValueNode(value=str(value))
    if isinstance(value, float):
        return ast.FloatValueNode(value=str(value))
    if isinstance(value, str):
        if isinstance(graphql_type, GraphQLEnumType):
            return ast.EnumValueNode(value=value)
        return ast.StringValueNode(value=value)

    raise TypeError(
        f"Unable to map Python scalar type {type(value)} to a valid GraphQL AST type."
    )


class GraphQLRemoteExecutor(GraphQLBaseExecutor, GraphQLObjectType):
    """
    A GraphQL executor that forwards all operations to a remote GraphQL service.
    """

    def __init__(
        self,
        url,
        name="Remote",
        description=None,
        http_method="GET",
        http_headers=None,
        http_timeout=None,
        verify=True,
        ignore_unsupported=True,
    ):
        if not description:
            description = (
                f"The `{name}` object type forwards all "
                f"requests to the GraphQL executor at {url}."
            )

        if http_headers is None:
            http_headers = {}

        self.url = url
        self.http_method = http_method
        self.http_headers = http_headers
        self.http_timeout = http_timeout
        self.verify = verify
        self.ignore_unsupported = ignore_unsupported

        super().__init__(name=name, fields=self.build_fields, description=description)

    def build_fields(self):
        """Dynamically builds fields by introspecting the remote schema."""
        ast_schema = url_to_ast(
            self.url, http_method=self.http_method, http_headers=self.http_headers
        )

        def resolver(root, info, *args, **kwargs):
            key_ = (
                info.field_nodes[0].alias.value
                if info.field_nodes[0].alias
                else info.field_nodes[0].name.value
            )
            return root[key_]

        if not ast_schema.query_type:
            return {}

        for name, graphql_type in ast_schema.type_map.items():
            if isinstance(
                graphql_type, (GraphQLObjectType, GraphQLInputObjectType)
            ) and not graphql_type.name.startswith("__"):
                for _, field in graphql_type.fields.items():
                    field.resolver = resolver
            elif isinstance(graphql_type, GraphQLEnumType):
                if not self.ignore_unsupported:
                    raise GraphQLError(
                        f"GraphQLScalarType '{graphql_type}' is not supported "
                        f"in a remote executor '{self.url}'."
                    )
            elif isinstance(graphql_type, (GraphQLInterfaceType, GraphQLUnionType)):
                super_type = (
                    "GraphQLInterface"
                    if isinstance(graphql_type, GraphQLInterfaceType)
                    else "GraphQLUnionType"
                )
                if not self.ignore_unsupported:
                    raise GraphQLError(
                        f"{super_type} '{graphql_type}' is not supported "
                        f"from remote executor '{self.url}'."
                    )
            elif isinstance(graphql_type, GraphQLScalarType):
                # Allow basic scalars only
                if graphql_type not in [
                    GraphQLID,
                    GraphQLString,
                    GraphQLFloat,
                    GraphQLBoolean,
                    GraphQLInt,
                ]:
                    if not self.ignore_unsupported:
                        raise GraphQLError(
                            f"GraphQLScalarType '{graphql_type}' is not supported "
                            f"in a remote executor '{self.url}'."
                        )
            elif str(graphql_type).startswith("__"):
                continue
            else:
                raise GraphQLError(
                    f"Unknown GraphQLType '{graphql_type}' is not supported "
                    f"in a remote executor '{self.url}'."
                )

        return ast_schema.query_type.fields

    async def execute_async(
        self,
        query,
        variable_values=None,
        operation_name=None,
        http_headers=None,
    ) -> ExecutionResult:
        """Execute the query asynchronously against the remote GraphQL endpoint."""
        if http_headers is None:
            http_headers = self.http_headers
        else:
            http_headers = {**self.http_headers, **http_headers}

        try:
            json_ = await http_query(
                url=self.url,
                query=query,
                variable_values=variable_values,
                operation_name=operation_name,
                http_method=self.http_method,
                http_headers=http_headers,
                http_timeout=(
                    int(self.http_timeout) if self.http_timeout is not None else 0
                ),
                verify=self.verify,
            )
        except RequestException as e:
            err_msg = f"{e}, remote service '{self.name}' is unavailable."
            raise type(e)(err_msg).with_traceback(sys.exc_info()[2])

        except ValueError as e:
            raise ValueError(f"{e}, from remote service '{self.name}'.")

        return ExecutionResult(data=json_.get("data"), errors=json_.get("errors"))

    def execute(
        self,
        query,
        variable_values=None,
        operation_name=None,
        http_headers=None,
    ) -> ExecutionResult:
        """Execute the query synchronously against the remote GraphQL endpoint."""
        if http_headers is None:
            http_headers = self.http_headers
        else:
            http_headers = {**self.http_headers, **http_headers}

        try:
            json_ = asyncio.run(
                http_query(
                    url=self.url,
                    query=query,
                    variable_values=variable_values,
                    operation_name=operation_name,
                    http_method=self.http_method,
                    http_headers=http_headers,
                    http_timeout=(
                        int(self.http_timeout) if self.http_timeout is not None else 0
                    ),
                    verify=self.verify,
                )
            )
        except RequestException as e:
            err_msg = f"{e}, remote service '{self.name}' is unavailable '{self.url}'."
            raise type(e)(err_msg).with_traceback(sys.exc_info()[2])

        except ValueError as e:
            raise ValueError(f"{e}, from remote service '{self.name}' at '{self.url}'.")

        return ExecutionResult(data=json_.get("data"), errors=json_.get("errors"))


class GraphQLMappers:
    """
    Holds two GraphQLTypeMappers, one for queries and one for mutations.
    """

    def __init__(
        self,
        query_mapper: GraphQLTypeMapper,
        mutable_mapper: GraphQLTypeMapper,
    ):
        self.query_mapper = query_mapper
        self.mutable_mapper = mutable_mapper

    def map(self, type_, reverse=False):
        """
        Map the given Python type <-> GraphQL type using the stored mappers.
        If reverse=True, the direction is GraphQL -> Python.
        Otherwise, Python -> GraphQL returns (query_type, mutation_type).
        """
        if reverse:
            query_type = self.query_mapper.rmap(type_)
            mutable_type = self.mutable_mapper.rmap(type_)
            return query_type or mutable_type

        query_type = self.query_mapper.map(type_)
        mutable_type = self.mutable_mapper.map(type_)
        return query_type, mutable_type


class GraphQLRemoteObject:
    """
    Represents a Python-side proxy object that fetches or mutates data
    on a remote GraphQL service.
    """

    @classmethod
    def from_url(
        cls,
        url: str,
        api: GraphQLAPI,
        http_method: str = "GET",
    ) -> "GraphQLRemoteObject":
        """
        Convenience constructor that creates a GraphQLRemoteExecutor
        and returns a GraphQLRemoteObject bound to it.
        """
        executor = GraphQLRemoteExecutor(url=url, http_method=http_method)
        return GraphQLRemoteObject(executor=executor, api=api)

    def __init__(
        self,
        executor: GraphQLBaseExecutor,
        api: Optional[GraphQLAPI] = None,
        mappers: Optional[GraphQLMappers] = None,
        python_type: Optional[Type] = None,
        call_history: Optional[List[Tuple["GraphQLRemoteField", Dict]]] = None,
        delay_mapping: bool = True,
    ):
        if not call_history:
            call_history = []

        if not api and python_type:
            api = GraphQLAPI(root_type=python_type)
        elif not python_type and api:
            python_type = api.root_type
        elif not python_type and not api:
            raise ValueError("Either `api` or `python_type` must be provided.")

        self.executor = executor
        self.api: Optional[GraphQLAPI] = api
        self.mappers: Optional[GraphQLMappers] = mappers
        self.call_history = call_history
        self.values: Dict[Tuple["GraphQLRemoteField", int], object] = {}
        self.python_type: Optional[Type] = python_type
        self.mapped_types = False
        self.graphql_query_type: Optional[GraphQLObjectType] = None
        self.graphql_mutable_type: Optional[GraphQLObjectType] = None

        if not delay_mapping:
            self._initialize_type_mappers()

    def clear_cache(self):
        """Clear locally cached field values."""
        self.values.clear()

    def _initialize_type_mappers(self, force=False):
        """Ensure the Python type is mapped to its GraphQL query/mutation types."""
        if self.mappers is None:
            if not self.api:
                raise ValueError(
                    "Cannot initialize type mappers without a GraphQLAPI instance."
                )
            self.api.build_schema()
            self.mappers = GraphQLMappers(
                query_mapper=self.api.query_mapper,  # type: ignore
                mutable_mapper=self.api.mutation_mapper,  # type: ignore
            )

        if not self.mapped_types and self.python_type and self.mappers:
            self.mapped_types = True
            graphql_types = self.mappers.map(self.python_type)
            if isinstance(graphql_types, tuple) and len(graphql_types) == 2:
                query_type, mutable_type = graphql_types
                if query_type and not isinstance(query_type, GraphQLObjectType):
                    raise TypeError(
                        f"Expected GraphQLObjectType for query type, got {type(query_type)}"
                    )
                if mutable_type and not isinstance(mutable_type, GraphQLObjectType):
                    raise TypeError(
                        f"Expected GraphQLObjectType for mutable type, got {type(mutable_type)}"
                    )
                self.graphql_query_type = query_type
                self.graphql_mutable_type = mutable_type
            else:
                raise TypeError(
                    f"Expected a tuple of 2 types from mappers, got {graphql_types}"
                )

    def _gather_scalar_fields(self) -> List[Tuple["GraphQLRemoteField", Dict]]:
        """
        Gather a list of all scalar fields on the GraphQL query type
        that do not have required arguments.
        """
        self._initialize_type_mappers()

        def is_valid_field(field_def: GraphQLField):
            if not is_scalar(field_def.type):
                return False
            for arg in field_def.args.values():
                if isinstance(arg.type, GraphQLNonNull):
                    return False
            return True

        if not self.graphql_query_type:
            return []

        valid_field_names = [
            name
            for name, field in self.graphql_query_type.fields.items()
            if is_valid_field(field)
        ]
        return [(self.get_field(name), {}) for name in valid_field_names]

    def fetch(self, fields: Optional[List[Tuple["GraphQLRemoteField", Dict]]] = None):
        """Fetch values for the given scalar fields from the remote API."""
        if fields is None:
            fields = self._gather_scalar_fields()

        field_values = self._perform_sync_fetch(fields=fields)
        if isinstance(field_values, dict):
            for field, args in fields:
                field_value = field_values.get(to_camel_case(field.name))
                arg_hash = self.hash(args)
                self.values[(field, arg_hash)] = field_value
        # If field_values is a list, it's handled by the caller, e.g., get_value

    async def fetch_async(
        self, fields: Optional[List[Tuple["GraphQLRemoteField", Dict]]] = None
    ):
        """Asynchronously fetch values for the given scalar fields."""
        if fields is None:
            fields = self._gather_scalar_fields()

        field_values = await self._perform_async_fetch(fields=fields)
        if isinstance(field_values, dict):
            for field, args in fields:
                field_value = field_values.get(to_camel_case(field.name))
                arg_hash = self.hash(args)
                self.values[(field, arg_hash)] = field_value
        # If field_values is a list, it's handled by the caller, e.g., get_value

    def _perform_sync_fetch(
        self, fields: Optional[List[Tuple["GraphQLRemoteField", Dict]]] = None
    ):
        """Internal synchronous fetch implementation."""
        if not fields:
            fields = self._gather_scalar_fields()

        query = self._build_fetch_query(fields=fields)
        result = self.executor.execute(query=query)
        return self._process_fetch_result(query, result, fields)

    async def _perform_async_fetch(
        self, fields: Optional[List[Tuple["GraphQLRemoteField", Dict]]] = None
    ):
        """Internal asynchronous fetch implementation."""
        if not fields:
            fields = self._gather_scalar_fields()
        query = self._build_fetch_query(fields=fields)
        result = await self.executor.execute_async(query=query)
        return self._process_fetch_result(query, result, fields)

    def _build_fetch_query(self, fields: List[Tuple["GraphQLRemoteField", Dict]]):
        """Builds the GraphQL query string for fetching the given fields."""
        self._initialize_type_mappers()
        mutable = any(f.mutable for f, _ in self.call_history + fields)

        if not self.mappers:
            raise ValueError("Mappers not initialized before building query.")

        query_builder = GraphQLRemoteQueryBuilder(
            call_stack=self.call_history,
            fields=fields,
            mappers=self.mappers,
            mutable=mutable,
        )
        return query_builder.build()

    def _process_fetch_result(
        self,
        query: str,
        result: ExecutionResult,
        fields: List[Tuple["GraphQLRemoteField", Dict]],
    ):
        """
        Processes the result of a GraphQL fetch, raising any errors and mapping
        the data to field keys.
        """
        if result.errors:
            raise GraphQLRemoteError(
                query=query, result=result, message=str(result.errors)
            )

        field_values = result.data

        # Follow the call_history chain to get the correct nested data object
        for field, _ in self.call_history:
            if isinstance(field_values, list):
                # The code here assumes any lists are only scalar lists, which
                # doesn't allow nested object sets in lists. Adjust if needed.
                raise ValueError("GraphQLLists can only contain scalar values.")
            if field_values is None:
                raise NullResponse()
            field_values = field_values.get(to_camel_case(field.name))

        if field_values is None:
            raise NullResponse()

        def parse_field(key, value):
            """Parse a single field's value from the raw response."""
            field_obj = None
            for f, _ in fields:
                if f.name == key:
                    field_obj = f
                    break

            if not field_obj:
                raise KeyError(f"Could not find matching field for key {key}")

            field_type = field_obj.graphql_field.type

            if value is None:
                if not field_obj.nullable:
                    raise TypeError(
                        f"Received None for non-nullable field '{key}'. "
                        f"Expected type: {field_type}"
                    )
                return None

            unwrapped_field_type = get_named_type(field_type)
            if not is_scalar(unwrapped_field_type):
                raise TypeError(
                    f"Unable to parse non-scalar type {unwrapped_field_type}"
                )

            def _to_value(val):
                ast_val = to_ast_value(val, unwrapped_field_type)
                if isinstance(
                    unwrapped_field_type, (GraphQLScalarType, GraphQLEnumType)
                ) and hasattr(unwrapped_field_type, "parse_literal"):
                    parsed_val = unwrapped_field_type.parse_literal(ast_val, None)  # type: ignore
                    # If the field is an enum, convert to the Python enum if available
                    if isinstance(unwrapped_field_type, GraphQLEnumType) and hasattr(
                        unwrapped_field_type, "enum_type"
                    ):
                        return unwrapped_field_type.enum_type(parsed_val)  # type: ignore
                    return parsed_val
                return val  # Fallback for simple scalars

            if field_obj.list:
                return [_to_value(v) for v in value]
            return _to_value(value)

        if isinstance(field_values, list):
            # If the response is a list of dicts (scalar sets or enumerations)
            return [
                {k: parse_field(k, v) for k, v in single_item.items()}
                for single_item in field_values
            ]
        else:
            return {k: parse_field(k, v) for k, v in field_values.items()}

    def hash(self, args: Dict) -> int:
        """
        Return a stable hash for the provided arguments dict,
        turning lists into tuples for immutability.
        """
        hashable_args = {}
        for key, value in args.items():
            if isinstance(value, list):
                value = tuple(value)
            hashable_args[key] = value
        return hash(frozenset(hashable_args.items()))

    def _retrieve_cached_value(
        self,
        field: "GraphQLRemoteField",
        args: Dict,
    ) -> Tuple[object, bool, int]:
        """
        Check if a value is already cached for a given field + args. Return
        (value, bool_found, arg_hash).
        """
        try:
            arg_hash = self.hash(args)
        except TypeError:
            # If the args are not strictly hashable, fallback to a random hash
            arg_hash = hash(uuid.uuid4())

        if field.mutable:
            # If the field is mutable, invalidate the entire cache
            self.values.clear()

        for (cached_field, cached_hash), value in self.values.items():
            if field.name == cached_field.name and arg_hash == cached_hash:
                return value, True, arg_hash

        return None, False, arg_hash

    def _check_field_mutation_state(self, field: "GraphQLRemoteField"):
        """
        Prevent re-fetching certain fields after a mutation (if rules require).
        """
        mutated = any(f.mutable for f, _ in self.call_history)
        if mutated and (field.scalar or field.mutable or field.nullable):
            raise GraphQLError(
                f"Cannot fetch field '{field.name}' from {self.python_type}; "
                f"mutated objects cannot be re-fetched."
            )

    async def get_value_async(self, field: "GraphQLRemoteField", args: Dict):
        """
        Retrieve the given field from the remote service asynchronously,
        respecting caching, call history, and GraphQL type conversions.
        """
        self._initialize_type_mappers()
        cached_value, found, arg_hash = self._retrieve_cached_value(field, args)
        if found:
            return cached_value

        if (field, arg_hash) in self.values:
            return self.values.get((field, arg_hash))

        self._check_field_mutation_state(field)

        if field.scalar:
            await self.fetch_async(fields=[(field, args)])
            return self.values.get((field, arg_hash))

        # Non-scalar field: map to Python type or create sub-objects
        if not self.mappers:
            raise ValueError("Mappers not initialized")
        python_type = self.mappers.map(field.graphql_field.type, reverse=True)
        if not python_type:
            raise TypeError(
                f"Could not reverse map GraphQL type for field '{field.name}'"
            )

        obj = GraphQLRemoteObject(
            executor=self.executor,
            api=self.api,
            python_type=python_type,  # type: ignore
            mappers=self.mappers,
            call_history=[*self.call_history, (field, args)],
        )

        if field.list:
            data = await obj._perform_async_fetch()
            if not isinstance(data, list):
                # This can happen if the query returns a single object instead of a list
                # or if the response is otherwise not as expected.
                # Depending on strictness, could raise an error or return an empty list.
                return []
            fields = obj._gather_scalar_fields()
            remote_objects = []
            for item_data in data:
                nested_obj = GraphQLRemoteObject(
                    executor=self.executor,
                    api=self.api,
                    python_type=python_type,  # type: ignore
                    mappers=self.mappers,
                    call_history=[*self.call_history, (field, args)],
                )
                if isinstance(item_data, dict):
                    for sub_field, sub_args in fields:
                        val = item_data.get(to_camel_case(sub_field.name))
                        nested_obj.values[(sub_field, self.hash(sub_args))] = val
                remote_objects.append(nested_obj)
            return remote_objects

        # Single nested object
        if field.mutable or field.nullable:
            try:
                await obj.fetch_async()
            except NullResponse:
                return None

        if field.mutable:
            if not self.graphql_mutable_type or not self.mappers:
                return obj

            meta = self.mappers.mutable_mapper.meta.get(
                (self.graphql_mutable_type.name, field.name)
            )
            if (
                field.recursive
                and meta
                and meta.get(GraphQLMetaKey.resolve_to_self, True)
            ):
                self.values.update(obj.values)
                return self

        return obj

    def get_value(self, field: "GraphQLRemoteField", args: Dict):
        """
        Retrieve the given field from the remote service synchronously,
        respecting caching, call history, and GraphQL type conversions.
        """
        self._initialize_type_mappers()
        cached_value, found, arg_hash = self._retrieve_cached_value(field, args)
        if found:
            return cached_value

        if (field, arg_hash) in self.values:
            return self.values.get((field, arg_hash))

        self._check_field_mutation_state(field)

        if field.scalar:
            self.fetch(fields=[(field, args)])
            return self.values.get((field, arg_hash))

        # Non-scalar field: map to Python type or create sub-objects
        if not self.mappers:
            raise ValueError("Mappers not initialized")
        python_type = self.mappers.map(field.graphql_field.type, reverse=True)
        if not python_type:
            raise TypeError(
                f"Could not reverse map GraphQL type for field '{field.name}'"
            )

        obj = GraphQLRemoteObject(
            executor=self.executor,
            api=self.api,
            python_type=python_type,  # type: ignore
            mappers=self.mappers,
            call_history=[*self.call_history, (field, args)],
        )

        if field.list:
            data = obj._perform_sync_fetch()
            if not isinstance(data, list):
                return []
            fields = obj._gather_scalar_fields()
            remote_objects = []
            for item_data in data:
                nested_obj = GraphQLRemoteObject(
                    executor=self.executor,
                    api=self.api,
                    python_type=python_type,  # type: ignore
                    mappers=self.mappers,
                    call_history=[*self.call_history, (field, args)],
                )
                if isinstance(item_data, dict):
                    for sub_field, sub_args in fields:
                        val = item_data.get(to_camel_case(sub_field.name))
                        nested_obj.values[(sub_field, self.hash(sub_args))] = val
                remote_objects.append(nested_obj)
            return remote_objects

        # Single nested object
        if field.mutable or field.nullable:
            try:
                obj.fetch()
            except NullResponse:
                return None

        if field.mutable:
            if not self.graphql_mutable_type or not self.mappers:
                return obj
            meta = self.mappers.mutable_mapper.meta.get(
                (self.graphql_mutable_type.name, field.name)
            )
            if (
                field.recursive
                and meta
                and meta.get(GraphQLMetaKey.resolve_to_self, True)
            ):
                self.values.update(obj.values)
                return self

        return obj

    def get_field(self, name: str) -> "GraphQLRemoteField":
        """
        Retrieve a GraphQLRemoteField object by name, checking both
        query and mutation fields.
        """
        self._initialize_type_mappers()
        camel_name = to_camel_case(name)
        field = None
        mutable = False

        # Check query type fields
        if self.graphql_query_type and camel_name in self.graphql_query_type.fields:
            field = self.graphql_query_type.fields.get(camel_name)
        # Check mutation type fields
        elif (
            self.graphql_mutable_type and camel_name in self.graphql_mutable_type.fields
        ):
            field = self.graphql_mutable_type.fields.get(camel_name)
            mutable = True

        if not field:
            raise GraphQLError(f"Field '{name}' does not exist on '{self}'.")

        return GraphQLRemoteField(
            name=camel_name,
            mutable=mutable,
            graphql_field=field,
            parent=self,
        )

    def __getattr__(self, name):
        """
        Dynamic attribute access. If the attribute is a GraphQL field,
        return a callable (if it takes args) or automatically fetch it if
        it's property-like access.
        """
        if name == "__await__":
            # This object isn't intended to be awaited directly.
            raise AttributeError("Not Awaitable")

        try:
            field, auto_call = self._resolve_attribute(name)
            if auto_call:
                return field()  # Immediately call if it's property-like
            return field
        except GraphQLError as e:
            if "does not exist" in str(e):
                # Fallback to python attribute if GraphQL field does not exist
                if hasattr(self.python_type, name):
                    return getattr(self.python_type, name)
                else:
                    raise AttributeError(
                        f"'{self}' object has no attribute '{name}'"
                    ) from e
            else:
                raise

    async def call_async(self, name, *args, **kwargs):
        """
        Helper to call a remote field asynchronously when you only have
        the field's name. (Equivalent to remote_obj.<field>(*args, **kwargs).)
        """
        field, _ = self._resolve_attribute(name, pass_through=False)
        if isinstance(field, GraphQLRemoteField):
            return await field.call_async(*args, **kwargs)
        elif callable(field):
            # for regular python methods
            return field(*args, **kwargs)
        return field  # for properties

    def _resolve_attribute(self, name, pass_through=True):
        """
        Resolves the requested attribute name, either to a method/field on the
        Python type or a GraphQLRemoteField. Determines if it should be called
        immediately (auto_call) if it's a property or dataclass field, etc.
        """
        self._initialize_type_mappers()

        if not self.python_type:
            raise ValueError("python_type not set on GraphQLRemoteObject")

        python_attr = getattr(self.python_type, name, None)
        is_dataclass_field = False

        try:
            if is_dataclass(self.python_type):
                # noinspection PyDataclass
                is_dataclass_field = any(
                    f.name == name for f in dataclasses_fields(self.python_type)
                )
        except ImportError:
            pass

        is_property = isinstance(python_attr, property)
        is_callable_attr = callable(python_attr)

        # Some attribute types (e.g., SQLAlchemy columns) might be auto-called.
        auto_call = is_dataclass_field or is_property

        # Attempt to get the corresponding GraphQL field
        try:
            field_obj = self.get_field(name)
        except GraphQLError as err:
            if not pass_through:
                raise err
            # If the GraphQL field doesn't exist, fall back to the Python attribute
            if "does not exist" in err.message:
                if is_callable_attr:
                    # Possibly a regular method on the Python type
                    func = python_attr
                    if inspect.ismethod(func) or is_static_method(
                        self.python_type, name
                    ):
                        return func, False
                    # If it's a plain function, wrap it to provide self as first arg
                    return (lambda *a, **kw: func(self, *a, **kw)), False

                if is_property and python_attr.fget:
                    # Evaluate property
                    return python_attr.fget(self), False
            raise

        return field_obj, auto_call

    def __str__(self):
        self._initialize_type_mappers()
        if self.graphql_query_type:
            return f"<RemoteObject({self.graphql_query_type.name}) at {hex(id(self))}>"
        return f"<RemoteObject(Unmapped) at {hex(id(self))}>"


class GraphQLRemoteField:
    """
    Represents a single remote field on a GraphQL type, capturing:
      - field name
      - whether it is mutable
      - its parent GraphQLRemoteObject
      - the underlying GraphQLField metadata
    """

    def __init__(
        self,
        name: str,
        mutable: bool,
        graphql_field: GraphQLField,
        parent: GraphQLRemoteObject,
        is_property: bool = False,
    ):
        self.name = name
        self.mutable = mutable
        self.graphql_field = graphql_field
        self.parent = parent
        self.nullable = is_nullable(self.graphql_field.type)
        self.scalar = is_scalar(self.graphql_field.type)
        self.list = is_list(self.graphql_field.type)
        self.is_property = is_property

        # For recursive field detection
        self.recursive = False
        if self.parent.mappers:
            reversed_type = self.parent.mappers.map(
                self.graphql_field.type, reverse=True
            )
            if isinstance(reversed_type, type):
                self.recursive = self.parent.python_type == reversed_type

    def graphql_type(self) -> GraphQLNamedType:
        """Get the final unwrapped GraphQLType."""
        return get_named_type(self.graphql_field.type)

    def _convert_args_to_kwargs(self, args, kwargs):
        """
        Remap positional args to named args based on the GraphQL argument order.
        """
        arg_names = list(self.graphql_field.args.keys())
        if len(args) > len(arg_names):
            raise TypeError(
                f"{self.name} takes {len(arg_names)} argument(s) "
                f"({len(args)} given)"
            )
        for i, arg_val in enumerate(args):
            kwargs[arg_names[i]] = arg_val

    @property
    def is_async(self) -> bool:
        """Return True if the field is asynchronous."""
        if not self.graphql_field or not self.graphql_field.resolve:
            return False
        return inspect.iscoroutinefunction(self.graphql_field.resolve)

    def __call__(self, *args, **kwargs):
        """Invoke the field, either locally or remotely."""
        is_async = self.is_async or kwargs.get("aio")
        kwargs.pop("aio", None)

        if args:
            self._convert_args_to_kwargs(args, kwargs)

        if is_async:
            return self.parent.get_value_async(self, kwargs)
        return self.parent.get_value(self, kwargs)

    async def call_async(self, *args, **kwargs):
        """
        Invoke the remote field asynchronously. If positional args are given,
        they are remapped to named GraphQL arguments.
        """
        if args:
            self._convert_args_to_kwargs(args, kwargs)
        return await self.parent.get_value_async(self, kwargs)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}>"

    def __hash__(self):
        if self.parent.python_type:
            return hash((self.parent.python_type.__name__, self.name))
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, GraphQLRemoteField):
            return False
        return other.parent == self.parent and other.name == self.name


class GraphQLRemoteQueryBuilder:
    """
    Builds a GraphQL query/mutation string given a call stack (nested fields)
    and a list of final fields to fetch.
    """

    def __init__(
        self,
        call_stack: List[Tuple[GraphQLRemoteField, Dict]],
        fields: List[Tuple[GraphQLRemoteField, Dict]],
        mappers: GraphQLMappers,
        mutable=False,
    ):
        self.call_stack = call_stack
        self.fields = fields
        self.mappers = mappers
        self.mutable = mutable

    def build(self) -> str:
        operation = "mutation" if self.mutable else "query"

        for field, args in self.call_stack:
            operation += "{" + self._field_call(field, args)

        final_fields = ",".join(
            self._field_call(field, args) for field, args in self.fields
        )
        operation += "{" + final_fields + "}"

        # Close all opened braces
        operation += "}" * len(self.call_stack)
        return operation

    def _field_call(self, field: GraphQLRemoteField, args=None) -> str:
        """Build a single field call string, including arguments."""
        call_str = field.name
        if args:
            arg_strs = []
            for arg_name, arg_value in args.items():
                camel_key = to_camel_case(arg_name)
                graphql_arg = field.graphql_field.args[camel_key]
                graphql_type = graphql_arg.type
                mapped_value = self.map_to_input_value(
                    value=arg_value,
                    mappers=self.mappers,
                    expected_graphql_type=graphql_type,
                )
                if mapped_value is not None:
                    arg_strs.append(f"{camel_key}:{mapped_value}")
            if arg_strs:
                call_str += f"({','.join(arg_strs)})"
        return call_str

    def map_to_input_value(
        self,
        value,
        mappers: GraphQLMappers,
        expected_graphql_type: Optional[GraphQLType] = None,
    ):
        """
        Convert a Python value to a GraphQL argument representation (string),
        respecting lists, scalars, enums, and input objects.
        """
        if value is None:
            return None

        if isinstance(value, (list, set)):
            mapped_items = [
                self.map_to_input_value(
                    v, mappers=mappers, expected_graphql_type=expected_graphql_type
                )
                for v in value
            ]
            # Filter out None for safety
            return "[" + ",".join(str(v) for v in mapped_items if v is not None) + "]"

        if isinstance(value, (str, bytes)):
            if isinstance(value, bytes):
                return '"' + serialize_bytes(value) + '"'
            return json.dumps(value)  # Properly escape strings via JSON

        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, (float, int)):
            return str(value)

        if isinstance(value, enum.Enum):
            return str(value.value)

        unwrapped_type = (
            get_named_type(expected_graphql_type) if expected_graphql_type else None
        )

        # Possibly an input object
        if unwrapped_type is None and not isinstance(
            value, (str, bytes, bool, float, int, list, set, enum.Enum)
        ):
            # If expected_graphql_type was not provided and value is not a basic scalar/list,
            # try to map it assuming it's an input object.
            # This branch might need more robust type inference if expected_graphql_type is often None for objects.
            py_type_to_map = type(value)
            # Attempt to get the input type mapping
            # Note: mappers.query_mapper.input_type_mapper might not exist or be the correct mapper.
            # This part of the logic might need to be reviewed based on how mappers are structured
            # and when expected_graphql_type is None.
            if (
                hasattr(mappers.query_mapper, "input_type_mapper")
                and mappers.query_mapper.input_type_mapper is not None
            ):
                mapped_gql_type = mappers.query_mapper.input_type_mapper.map(
                    py_type_to_map
                )
                if mapped_gql_type:
                    unwrapped_type = get_named_type(mapped_gql_type)
            elif (
                hasattr(mappers.mutable_mapper, "input_type_mapper")
                and mappers.mutable_mapper.input_type_mapper is not None
            ):  # Check mutable mapper as well
                mapped_gql_type = mappers.mutable_mapper.input_type_mapper.map(
                    py_type_to_map
                )
                if mapped_gql_type:
                    unwrapped_type = get_named_type(mapped_gql_type)

        input_object_fields = getattr(unwrapped_type, "fields", {})
        if not input_object_fields and not isinstance(
            unwrapped_type, (GraphQLScalarType, GraphQLEnumType)
        ):
            raise GraphQLError(
                f"Unable to map {value} (type: {type(value)}) to the expected GraphQL input type '{unwrapped_type}'. "
                "No fields found or not a scalar/enum."
            )
        elif not input_object_fields and isinstance(
            unwrapped_type, (GraphQLScalarType, GraphQLEnumType)
        ):
            # This case should have been handled by earlier scalar checks if expected_graphql_type was a scalar.
            # If it reaches here, it implies a mismatch or unhandled complex scalar.
            pass

        input_values = {}
        if input_object_fields:
            for key, field in input_object_fields.items():
                try:
                    raw_input_value = getattr(value, to_snake_case(key))
                    if inspect.ismethod(raw_input_value):
                        raw_input_value = raw_input_value()
                except AttributeError:
                    if not is_nullable(field.type):
                        raise GraphQLError(
                            f"InputObject error: '{type(value)}' object has no attribute "
                            f"'{to_snake_case(key)}'. Non-null field '{key}' is missing. "
                            f"nested inputs must have matching attribute to field names"
                        )
                    continue  # Skip nullable fields with no matching attribute

                nested_val = self.map_to_input_value(
                    raw_input_value, mappers=mappers, expected_graphql_type=field.type
                )
                if nested_val is not None:
                    input_values[key] = nested_val

        if not input_values:
            return None

        return "{" + ",".join(f"{k}:{v}" for k, v in input_values.items()) + "}"

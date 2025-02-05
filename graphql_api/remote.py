import asyncio
import enum
import inspect
import json
import sys
import uuid
from typing import List, Tuple, Dict, Type

from dataclasses import fields as dataclasses_fields, is_dataclass
from requests.exceptions import RequestException

from graphql.language import ast
from graphql import (
    GraphQLInputObjectType,
    GraphQLObjectType,
    GraphQLEnumType,
    GraphQLInterfaceType,
    GraphQLUnionType,
    GraphQLID,
    GraphQLString,
    GraphQLFloat,
    GraphQLBoolean,
    GraphQLInt,
)
from graphql.execution import ExecutionResult
from graphql.type.definition import (
    GraphQLField,
    GraphQLScalarType,
    GraphQLNonNull,
    GraphQLList,
    GraphQLType,
    is_enum_type,
)

from graphql_api.error import GraphQLError
from graphql_api.executor import GraphQLBaseExecutor
from graphql_api.mapper import GraphQLTypeMapper, GraphQLMetaKey
from graphql_api.api import GraphQLAPI
from graphql_api.types import serialize_bytes
from graphql_api.utils import to_camel_case, url_to_ast, to_snake_case, http_query


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
    operation = context.request.info.operation.operation
    query = context.field.query
    redirected_query = operation.value + " " + query

    result = executor.execute(query=redirected_query)

    if result.errors:
        raise GraphQLError(str(result.errors))

    return result.data


def is_list(graphql_type: GraphQLType) -> bool:
    """Return True if the GraphQLType is a list (potentially nested)."""
    while hasattr(graphql_type, "of_type"):
        if isinstance(graphql_type, GraphQLList):
            return True
        if hasattr(graphql_type, "of_type"):
            graphql_type = graphql_type.of_type
    return False


def is_scalar(graphql_type: GraphQLType) -> bool:
    """
    Return True if the final unwrapped GraphQLType is a scalar or an enum.
    (ID, String, Float, Boolean, Int, or Enum).
    """
    while hasattr(graphql_type, "of_type"):
        graphql_type = graphql_type.of_type

    if isinstance(graphql_type, (GraphQLScalarType, GraphQLEnumType)):
        return True
    return False


def is_nullable(graphql_type: GraphQLType) -> bool:
    """Return False if the type is NonNull at any level, otherwise True."""
    while hasattr(graphql_type, "of_type"):
        if isinstance(graphql_type, GraphQLNonNull):
            return False
        if hasattr(graphql_type, "of_type"):
            graphql_type = graphql_type.of_type
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

    # Map Python scalars to their equivalent GraphQL AST node
    type_map = {
        (bool,): ast.BooleanValueNode,
        (str,): ast.StringValueNode,
        (float,): ast.FloatValueNode,
        (int,): ast.IntValueNode,
    }

    ast_type = None
    ast_value_node = None

    for py_types, candidate_ast_type in type_map.items():
        if isinstance(value, py_types):
            ast_type = candidate_ast_type
            ast_value_node = ast_type(value=value)
            break

    if isinstance(graphql_type, GraphQLEnumType) and ast_type == ast.StringValueNode:
        # Convert a string value to an EnumValueNode if the type is an enum
        enum_node = ast.EnumValueNode()
        enum_node.value = value
        ast_value_node = enum_node

    if not ast_value_node:
        raise TypeError(
            f"Unable to map Python scalar type {type(value)} "
            f"to a valid GraphQL AST type."
        )
    return ast_value_node


class GraphQLRemoteExecutor(GraphQLBaseExecutor, GraphQLObjectType):
    """
    A GraphQL executor that forwards operations to a remote GraphQL service.
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

        def resolver(info=None, context=None, *args, **kwargs):
            field_ = context.field_nodes[0]
            key_ = field_.alias.value if field_.alias else field_.name.value
            return info[key_]

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
                http_timeout=self.http_timeout,
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
                    http_timeout=self.http_timeout,
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
        api: GraphQLAPI = None,
        mappers: GraphQLMappers = None,
        python_type: Type = None,
        call_history: List[Tuple["GraphQLRemoteField", Dict]] = None,
        delay_mapping: bool = True,
    ):
        if not call_history:
            call_history = []

        if not api and python_type:
            api = GraphQLAPI(root_type=python_type)
        elif not python_type:
            python_type = api.root_type

        self.executor = executor
        self.api = api
        self.mappers = mappers
        self.call_history = call_history
        self.values: Dict[Tuple["GraphQLRemoteField", int], object] = {}
        self.python_type = python_type
        self.mapped_types = False
        self.graphql_query_type = None
        self.graphql_mutable_type = None

        if not delay_mapping:
            self._initialize_type_mappers()

    def clear_cache(self):
        """Clear locally cached field values."""
        self.values.clear()

    def _initialize_type_mappers(self, force=False):
        """Ensure the Python type is mapped to its GraphQL query/mutation types."""
        if self.mappers is None:
            self.api.build_schema()
            self.mappers = GraphQLMappers(
                query_mapper=self.api.query_mapper,
                mutable_mapper=self.api.mutation_mapper,
            )

        if not self.mapped_types:
            self.mapped_types = True
            graphql_types = self.mappers.map(self.python_type)
            self.graphql_query_type, self.graphql_mutable_type = graphql_types

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

        valid_field_names = [
            name
            for name, field in self.graphql_query_type.fields.items()
            if is_valid_field(field)
        ]
        return [(self.get_field(name), {}) for name in valid_field_names]

    def fetch(self, fields: List[Tuple["GraphQLRemoteField", Dict]] = None):
        """Fetch values for the given scalar fields from the remote API."""
        if fields is None:
            fields = self._gather_scalar_fields()

        field_values = self._perform_sync_fetch(fields=fields)
        for field, args in fields:
            field_value = field_values.get(to_camel_case(field.name))
            arg_hash = self.hash(args)
            self.values[(field, arg_hash)] = field_value

    async def fetch_async(self, fields: List[Tuple["GraphQLRemoteField", Dict]] = None):
        """Asynchronously fetch values for the given scalar fields."""
        if fields is None:
            fields = self._gather_scalar_fields()

        field_values = await self._perform_async_fetch(fields=fields)
        for field, args in fields:
            field_value = field_values.get(to_camel_case(field.name))
            arg_hash = self.hash(args)
            self.values[(field, arg_hash)] = field_value

    def _perform_sync_fetch(
        self, fields: List[Tuple["GraphQLRemoteField", Dict]] = None
    ):
        """Internal synchronous fetch implementation."""
        if not fields:
            fields = self._gather_scalar_fields()

        query = self._build_fetch_query(fields=fields)
        result = self.executor.execute(query=query)
        return self._process_fetch_result(query, result, fields)

    async def _perform_async_fetch(
        self, fields: List[Tuple["GraphQLRemoteField", Dict]] = None
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
                query=query, result=result, message=result.errors[0].message
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

            field_type = field_obj.graphql_type()

            if value is None:
                if not field_obj.nullable:
                    raise TypeError(
                        f"Received None for non-nullable field '{key}'. "
                        f"Expected type: {field_type}"
                    )
                return None

            if not is_scalar(field_type):
                raise TypeError(f"Unable to parse non-scalar type {field_type}")

            def _to_value(val):
                ast_val = to_ast_value(val, field_type)
                if hasattr(field_type, "parse_literal"):
                    parsed_val = field_type.parse_literal(ast_val)
                    # If the field is an enum, convert to the Python enum if available
                    if is_enum_type(field_type) and hasattr(field_type, "enum_type"):
                        return field_type.enum_type(parsed_val)
                    return parsed_val

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
        python_type = self.mappers.map(field.graphql_field.type, reverse=True)
        obj = GraphQLRemoteObject(
            executor=self.executor,
            api=self.api,
            python_type=python_type,
            mappers=self.mappers,
            call_history=[*self.call_history, (field, args)],
        )

        if field.list:
            data = await obj._perform_async_fetch()
            fields = obj._gather_scalar_fields()
            remote_objects = []
            for item_data in data:
                nested_obj = GraphQLRemoteObject(
                    executor=self.executor,
                    api=self.api,
                    python_type=python_type,
                    mappers=self.mappers,
                    call_history=[*self.call_history, (field, args)],
                )
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
        python_type = self.mappers.map(field.graphql_field.type, reverse=True)
        obj = GraphQLRemoteObject(
            executor=self.executor,
            api=self.api,
            python_type=python_type,
            mappers=self.mappers,
            call_history=[*self.call_history, (field, args)],
        )

        if field.list:
            data = obj._perform_sync_fetch()
            fields = obj._gather_scalar_fields()
            remote_objects = []
            for item_data in data:
                nested_obj = GraphQLRemoteObject(
                    executor=self.executor,
                    api=self.api,
                    python_type=python_type,
                    mappers=self.mappers,
                    call_history=[*self.call_history, (field, args)],
                )
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
        else:
            # Check mutation type fields
            if (
                self.graphql_mutable_type
                and camel_name in self.graphql_mutable_type.fields
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

        field, auto_call = self._resolve_attribute(name)
        if auto_call:
            return field()  # Immediately call if it's property-like
        return field

    async def call_async(self, name, *args, **kwargs):
        """
        Helper to call a remote field asynchronously when you only have
        the field's name. (Equivalent to remote_obj.<field>(*args, **kwargs).)
        """
        field, _ = self._resolve_attribute(name, pass_through=False)
        return await field.call_async(*args, **kwargs)

    def _resolve_attribute(self, name, pass_through=True):
        """
        Resolves the requested attribute name, either to a method/field on the
        Python type or a GraphQLRemoteField. Determines if it should be called
        immediately (auto_call) if it's a property or dataclass field, etc.
        """
        self._initialize_type_mappers()
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
                    else:
                        # If it's a plain function, wrap it to provide self as first arg
                        return (lambda *a, **kw: func(self, *a, **kw)), False

                if is_property:
                    # Evaluate property
                    return python_attr.fget(self), False
            raise

        return field_obj, auto_call

    def __str__(self):
        self._initialize_type_mappers()
        return f"<RemoteObject({self.graphql_query_type.name}) at {hex(id(self))}>"


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
    ):
        self.name = name
        self.mutable = mutable
        self.graphql_field = graphql_field
        self.parent = parent
        self.nullable = is_nullable(self.graphql_field.type)
        self.scalar = is_scalar(self.graphql_field.type)
        self.list = is_list(self.graphql_field.type)

        # For recursive field detection
        self.recursive = self.parent.python_type == self.parent.mappers.map(
            self.graphql_field.type, reverse=True
        )

    def graphql_type(self) -> GraphQLType:
        """Get the final unwrapped GraphQLType."""
        graphql_type = self.graphql_field.type
        while hasattr(graphql_type, "of_type"):
            graphql_type = graphql_type.of_type
        return graphql_type

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

    def __call__(self, *args, **kwargs):
        """
        Invoke the remote field synchronously. If positional args are given,
        they are remapped to named GraphQL arguments.
        """
        if args:
            self._convert_args_to_kwargs(args, kwargs)
        return self.parent.get_value(self, kwargs)

    async def call_async(self, *args, **kwargs):
        """
        Invoke the remote field asynchronously. If positional args are given,
        they are remapped to named GraphQL arguments.
        """
        if args:
            self._convert_args_to_kwargs(args, kwargs)
        return await self.parent.get_value_async(self, kwargs)

    def __hash__(self):
        return hash((self.parent.python_type.__name__, self.name))

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
        expected_graphql_type: GraphQLType = None,
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

        # Unwrap the expected_graphql_type
        while hasattr(expected_graphql_type, "of_type"):
            expected_graphql_type = expected_graphql_type.of_type

        # Possibly an input object
        if expected_graphql_type is None:
            expected_graphql_type = mappers.query_mapper.input_type_mapper.map(
                type(value)
            )

        input_object_fields = getattr(expected_graphql_type, "fields", {})
        if not input_object_fields:
            raise GraphQLError(
                f"Unable to map {value} to the expected GraphQL input type."
            )

        input_values = {}
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

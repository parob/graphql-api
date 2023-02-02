import asyncio
import enum
import inspect
import json
import uuid

from typing import List, Tuple, Dict, Type

from graphql.language import ast
from requests.exceptions import RequestException

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
    GraphQLInt
)
from graphql.execution import ExecutionResult
from graphql.type.definition import (
    GraphQLField,
    GraphQLScalarType,
    GraphQLNonNull,
    GraphQLList,
    GraphQLType,
    is_enum_type
)

from graphql_api.error import GraphQLError
from graphql_api.executor import GraphQLBaseExecutor
from graphql_api.mapper import GraphQLTypeMapper, GraphQLMetaKey
from graphql_api.api import GraphQLAPI
from graphql_api.types import serialize_bytes
from graphql_api.utils import \
    to_camel_case, \
    url_to_ast, \
    to_snake_case, \
    http_query


class GraphQLRemoteExecutor(GraphQLBaseExecutor, GraphQLObjectType):

    def __init__(
            self,
            url,
            name="Remote",
            description=None,
            http_method="GET",
            http_headers=None,
            http_timeout=None,
            verify=True,
            ignore_unsupported=True
    ):

        if not description:
            description = f'The `{name}` object type forwards all ' \
                          f'requests to the GraphQL executor at {url}'

        if http_headers is None:
            http_headers = {}

        self.url = url
        self.http_method = http_method
        self.http_headers = http_headers
        self.http_timeout = http_timeout
        self.verify = verify
        self.ignore_unsupported = ignore_unsupported

        super().__init__(name=name,
                         fields=self.build_fields,
                         description=description)

    def build_fields(self):
        ast_schema = url_to_ast(
            self.url,
            http_method=self.http_method,
            http_headers=self.http_headers
        )

        def resolver(info=None, context=None, *args, **kwargs):
            field_ = context.field_nodes[0]
            if field_.alias:
                key_ = field_.alias.value
            else:
                key_ = field_.name.value

            return info[key_]

        # noinspection PyProtectedMember
        for name, type in ast_schema.type_map.items():
            if (isinstance(type, GraphQLObjectType) or
                isinstance(type, GraphQLInputObjectType)) and \
                    not type.name.startswith("__"):
                for key, field in type.fields.items():
                    field.resolver = resolver
            elif isinstance(type, GraphQLEnumType):
                if not self.ignore_unsupported:
                    raise GraphQLError(
                        f"GraphQLScalarType '{type}' type is not supported "
                        f"in a remote executor '{self.url}'."
                    )
            elif isinstance(type, (GraphQLInterfaceType, GraphQLUnionType)):

                super_type = 'GraphQLInterface' \
                    if isinstance(type, GraphQLInterfaceType) \
                    else 'GraphQLUnionType'

                if not self.ignore_unsupported:
                    raise GraphQLError(
                        f"{super_type} '{type}' type is not supported"
                        f" from remote executor '{self.url}'."
                    )
            elif isinstance(type, GraphQLScalarType):
                if type not in [
                    GraphQLID,
                    GraphQLString,
                    GraphQLFloat,
                    GraphQLBoolean,
                    GraphQLInt
                ]:
                    if not self.ignore_unsupported:
                        raise GraphQLError(
                            f"GraphQLScalarType '{type}' type is not "
                            f"supported in a remote executor '{self.url}'."
                        )
            elif str(type).startswith('__'):
                continue
            else:
                raise GraphQLError(
                    f"Unknown GraphQLType '{type}' type is not supported in "
                    f"a remote executor '{self.url}'."
                )

        # noinspection PyProtectedMember
        return ast_schema.query_type.fields

    async def execute_async(
            self,
            query,
            variable_values=None,
            operation_name=None,
            http_headers=None
    ) -> ExecutionResult:

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
                verify=self.verify
            )
        except RequestException as e:
            import sys
            err_msg = f"{e}, remote service '{self.name}' is unavailable."
            raise type(e)(err_msg).with_traceback(sys.exc_info()[2])

        except ValueError as e:
            raise ValueError(
                f"{e}, from remote service '{self.name}'."
            )

        return ExecutionResult(
            data=json_.get('data'),
            errors=json_.get('errors')
        )

    def execute(
            self,
            query,
            variable_values=None,
            operation_name=None,
            http_headers=None
    ) -> ExecutionResult:

        if http_headers is None:
            http_headers = self.http_headers
        else:
            http_headers = {**self.http_headers, **http_headers}

        try:
            json_ = asyncio.run(http_query(
                url=self.url,
                query=query,
                variable_values=variable_values,
                operation_name=operation_name,
                http_method=self.http_method,
                http_headers=http_headers,
                http_timeout=self.http_timeout,
                verify=self.verify
            ))
        except RequestException as e:
            import sys
            err_msg = f"{e}, remote service '{self.name}' is unavailable."
            raise type(e)(err_msg).with_traceback(sys.exc_info()[2])

        except ValueError as e:
            raise ValueError(
                f"{e}, from remote service '{self.name}'."
            )

        return ExecutionResult(
            data=json_.get('data'),
            errors=json_.get('errors')
        )


class GraphQLMappers:

    def __init__(
            self,
            query_mapper: GraphQLTypeMapper,
            mutable_mapper: GraphQLTypeMapper
    ):
        self.query_mapper = query_mapper
        self.mutable_mapper = mutable_mapper

    def map(self, type, reverse=False):
        query_type = None
        try:
            if reverse:
                query_type = self.query_mapper.rmap(type)
            else:
                query_type = self.query_mapper.map(type)
        except Exception:
            pass

        mutable_type = None
        try:
            if reverse:
                mutable_type = self.mutable_mapper.rmap(type)
            else:
                mutable_type = self.mutable_mapper.map(type)
        except Exception:
            pass

        if reverse:
            return query_type or mutable_type

        return query_type, mutable_type


class NullResponse(BaseException):
    pass


class GraphQLRemoteError(GraphQLError):

    def __init__(self, query=None, result=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.query = query
        self.result = result


class GraphQLAsyncStub:

    async def call_async(self, name, *args, **kwargs):
        pass


class GraphQLRemoteObject:

    def get_labels(self) -> List[str]:
        return self.python_type.get_labels()

    @classmethod
    def from_url(
            cls,
            url: str,
            api: GraphQLAPI,
            http_method: str = "GET"
    ) -> 'GraphQLRemoteObject':
        executor = GraphQLRemoteExecutor(url=url, http_method=http_method)

        return GraphQLRemoteObject(executor=executor, api=api)

    # noinspection PyProtectedMember
    def __init__(
            self,
            executor: GraphQLBaseExecutor,
            api: GraphQLAPI = None,
            mappers: GraphQLMappers = None,
            python_type: Type = None,
            call_history: List[Tuple['GraphQLRemoteField', Dict]] = None,
            delay_mapping: bool = True
    ):
        if not call_history:
            call_history = []

        if not api and python_type:
            api = GraphQLAPI(root=python_type)

        elif not python_type:
            python_type = api.root_type

        self.executor = executor
        self.api = api
        self.mappers = mappers
        self.call_history = call_history
        self.values = {}
        self.python_type = python_type
        self.mapped_types = False
        self.graphql_query_type = None
        self.graphql_mutable_type = None

        if not delay_mapping:
            self._map()

    def clear_cache(self):
        self.values.clear()

    def _map(self, force=False):
        if self.mappers is None:
            api = self.api

            api.graphql_schema()

            self.mappers = GraphQLMappers(
                query_mapper=api.query_mapper,
                mutable_mapper=api.mutation_mapper
            )

        if not self.mapped_types:
            self.mapped_types = True
            graphql_types = self.mappers.map(self.python_type)
            self.graphql_query_type, self.graphql_mutable_type = graphql_types

    def fetch(self, fields: List[Tuple['GraphQLRemoteField', Dict]] = None):
        if fields is None:
            fields = self._fields()

        field_values = self._fetch(fields=fields)

        for field, args in fields:
            field_value = field_values.get(to_camel_case(field.name))

            arg_hash = self.hash(args)

            self.values[(field, arg_hash)] = field_value

    async def fetch_async(
            self,
            fields: List[Tuple['GraphQLRemoteField', Dict]] = None
    ):
        if fields is None:
            fields = self._fields()

        field_values = await self._fetch_async(fields=fields)

        for field, args in fields:
            field_value = field_values.get(to_camel_case(field.name))

            arg_hash = self.hash(args)

            self.values[(field, arg_hash)] = field_value

    def _fields(self):
        self._map()

        def is_valid_field(field):
            if not is_scalar(field.type):
                return False

            for arg in field.args.values():
                if isinstance(arg.type, GraphQLNonNull):
                    return False

            return True

        valid_fields = [
            name
            for name, field in self.graphql_query_type.fields.items()
            if is_valid_field(field)
        ]

        return [(self.get_field(name), {}) for name in valid_fields]

    def _fetch(self, fields: List[Tuple['GraphQLRemoteField', Dict]] = None):
        """
        Load all the scalar values for this object into the values dictionary
        :return:
        """
        if fields is None:
            fields = self._fields()

        query = self._fetch_build_query(fields=fields)

        result = self.executor.execute(query=query)

        return self._fetch_process(query, result, fields)

    async def _fetch_async(
            self,
            fields: List[Tuple['GraphQLRemoteField', Dict]] = None
    ):
        """
        Load all the scalar values for this object into the values dictionary
        :return:
        """
        if fields is None:
            fields = self._fields()

        query = self._fetch_build_query(fields=fields)

        result = await self.executor.execute_async(query=query)

        return self._fetch_process(query, result, fields)

    def _fetch_build_query(
            self,
            fields: List[Tuple['GraphQLRemoteField', Dict]]
    ):
        self._map()

        mutable = any([
            field.mutable
            for field, args in self.call_history + fields])

        query_builder = GraphQLRemoteQueryBuilder(
            call_stack=self.call_history,
            fields=fields,
            mappers=self.mappers,
            mutable=mutable
        )

        return query_builder.build()

    def _fetch_process(
            self,
            query,
            result: ExecutionResult,
            fields: List[Tuple['GraphQLRemoteField', Dict]]
    ):

        if result.errors:
            raise GraphQLRemoteError(
                query=query,
                result=result,
                message=result.errors[0]["message"]
            )

        field_values = result.data
        for field, args in self.call_history:
            camel_name = to_camel_case(field.name)

            if isinstance(field_values, list):
                raise ValueError(
                    "GraphQLLists can only contain scalar values."
                )

            if field_values is None:
                raise NullResponse()

            field_values = field_values.get(camel_name)

        if field_values is None:
            raise NullResponse()

        def parse_field(key, value):

            field: GraphQLRemoteField = None

            for _field, _field_dict in fields:
                if _field.name == key:
                    field = _field
                    break

            if not field:
                raise KeyError(
                    f"Could not find field for key {key}"
                )

            field_type = field.graphql_type()

            if value is None:
                if not field.nullable:
                    raise TypeError(
                        f"Unable to parse None type for non nullable field, "
                        f"'{key}'. Expected type: {field_type}"
                    )
                return None

            if not is_scalar(field_type):
                raise TypeError(
                    f"Unable to parse non-scalar type {field_type}"
                )

            def _to_value(value):
                ast_value = to_ast_value(value, field_type)

                if hasattr(field_type, 'parse_literal'):
                    value = field_type.parse_literal(ast_value)

                    if is_enum_type(field_type) and \
                            hasattr(field_type, 'enum_type'):
                        enum_type = field_type.enum_type
                        value = enum_type(value)

                    return value

            if field.list:
                values = []
                for _value in value:
                    values.append(_to_value(value))
                return value
            else:
                return _to_value(value)

            raise TypeError(
                f"Scalar type {field_type} missing 'parse_literal' attribute"
            )

        if isinstance(field_values, list):
            field_values = [
                {
                    key: parse_field(key, value)
                    for key, value in field_values_list_item.items()
                }
                for field_values_list_item in field_values
            ]
        else:
            field_values = {
                key: parse_field(key, value)
                for key, value in field_values.items()
            }

        return field_values

    def hash(self, args: Dict):
        hashable_args = {}

        for key, value in args.items():

            if isinstance(value, list):
                value = tuple(value)

            hashable_args[key] = value

        return hash(frozenset(hashable_args.items()))

    def _get_value_cached(self, field: 'GraphQLRemoteField', args: Dict):
        try:
            arg_hash = self.hash(args)
        except TypeError:
            arg_hash = hash(uuid.uuid4())

        if field.mutable:
            self.values.clear()

        for ((_field, _arg_hash), value) in self.values.items():
            if field.name == _field.name and arg_hash == _arg_hash:
                return value, True, arg_hash

        return None, False, arg_hash

    def _get_value_check_mutated(self, field):
        mutated = any([field.mutable for field, args in self.call_history])

        if mutated and (field.scalar or field.mutable or field.nullable):
            raise GraphQLError(
                f"Cannot fetch {field.name} from {self.python_type}, "
                f"mutated objects cannot be re-fetched."
            )

    async def get_value_async(self, field: 'GraphQLRemoteField', args: Dict):
        self._map()
        value, result, arg_hash = self._get_value_cached(field, args)

        if result:
            return value

        if (field, arg_hash) in self.values.keys():
            return self.values.get((field, arg_hash), None)

        self._get_value_check_mutated(field)

        if field.scalar:
            await self.fetch_async(fields=[(field, args)])
            return self.values.get((field, arg_hash), None)

        else:
            python_type = self.mappers.map(
                field.graphql_field.type,
                reverse=True
            )

            obj = GraphQLRemoteObject(
                executor=self.executor,
                api=self.api,
                python_type=python_type,
                mappers=self.mappers,
                call_history=[*self.call_history, (field, args)]
            )

            if field.list:
                data = await obj._fetch_async()
                fields = obj._fields()
                remote_objects = []

                for remote_object_data in data:
                    remote_object = GraphQLRemoteObject(
                        executor=self.executor,
                        api=self.api,
                        python_type=python_type,
                        mappers=self.mappers,
                        call_history=[*self.call_history, (field, args)]
                    )

                    for field, args in fields:
                        field_value = remote_object_data.get(
                            to_camel_case(field.name)
                        )
                        arg_hash = self.hash(args)
                        field_key = (field, arg_hash)
                        remote_object.values[field_key] = field_value

                    remote_objects.append(remote_object)
                return remote_objects

            else:
                if field.mutable or field.nullable:
                    try:
                        await obj.fetch_async()
                    except NullResponse:
                        return None

                if field.mutable:
                    meta = self.mappers.mutable_mapper.meta.get(
                        (self.graphql_mutable_type.name, field.name)
                    )

                    if field.recursive and \
                            meta and \
                            meta.get(GraphQLMetaKey.resolve_to_self, True):
                        self.values.update(obj.values)
                        return self

                return obj

    def get_value(self, field: 'GraphQLRemoteField', args: Dict):
        self._map()
        value, result, arg_hash = self._get_value_cached(field, args)

        if result:
            return value

        if (field, arg_hash) in self.values.keys():
            return self.values.get((field, arg_hash), None)

        self._get_value_check_mutated(field)

        if field.scalar:
            self.fetch(fields=[(field, args)])
            return self.values.get((field, arg_hash), None)

        else:
            python_type = self.mappers.map(
                field.graphql_field.type,
                reverse=True
            )

            obj = GraphQLRemoteObject(
                executor=self.executor,
                api=self.api,
                python_type=python_type,
                mappers=self.mappers,
                call_history=[*self.call_history, (field, args)]
            )

            if field.list:
                data = obj._fetch()
                fields = obj._fields()
                remote_objects = []

                for remote_object_data in data:
                    remote_object = GraphQLRemoteObject(
                        executor=self.executor,
                        api=self.api,
                        python_type=python_type,
                        mappers=self.mappers,
                        call_history=[*self.call_history, (field, args)]
                    )

                    for field, args in fields:
                        field_value = remote_object_data.get(
                            to_camel_case(field.name)
                        )
                        arg_hash = self.hash(args)
                        field_key = (field, arg_hash)
                        remote_object.values[field_key] = field_value

                    remote_objects.append(remote_object)
                return remote_objects

            else:
                if field.mutable or field.nullable:
                    try:
                        obj.fetch()
                    except NullResponse:
                        return None

                if field.mutable:
                    meta = self.mappers.mutable_mapper.meta.get(
                        (self.graphql_mutable_type.name, field.name)
                    )

                    if field.recursive and \
                            meta and \
                            meta.get(GraphQLMetaKey.resolve_to_self, True):
                        self.values.update(obj.values)
                        return self

                return obj

    def get_field(self, name):
        self._map()

        camel_name = to_camel_case(name)
        field = None
        mutable = False

        try:
            field = self.graphql_query_type.fields.get(camel_name)
        except AssertionError:
            pass

        if field is None:
            try:
                field = self.graphql_mutable_type.fields.get(camel_name)
                mutable = True
            except AssertionError:
                pass

        if not field:
            raise GraphQLError(f"Field {name} on {self} does not exist")

        return GraphQLRemoteField(
            name=camel_name,
            mutable=mutable,
            graphql_field=field,
            parent=self
        )

    def __getattr__(self, name):
        if name == "__await__":
            raise AttributeError('Not Awaitable')

        field, auto_call = self.getattr(name)

        if auto_call:
            return field()

        return field

    async def call_async(self, name, *args, **kwargs):
        field, auto_call = self.getattr(name, pass_through=False)
        return await field.call_async(*args, **kwargs)

    def getattr(self, name, pass_through=True):
        self._map()

        attribute_type = getattr(self.python_type, name, None)

        is_dataclass_field = False

        try:
            from dataclasses import fields, is_dataclass

            if is_dataclass(self.python_type):
                # noinspection PyDataclass
                field_names = [
                    field.name
                    for field in fields(self.python_type)
                ]

                is_dataclass_field = name in field_names

        except ImportError:
            pass

        is_property = isinstance(attribute_type, property)
        is_callable = callable(attribute_type)

        auto_call = is_dataclass_field or is_property

        if not auto_call:
            try:
                from sqlalchemy.orm.attributes import InstrumentedAttribute
                auto_call = isinstance(attribute_type, InstrumentedAttribute)
            except ImportError:
                pass

        try:
            field = self.get_field(name)

        except GraphQLError as err:
            if not pass_through:
                raise err

            if "does not exist" in err.message:
                if is_callable:
                    func = getattr(self.python_type, name)
                    _is_method = inspect.ismethod(func)
                    _is_static_method = is_static_method(
                        self.python_type,
                        name
                    )

                    if _is_method or _is_static_method:
                        return func, False
                    else:
                        return (lambda *args, **kwargs: func(
                            self,
                            *args, **kwargs
                        )), False

                if is_property:
                    prop = getattr(self.python_type, name)
                    return prop.fget(self), False
            raise

        return field, auto_call

    def __str__(self):
        self._map()

        return f"<RemoteObject({self.graphql_query_type.name}) " \
               f"at {hex(id(self))}>"


class GraphQLRemoteField:

    # noinspection PyProtectedMember
    def __init__(
            self,
            name: str,
            mutable: bool,
            graphql_field: GraphQLField,
            parent: GraphQLRemoteObject
    ):
        self.name = name
        self.mutable = mutable
        self.graphql_field = graphql_field
        self.parent = parent
        self.nullable = is_nullable(self.graphql_field.type)
        self.scalar = is_scalar(self.graphql_field.type)
        self.list = is_list(self.graphql_field.type)

        self.recursive = self.parent.python_type == self.parent.mappers.map(
            self.graphql_field.type,
            reverse=True
        )

    def graphql_type(self) -> GraphQLType:
        graphql_type = self.graphql_field.type
        while hasattr(graphql_type, 'of_type'):
            graphql_type = graphql_type.of_type

        return graphql_type

    def remap_args_to_kwargs(self, args, kwargs):
        arg_names = list(self.graphql_field.args.keys())
        arg_names_count = len(arg_names)
        arg_count = len(args)

        if arg_count > arg_names_count:
            raise TypeError(
                f"{self.name} takes {arg_names_count} "
                f"argument{'s' if arg_names_count > 1 else ''} "
                f"({arg_count} given)"
            )

        for arg_index in range(0, arg_count):
            arg_name = arg_names[arg_index]
            kwargs[arg_name] = args[arg_index]

    def __call__(self, *args, **kwargs):
        if args:
            self.remap_args_to_kwargs(args=args, kwargs=kwargs)
        return self.parent.get_value(self, kwargs)

    async def call_async(self, *args, **kwargs):
        if args:
            self.remap_args_to_kwargs(args=args, kwargs=kwargs)
        return await self.parent.get_value_async(self, kwargs)

    def __hash__(self):
        return hash(hash(self.parent.python_type.__name__) + hash(self.name))

    def __eq__(self, other):
        if isinstance(other, GraphQLRemoteField):
            if other.parent == self.parent and other.name == self.name:
                return True


class GraphQLRemoteQueryBuilder:

    def __init__(
            self,
            call_stack: List[Tuple['GraphQLRemoteField', Dict]],
            fields: List[Tuple['GraphQLRemoteField', Dict]],
            mappers: GraphQLMappers,
            mutable=False
    ):
        self.call_stack = call_stack
        self.fields = fields
        self.mappers = mappers
        self.mutable = mutable

    def build(self):
        if self.mutable:
            query = 'mutation'
        else:
            query = 'query'

        def to_field_call(field, args=None):
            name = field.name
            field_call = to_camel_case(name)
            if args:
                values = []
                for key, value in args.items():
                    camel_key = to_camel_case(key)
                    graphql_arg = field.graphql_field.args[camel_key]
                    graphql_type = graphql_arg.type

                    str_value = self.map_to_input_value(
                        value=value,
                        expected_graphql_type=graphql_type,
                        mappers=self.mappers
                    )

                    if str_value is not None:
                        values.append(f"{camel_key}:{str_value}")

                field_call += f"({','.join(values)})"
            return field_call

        for field, args in self.call_stack:
            query += "{" + to_field_call(field, args=args)

        field_calls = [
            to_field_call(field, args=args)
            for field, args in self.fields
        ]

        query += "{" + ",".join(field_calls) + "}"
        query += "}" * len(self.call_stack)

        return query

    # noinspection PyMethodMayBeStatic
    def map_to_input_value(
            self,
            value,
            mappers: GraphQLMappers,
            expected_graphql_type=None
    ):
        from graphql_api.mapper import is_scalar

        if value is None:
            return None

        python_type = type(value)

        if is_scalar(python_type):
            if isinstance(value, (list, set)):
                values = [
                    self.map_to_input_value(
                        item,
                        mappers=mappers,
                        expected_graphql_type=expected_graphql_type
                    )
                    for item in value
                ]
                return '[' + ','.join(values) + ']'

            if isinstance(value, str):
                return json.dumps(value)
            if isinstance(value, bool):
                return 'true' if value else 'false'
            if isinstance(value, (float, int)):
                return str(value)
            if isinstance(value, bytes):
                return '"' + serialize_bytes(value) + '"'
            else:
                return '"' + str(value) + '"'

        if isinstance(value, enum.Enum):
            return str(value.value)

        if isinstance(value, object):

            if expected_graphql_type is not None:

                while hasattr(expected_graphql_type, 'of_type'):
                    expected_graphql_type = expected_graphql_type.of_type

                graphql_type = expected_graphql_type
            else:
                graphql_type = mappers.query_mapper.input_type_mapper.map(
                    type(value)
                )

            input_dict = {}

            for key, field in graphql_type.fields.items():
                try:
                    raw_input_value = getattr(value, to_snake_case(key))

                    if inspect.ismethod(raw_input_value):
                        raw_input_value = raw_input_value()

                except AttributeError:
                    if not is_nullable(field.type):
                        raise GraphQLError(
                            f"InputObject error, '{type(value)}' object has"
                            f" no attribute {to_snake_case(key)}, nested"
                            f" inputs must have matching attribute "
                            f"to field names"
                        )
                else:
                    _value = self.map_to_input_value(
                        raw_input_value,
                        mappers=mappers
                    )

                    if _value is not None:
                        input_dict[key] = _value

            input_values = [
                f"{key}:{value}"
                for key, value in input_dict.items()
            ]

            input_value = "{" + ",".join(input_values) + "}"

            return input_value


def remote_execute(executor: GraphQLBaseExecutor, context):
    operation = context.request.info.operation.operation
    query = context.field.query
    redirected_query = operation.value + " " + query

    result = executor.execute(query=redirected_query)

    if result.errors:
        raise GraphQLError(str(result.errors))

    return result.data


def is_list(graphql_type):
    while hasattr(graphql_type, 'of_type'):
        if isinstance(graphql_type, GraphQLList):
            return True
        graphql_type = graphql_type.of_type

    return False


def is_scalar(graphql_type):
    while hasattr(graphql_type, 'of_type'):
        graphql_type = graphql_type.of_type

    if isinstance(graphql_type, GraphQLScalarType):
        return True

    if isinstance(graphql_type, GraphQLEnumType):
        return True

    return False


def is_nullable(graphql_type):
    while hasattr(graphql_type, 'of_type'):
        if isinstance(graphql_type, GraphQLNonNull):
            return False
        graphql_type = graphql_type.of_type

    return True


def is_static_method(klass, attr, value=None):
    if value is None:
        value = getattr(klass, attr)
    assert getattr(klass, attr) == value

    for cls in inspect.getmro(klass):
        if inspect.isroutine(value):
            if attr in cls.__dict__:
                bound_value = cls.__dict__[attr]
                if isinstance(bound_value, staticmethod):
                    return True

    return False


def to_ast_value(value, graphql_type):
    if value is None:
        return None

    type_map = {
        (bool,): ast.BooleanValueNode,
        (str,): ast.StringValueNode,
        (float,): ast.FloatValueNode,
        (int,): ast.IntValueNode
    }
    ast_type = None
    ast_value = None

    for types, ast_type in type_map.items():
        if isinstance(value, types):
            ast_value = ast_type(value=value)
            break

    if isinstance(graphql_type, GraphQLEnumType):
        if ast_type == ast.StringValueNode:
            ast_value = ast.EnumValueNode()
            ast_value.value = value

    if not ast_value:
        raise TypeError(
            f"Unable to map Python scalar type {type(value)} "
            f"to a valid GraphQL ast type"
        )
    else:
        return ast_value

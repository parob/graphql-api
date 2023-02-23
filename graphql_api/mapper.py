import enum
import inspect
import collections.abc

import typing
import types
import typing_inspect

from uuid import UUID

from typing import List, Union, Type, Callable, Tuple, Any, Dict, Set

from typing_inspect import get_origin
from datetime import datetime

from graphql import (
    GraphQLObjectType,
    GraphQLField,
    GraphQLString,
    GraphQLList,
    GraphQLBoolean,
    GraphQLInt,
    GraphQLFloat
)

from graphql.type.definition import (
    GraphQLType,
    GraphQLUnionType,
    GraphQLInterfaceType,
    GraphQLArgument,
    GraphQLInputObjectType,
    is_input_type,
    GraphQLEnumType,
    GraphQLScalarType,
    GraphQLNonNull,
    GraphQLInputField
)

from graphql.pyutils import Undefined, UndefinedType

from graphql_api.context import GraphQLContext
from graphql_api.types import (
    GraphQLBytes,
    GraphQLUUID,
    GraphQLDateTime,
    GraphQLJSON, JsonType
)

from graphql_api.utils import to_camel_case, to_snake_case, to_input_value
from graphql_api.exception import GraphQLBaseException
from graphql_api.dataclass_mapping import \
    type_is_dataclass, \
    type_from_dataclass

"""
class AnyObject:


    @classmethod
    def graphql_from_input(cls, age: int):
        pass

    # @classmethod
    # def graphql_fields(cls):
    #     pass

"""


class GraphQLTypeMapInvalid(GraphQLBaseException):
    pass


class GraphQLTypeMapError(GraphQLBaseException):
    pass


class GraphQLTypeWrapper:

    @classmethod
    def graphql_type(cls, mapper: "GraphQLTypeMapper") -> GraphQLType:
        pass


class GraphQLMetaKey(enum.Enum):
    resolve_to_mutable = "RESOLVE_TO_MUTABLE"
    resolve_to_self = "RESOLVE_TO_SELF"
    native_middleware = "NATIVE_MIDDLEWARE"


class GraphQLMutableField(GraphQLField):
    pass


class GraphQLTypeMapper:

    def __init__(
        self,
        as_mutable=False,
        as_input=False,
        registry=None,
        reverse_registry=None,
        suffix="",
        schema=None
    ):
        self.as_mutable = as_mutable
        self.as_input = as_input
        self.registry = registry or {}
        self.reverse_registry = reverse_registry or {}
        self.suffix = suffix
        self.meta = {}
        self.input_type_mapper = None
        self.schema = schema

    def types(self) -> Set[GraphQLType]:
        return set(self.registry.values())

    def map_to_field(
        self,
        function_type: Callable,
        name="",
        key=""
    ) -> GraphQLField:
        type_hints = typing.get_type_hints(function_type)
        description = inspect.getdoc(function_type)

        return_type = type_hints.pop('return', None)

        if not return_type:
            raise GraphQLTypeMapInvalid(
                f"Field '{name}.{key}' with function ({function_type}) did "
                f"not specify a valid return type."
            )

        return_graphql_type = self.map(return_type)

        nullable = False

        if typing_inspect.is_union_type(return_type):
            union_args = typing_inspect.get_args(return_type, evaluate=True)
            if type(None) in union_args:
                nullable = True

        if not self.validate(return_graphql_type):
            raise GraphQLTypeMapError(
                f"Field '{name}.{key}' with function '{function_type}' return "
                f"type '{return_type}' could not be mapped to a valid GraphQL "
                f"type, was mapped to invalid type {return_graphql_type}."
            )

        enum_return = None

        if isinstance(return_graphql_type, GraphQLEnumType):
            enum_return = return_type

        if not nullable:
            return_graphql_type: GraphQLType = GraphQLNonNull(
                return_graphql_type
            )

        signature = inspect.signature(function_type)

        default_args = {
            key: value.default
            for key, value in signature.parameters.items()
            if value.default is not inspect.Parameter.empty
        }

        input_type_mapper = GraphQLTypeMapper(
            as_mutable=self.as_mutable,
            as_input=True,
            registry=self.registry,
            reverse_registry=self.reverse_registry,
            suffix=self.suffix,
            schema=self.schema
        )
        self.input_type_mapper = input_type_mapper
        arguments = {}
        enum_arguments = {}

        include_context = False

        for key, hint in type_hints.items():
            if key == 'context' and \
                    inspect.isclass(hint) and \
                    issubclass(hint, GraphQLContext):
                include_context = True
                continue

            arg_type = input_type_mapper.map(hint)

            if isinstance(arg_type, GraphQLEnumType):
                enum_arguments[key] = hint

            nullable = key in default_args
            if not nullable:
                arg_type = GraphQLNonNull(arg_type)

            arguments[to_camel_case(key)] = GraphQLArgument(
                type_=arg_type,
                default_value=default_args.get(key, Undefined)
            )

        def resolve(self, info=None, context=None, *args, **kwargs):
            _args = {to_snake_case(key): arg for key, arg in kwargs.items()}

            def _unwrap_union(_type):
                if typing_inspect.is_optional_type(_type):
                    return typing_inspect.get_args(_type, evaluate=True)[0]
                return _type

            if enum_arguments:
                enum_keys = list(enum_arguments.keys())
                _args = {
                    key: _unwrap_union(enum_arguments[key])(arg)
                    if key in enum_keys else arg
                    for key, arg in _args.items()
                }

            if include_context:
                _args['context'] = info.context

            function_name = function_type.__name__
            parent_type = self.__class__
            class_attribute = getattr(parent_type, function_name, None)
            is_property = isinstance(class_attribute, property)
            response = None

            if is_property:
                if _args:
                    if len(_args) > 1:
                        raise KeyError(
                            f"{function_name} on type {parent_type} is a"
                            f" property, and cannot have multiple arguments."
                        )
                    else:
                        response = function_type(self, **_args)
                else:
                    response = getattr(self, function_name, None)
            else:
                function_type_override = getattr(self, function_name, None)

                if function_type_override is not None:
                    response = function_type_override(**_args)
                else:
                    response = function_type(self, **_args)

            if enum_return:
                if isinstance(response, enum.Enum):
                    response = response.value

            return response

        field_class = GraphQLField
        func_type = get_value(function_type, self.schema, 'type')
        if func_type == "mutation":
            field_class = GraphQLMutableField

        return field_class(
            return_graphql_type,
            arguments,
            resolve,
            description=description
        )

    def map_to_union(self, union_type: Union) -> GraphQLType:
        union_args = typing_inspect.get_args(union_type, evaluate=True)
        none_type = type(None)
        union_map: Dict[type, GraphQLType] = {
            arg: self.map(arg)
            for arg in union_args if arg and arg != none_type
        }

        if len(union_map) == 1:
            _, mapped_type = union_map.popitem()
            return mapped_type

        def resolve_type(value, info, _type):
            from graphql_api.remote import GraphQLRemoteObject

            value_type = type(value)

            if isinstance(value, GraphQLRemoteObject):
                value_type = value.python_type

            for arg, mapped_type in union_map.items():
                if issubclass(value_type, arg):
                    return mapped_type.name

        names = [arg.__name__ for arg in union_args]
        name = f"{''.join(names)}{self.suffix}Union"

        return GraphQLUnionType(
            name,
            types=[*union_map.values()],
            resolve_type=resolve_type
        )

    def map_to_list(self, type_: List) -> GraphQLList:
        list_subtype = typing_inspect.get_args(type_)[0]

        list_type = GraphQLList(type_=self.map(list_subtype))

        return list_type

    def map_to_enum(self, type_: Type[enum.Enum]) -> GraphQLEnumType:
        enum_type = type_
        name = f"{type_.__name__}Enum"
        # Enums dont include a suffix as they are immutable

        description = inspect.getdoc(enum_type)

        enum_type = GraphQLEnumType(
            name=name,
            values=enum_type,
            description=description
        )

        enum_type.enum_type = type_

        def serialize(self, value) -> Union[str, None, UndefinedType]:
            if value and isinstance(value, collections.abc.Hashable):
                if isinstance(value, enum.Enum):
                    value = value.value

                lookup_value = self._value_lookup.get(value)
                if lookup_value:
                    return lookup_value
                else:
                    return Undefined

            return None

        enum_type.serialize = types.MethodType(serialize, enum_type)

        return enum_type

    scalar_map = [
        ([UUID], GraphQLUUID),
        ([str], GraphQLString),
        ([bytes], GraphQLBytes),
        ([bool], GraphQLBoolean),
        ([int], GraphQLInt),
        ([dict, list, set], GraphQLJSON),
        ([float], GraphQLFloat),
        ([datetime], GraphQLDateTime),
        ([type(None)], None)
    ]

    def scalar_classes(self):
        classes = []
        for scalar_class_map in self.scalar_map:
            for scalar_class in scalar_class_map[0]:
                classes.append(scalar_class)
        return classes

    def map_to_scalar(self, class_type: Type) -> GraphQLScalarType:
        for test_types, graphql_type in self.scalar_map:
            for test_type in test_types:
                if issubclass(class_type, test_type):
                    return graphql_type

    def map_to_interface(self, class_type: Type, ) -> GraphQLType:
        subclasses = class_type.__subclasses__()
        name = class_type.__name__

        for subclass in subclasses:
            if not is_abstract(subclass, self.schema):
                self.map(subclass)

        class_funcs = get_class_funcs(class_type, self.schema, self.as_mutable)

        interface_name = f"{name}{self.suffix}Interface"
        description = inspect.getdoc(class_type)

        def local_resolve_type():
            local_self = self

            def resolve_type(value, info, _type):
                return local_self.map(type(value)).name
            return resolve_type

        def local_fields():
            local_self = self
            local_class_funcs = class_funcs
            local_class_type = class_type
            local_name = name

            def fields():
                fields_ = {}
                for key_, func_ in local_class_funcs:
                    local_class_name = local_class_type.__name__
                    func_.__globals__[local_class_name] = local_class_type
                    fields_[to_camel_case(key_)] = local_self.map_to_field(
                        func_,
                        local_name,
                        key_
                    )

                return fields_
            return fields

        return GraphQLInterfaceType(
            interface_name,
            fields=local_fields(),
            resolve_type=local_resolve_type(),
            description=description
        )

    def map_to_input(self, class_type: Type) -> GraphQLType:
        name = f"{class_type.__name__}{self.suffix}Input"

        if hasattr(class_type, 'graphql_from_input'):
            creator = class_type.graphql_from_input
            func = creator

        else:
            creator = class_type
            func = class_type.__init__

        description = inspect.getdoc(func) or inspect.getdoc(class_type)

        try:
            type_hints = typing.get_type_hints(func)
        except Exception as err:
            raise TypeError(
                f"Unable to build input type '{name}' for '{class_type}', "
                f"check the '{class_type}.__init__' method or the "
                f"'{class_type}.graphql_from_input' method, {err}."
            )
        type_hints.pop("return", None)

        signature = inspect.signature(func)

        default_args = {
            key: value.default
            for key, value in signature.parameters.items()
            if value.default is not inspect.Parameter.empty
        }

        def local_fields():

            local_name = name
            local_self = self
            local_type_hints = type_hints
            local_default_args = default_args

            def fields():
                arguments = {}

                for key, hint in local_type_hints.items():

                    input_arg_type = local_self.map(hint)

                    nullable = key in local_default_args
                    if not nullable:
                        input_arg_type = GraphQLNonNull(input_arg_type)

                    default_value = local_default_args.get(key, None)

                    if default_value is not None:
                        try:
                            default_value = to_input_value(default_value)
                        except ValueError as err:
                            raise ValueError(
                                f"Unable to map {local_name}.{key}, {err}."
                            )

                    arguments[to_camel_case(key)] = GraphQLInputField(
                        type_=input_arg_type,
                        default_value=default_value
                    )
                return arguments

            return fields

        def local_container_type():
            local_creator = creator

            def container_type(data):
                data = {
                    to_snake_case(key): value
                    for key, value in data.items()
                }
                return local_creator(**data)

            return container_type

        return GraphQLInputObjectType(
            name,
            fields=local_fields(),
            out_type=local_container_type(),
            description=description
        )

    def map_to_object(self, class_type: Type) -> GraphQLType:
        name = f"{class_type.__name__}{self.suffix}"
        description = inspect.getdoc(class_type)

        class_funcs = get_class_funcs(class_type, self.schema, self.as_mutable)

        for key, func in class_funcs:
            func_meta = get_value(func, self.schema, 'meta')
            func_meta['type'] = get_value(func, self.schema, 'type')

            self.meta[(name, to_snake_case(key))] = func_meta

        def local_interfaces():
            local_class_type = class_type
            local_self = self

            def interfaces():
                _interfaces = []
                superclasses = inspect.getmro(local_class_type)[1:]

                for superclass in superclasses:
                    if is_interface(superclass, local_self.schema):
                        _interfaces.append(local_self.map(superclass))

                return _interfaces

            return interfaces

        def local_fields():
            local_self = self
            local_class_funcs = class_funcs
            local_class_type = class_type
            local_name = name

            def fields():
                fields_ = {}

                for key_, func_ in local_class_funcs:
                    local_class_type_name = local_class_type.__name__
                    func_.__globals__[local_class_type_name] = local_class_type
                    fields_[to_camel_case(key_)] = local_self.map_to_field(
                        func_,
                        local_name,
                        key_
                    )

                return fields_

            return fields

        obj = GraphQLObjectType(
            name,
            local_fields(),
            local_interfaces(),
            description=description
        )

        return obj

    def rmap(self, graphql_type: GraphQLType) -> Type:
        while hasattr(graphql_type, 'of_type'):
            graphql_type = graphql_type.of_type

        return self.reverse_registry.get(graphql_type)

    def map(self, type_, use_graphql_type=True) -> GraphQLType:

        def _map(type__) -> GraphQLType:

            if type_ == JsonType:
                return GraphQLJSON

            if use_graphql_type and inspect.isclass(type__):
                if issubclass(type__, GraphQLTypeWrapper):
                    return type__.graphql_type(mapper=self)

                if type_is_dataclass(type__):
                    return type_from_dataclass(type__, mapper=self)

            if typing_inspect.is_union_type(type__):
                return self.map_to_union(type__)

            origin_type = get_origin(type__)

            if inspect.isclass(origin_type) and \
                    issubclass(get_origin(type__), (List, Set)):
                return self.map_to_list(type__)

            if inspect.isclass(type__):
                if issubclass(type__, GraphQLType):
                    return type__()

                if issubclass(type__, tuple(self.scalar_classes())):
                    return self.map_to_scalar(type__)

                if issubclass(type__, enum.Enum):
                    return self.map_to_enum(type__)

                if is_interface(type__, self.schema):
                    return self.map_to_interface(type__)

                if self.as_input:
                    return self.map_to_input(type__)
                else:
                    return self.map_to_object(type__)

            if isinstance(type__, GraphQLType):
                return type__

        key_hash = abs(hash(str(type_))) % (10 ** 8)
        suffix = {'|' + self.suffix if self.suffix else ''}
        generic_key = f"Registry({key_hash})" \
                      f"{suffix}|{self.as_input}|{self.as_mutable}"

        generic_registry_value = self.registry.get(generic_key, None)

        if generic_registry_value:
            return generic_registry_value

        value: GraphQLType = _map(type_)
        key = str(value)

        registry_value = self.registry.get(key, None)

        if not registry_value:
            self.register(python_type=type_, key=key, value=value)
            self.register(python_type=type_, key=generic_key, value=value)
            return value

        return registry_value

    def register(self, python_type: Type, key: str, value: GraphQLType):
        if self.validate(value):
            self.registry[key] = value
            self.reverse_registry[value] = python_type

    def validate(self, type_: GraphQLType, evaluate=False) -> bool:
        if not type_:
            return False

        if not isinstance(type_, GraphQLType):
            return False

        if isinstance(type_, GraphQLNonNull):
            type_ = type_.of_type

        if self.as_input and not is_input_type(type_):
            return False

        if isinstance(type_, GraphQLObjectType):
            if evaluate:
                try:
                    if len(type_.fields) == 0:
                        return False
                except AssertionError:
                    return False

            elif not callable(type_._fields) and len(type_._fields) == 0:
                return False

        return True


def get_class_funcs(
    class_type,
    schema,
    mutable=False
) -> List[Tuple[Any, Any]]:
    members = [(key, member) for key, member in inspect.getmembers(class_type)]

    if hasattr(class_type, 'graphql_fields'):
        members += [
            (func.__name__, func)
            for func in class_type.graphql_fields()
        ]
    func_members = []

    for key, member in members:
        if isinstance(member, property):
            getter = member.fget
            if getter:
                func_members.append((key, getter))
            setter = member.fset

            if setter:
                func_members.append((key, setter))
        else:
            func_members.append((key, member))

    def matches_criterion(func):
        func_type = get_value(func, schema, 'type')
        return func_type == "query" or (mutable and func_type == "mutation")

    callable_funcs = []

    for key, member in func_members:
        if is_graphql(member, schema=schema) and matches_criterion(member):
            if not callable(member):
                type_hints = typing.get_type_hints(member)
                return_type = type_hints.pop('return', None)

                def local_func():
                    local_key = key
                    local_member = member

                    def func(self) -> return_type:
                        return getattr(self, local_key)

                    func.graphql = local_member.graphql
                    func.defined_on = local_member.defined_on
                    func.schemas = {
                        schema: {
                            "meta": local_member.meta,
                            "type": local_member.type,
                            "defined_on": local_member.defined_on,
                            "schema": schema
                        }
                    }

                    return func

                func = local_func()

            else:
                func = member

            callable_funcs.append((key, func))

    return callable_funcs


def get_value(type_, schema, key):
    if is_graphql(type_, schema):
        return type_.schemas.get(schema, type_.schemas.get(None)).get(key)


def is_graphql(type_, schema):
    graphql = getattr(type_, 'graphql', None)
    schemas = getattr(type_, 'schemas', {})

    valid_schema = schema in schemas.keys() or None in schemas.keys()

    return graphql and schemas and valid_schema


def is_interface(type_, schema):
    if is_graphql(type_, schema):
        type_type = get_value(type_, schema, 'type')
        type_defined_on = get_value(type_, schema, 'defined_on')

        return type_type == "interface" and type_defined_on == type_


def is_abstract(type_, schema):
    if is_graphql(type_, schema):
        type_type = get_value(type_, schema, 'type')
        type_defined_on = get_value(type_, schema, 'defined_on')

        return type_type == "abstract" and type_defined_on == type_


def is_scalar(type_):
    for test_types, graphql_type in GraphQLTypeMapper.scalar_map:
        for test_type in test_types:
            if issubclass(type_, test_type):
                return True
    return False

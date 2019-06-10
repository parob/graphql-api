import enum
import inspect
import collections

import typing
import types
import typing_inspect

from collections import OrderedDict
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
    GraphQLFloat)

from graphql.type.definition import (
    GraphQLType,
    GraphQLUnionType,
    GraphQLInterfaceType,
    GraphQLArgument,
    GraphQLInputObjectType,
    is_input_type,
    GraphQLInputObjectField,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLScalarType,
    GraphQLNonNull
)

from objectql.context import ObjectQLContext
from objectql.types import \
    GraphQLBytes, \
    GraphQLUUID, \
    GraphQLDateTime, \
    GraphQLJSON
from objectql.utils import to_camel_case, to_snake_case, to_input_value
from objectql.exception import ObjectQLBaseException
from objectql.dataclass_mapping import type_is_dataclass, type_from_dataclass

"""
class AnyObject:


    @classmethod
    def graphql_from_input(cls, age: int):
        pass

    # @classmethod
    # def graphql_fields(cls):
    #     pass

"""


class ObjectQLTypeMapInvalid(ObjectQLBaseException):
    pass


class ObjectQLTypeMapError(ObjectQLBaseException):
    pass


class ObjectQLTypeWrapper:

    @classmethod
    def graphql_type(cls, mapper: "ObjectQLTypeMapper") -> GraphQLType:
        pass


class ObjectQLMetaKey(enum.Enum):
    resolve_to_mutable = "RESOLVE_TO_MUTABLE"
    resolve_to_self = "RESOLVE_TO_SELF"
    native_middleware = "NATIVE_MIDDLEWARE"


class ObjectQLMutableField(GraphQLField):
    pass


class ObjectQLTypeMapper:

    def __init__(
        self,
        as_mutable=False,
        as_input=False,
        registry=None,
        reverse_registry=None,
        suffix=""
    ):
        self.as_mutable = as_mutable
        self.as_input = as_input
        self.registry = registry or {}
        self.reverse_registry = reverse_registry or {}
        self.suffix = suffix
        self.meta = {}
        self.input_type_mapper = None

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
            raise ObjectQLTypeMapInvalid(
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
            raise ObjectQLTypeMapError(
                f"Field '{name}.{key}' with function '{function_type}' return "
                f"type '{return_type}' could not be mapped to a valid GraphQL "
                f"type, was mapped to invalid type {return_graphql_type}."
            )

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

        input_type_mapper = ObjectQLTypeMapper(
            as_mutable=self.as_mutable,
            as_input=True,
            registry=self.registry,
            reverse_registry=self.reverse_registry,
            suffix=self.suffix
        )
        self.input_type_mapper = input_type_mapper
        arguments = {}

        include_context = False

        for key, hint in type_hints.items():
            if key == 'context' and issubclass(hint, ObjectQLContext):
                include_context = True
                continue

            arg_type = input_type_mapper.map(hint)

            nullable = key in default_args
            if not nullable:
                arg_type = GraphQLNonNull(arg_type)

            arguments[to_camel_case(key)] = GraphQLArgument(
                type=arg_type,
                default_value=default_args.get(key, None)
            )

        def resolve(self, info=None, context=None, *args, **kwargs):
            _args = {to_snake_case(key): arg for key, arg in kwargs.items()}

            if include_context:
                _args['context'] = info.context

            function_name = function_type.__name__
            parent_type = self.__class__
            class_attribute = getattr(parent_type, function_name, None)
            is_property = isinstance(class_attribute, property)

            if is_property:
                if _args:
                    if len(_args) > 1:
                        raise KeyError(
                            f"{function_name} on type {parent_type} is a"
                            f" property, and cannot have multiple arguments."
                        )
                    return function_type(self, **_args)

                return getattr(self, function_name, None)

            function_type_override = getattr(self, function_name, None)

            if function_type_override is not None:
                return function_type_override(**_args)

            return function_type(self, **_args)

        field_class = GraphQLField
        if function_type.type == "mutation":
            field_class = ObjectQLMutableField

        return field_class(return_graphql_type,
                           arguments,
                           resolve,
                           description=description)

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

        def resolve_type(value, info):
            from objectql.remote import ObjectQLRemoteObject

            value_type = type(value)

            if isinstance(value, ObjectQLRemoteObject):
                value_type = value.python_type

            for arg, mapped_type in union_map.items():
                if issubclass(value_type, arg):
                    return mapped_type

        names = [arg.__name__ for arg in union_args]
        name = f"{''.join(names)}{self.suffix}Union"

        return GraphQLUnionType(
            name,
            types=[*union_map.values()],
            resolve_type=resolve_type
        )

    def map_to_list(self, type: List) -> GraphQLList:
        list_subtype = typing_inspect.get_args(type)[0]

        list_type = GraphQLList(type=self.map(list_subtype))

        return list_type

    def map_to_enum(self, type: enum.Enum) -> GraphQLEnumType:
        enum_type = type
        name = f"{type.__name__}Enum"
        # Enums dont include a suffix as they are immutable

        description = inspect.getdoc(enum_type)

        values = OrderedDict([
            (name, GraphQLEnumValue(value))
            for name, value in enum_type.__members__.items()
        ])

        enum_type = GraphQLEnumType(name=name,
                                    values=values,
                                    description=description)

        def serialize(self, value):
            if isinstance(value, collections.Hashable):
                enum_value = self._value_lookup.get(value)
            if enum_value:
                return enum_value.name

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
            if not is_abstract(subclass):
                self.map(subclass)

        class_funcs = get_class_funcs(class_type, self.as_mutable)

        interface_name = f"{name}{self.suffix}Interface"
        description = inspect.getdoc(class_type)

        def local_resolve_type():
            local_self = self

            def resolve_type(value, info):
                return local_self.map(type(value))
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

        return GraphQLInterfaceType(interface_name,
                                    fields=local_fields(),
                                    resolve_type=local_resolve_type(),
                                    description=description)

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
                f"Unable to map input type '{name}' for '{class_type}', "
                f"check the '{class_type}.__init__' method or the "
                f"'{class_type}.graphql_from_input' method. "
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

                    arguments[to_camel_case(key)] = GraphQLInputObjectField(
                        type=input_arg_type,
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
            container_type=local_container_type(),
            description=description
        )

    def map_to_object(self, class_type: Type) -> GraphQLType:
        name = f"{class_type.__name__}{self.suffix}"
        description = inspect.getdoc(class_type)

        class_funcs = get_class_funcs(class_type, self.as_mutable)

        for key, func in class_funcs:
            func_meta = getattr(func, 'meta', {})
            func_meta['type'] = getattr(func, 'type')

            self.meta[(name, to_snake_case(key))] = func_meta

        def local_interfaces():
            local_class_type = class_type
            local_self = self

            def interfaces():
                _interfaces = []
                superclasses = inspect.getmro(local_class_type)[1:]

                for superclass in superclasses:
                    if is_interface(superclass):
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

    def map(self, type, use_graphql_type=True) -> GraphQLType:

        def _map(type_) -> GraphQLType:

            if use_graphql_type and inspect.isclass(type_):
                if issubclass(type_, ObjectQLTypeWrapper):
                    return type_.graphql_type(mapper=self)

                if type_is_dataclass(type_):
                    return type_from_dataclass(type_, mapper=self)

            if typing_inspect.is_union_type(type_):
                return self.map_to_union(type_)

            origin_type = get_origin(type_)

            if inspect.isclass(origin_type) and \
                    issubclass(get_origin(type_), (List, Set)):
                return self.map_to_list(type_)

            if inspect.isclass(type_):
                if issubclass(type_, GraphQLType):
                    return type_()

                if issubclass(type_, tuple(self.scalar_classes())):
                    return self.map_to_scalar(type_)

                if issubclass(type_, enum.Enum):
                    return self.map_to_enum(type_)

                if is_interface(type_):
                    return self.map_to_interface(type_)

                if self.as_input:
                    return self.map_to_input(type_)
                else:
                    return self.map_to_object(type_)

            if isinstance(type_, GraphQLType):
                return type_

        key_hash = abs(hash(str(type))) % (10 ** 8)
        suffix = {'|' + self.suffix if self.suffix else ''}
        generic_key = f"Registry({key_hash})" \
                      f"{suffix}|{self.as_input}|{self.as_mutable}"

        generic_registry_value = self.registry.get(generic_key, None)

        if generic_registry_value:
            return generic_registry_value

        value: GraphQLType = _map(type)
        key = str(value)

        registry_value = self.registry.get(key, None)

        if not registry_value:
            self.register(python_type=type, key=key, value=value)
            self.register(python_type=type, key=generic_key, value=value)
            return value

        return registry_value

    def register(self, python_type: Type, key: str, value: GraphQLType):
        if self.validate(value):
            self.registry[key] = value
            self.reverse_registry[value] = python_type

    def validate(self, type: GraphQLType, evaluate=False) -> bool:
        if not type:
            return False

        if not isinstance(type, GraphQLType):
            return False

        if isinstance(type, GraphQLNonNull):
            type = type.of_type

        if self.as_input and not is_input_type(type):
            return False

        if isinstance(type, GraphQLObjectType):
            if evaluate:
                try:
                    if len(type.fields) == 0:
                        return False
                except AssertionError:
                    return False

            elif not callable(type._fields) and len(type._fields) == 0:
                return False

        return True


def get_class_funcs(class_type, mutable=False) -> List[Tuple[Any, Any]]:
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
        return func.type == "query" or (mutable and func.type == "mutation")

    callable_funcs = []

    for key, member in func_members:
        if is_graphql(member) and matches_criterion(member):
            if not callable(member):
                type_hints = typing.get_type_hints(member)
                return_type = type_hints.pop('return', None)

                def local_func():
                    local_key = key
                    local_member = member

                    def func(self) -> return_type:
                        return getattr(self, local_key)

                    func.graphql = local_member.graphql
                    func.meta = local_member.meta
                    func.type = local_member.type
                    func.defined_on = local_member.defined_on

                    return func

                func = local_func()

            else:
                func = member

            callable_funcs.append((key, func))

    return callable_funcs


def is_graphql(type):
    return hasattr(type, 'graphql') and \
           hasattr(type, 'meta') and \
           hasattr(type, 'type') and \
           hasattr(type, 'defined_on')


def is_interface(type):
    if is_graphql(type):
        return type.graphql and \
               type.type == "interface" and \
               type.defined_on == type


def is_abstract(type):
    if is_graphql(type):
        return type.graphql and \
               type.type == "abstract" and \
               type.defined_on == type


def is_scalar(type):
    for test_types, graphql_type in ObjectQLTypeMapper.scalar_map:
        for test_type in test_types:
            if issubclass(type, test_type):
                return True
    return False

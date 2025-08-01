import collections.abc
import enum
import inspect
import types
import typing
from datetime import date, datetime
from typing import Any, Callable, List, Optional, Set, Tuple, Type, Union, cast
from uuid import UUID
from abc import abstractmethod

import typing_inspect
from graphql import (
    DirectiveLocation,
    GraphQLBoolean,
    GraphQLField,
    GraphQLFloat,
    GraphQLInt,
    GraphQLList,
    GraphQLObjectType,
    GraphQLString,
    is_union_type,
    GraphQLWrappingType,
)
from graphql.pyutils import Undefined, UndefinedType
from graphql.type.definition import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInterfaceType,
    GraphQLNonNull,
    GraphQLScalarType,
    GraphQLType,
    GraphQLUnionType,
    is_abstract_type,
    is_enum_type,
    is_input_type,
    is_interface_type,
    is_object_type,
    is_scalar_type,
    is_nullable_type,
)
from typing_inspect import get_origin

from graphql_api.context import GraphQLContext
from graphql_api.dataclass_mapping import type_from_dataclass, type_is_dataclass
from graphql_api.exception import GraphQLBaseException
from graphql_api.pydantic import type_from_pydantic_model, type_is_pydantic_model
from graphql_api.schema import add_applied_directives, get_applied_directives
from graphql_api.types import (
    GraphQLBytes,
    GraphQLDate,
    GraphQLDateTime,
    GraphQLJSON,
    GraphQLMappedEnumType,
    GraphQLUUID,
    JsonType,
)
from graphql_api.utils import (
    has_single_type_union_return,
    to_camel_case,
    to_camel_case_text,
    to_input_value,
    to_snake_case,
)

"""
class AnyObject:


    @classmethod
    def graphql_from_input(cls, age: int):
        pass

    # @classmethod
    # def graphql_fields(cls):
    #     pass

"""


class UnionFlagType:
    pass


class GraphQLTypeMapInvalid(GraphQLBaseException):
    pass


class GraphQLTypeMapError(GraphQLBaseException):
    pass


class GraphQLTypeWrapper:
    @classmethod
    @abstractmethod
    def graphql_type(cls, mapper: "GraphQLTypeMapper") -> GraphQLType:
        ...


class GraphQLMetaKey(enum.Enum):
    resolve_to_mutable = "RESOLVE_TO_MUTABLE"
    resolve_to_self = "RESOLVE_TO_SELF"
    native_middleware = "NATIVE_MIDDLEWARE"
    error_protection = "ERROR_PROTECTION"


class GraphQLMutableField(GraphQLField):
    pass


class GraphQLGenericEnum(enum.Enum):
    pass


class GraphQLTypeMapper:
    def __init__(
        self,
        as_mutable=False,
        as_input=False,
        registry=None,
        reverse_registry=None,
        suffix="",
        schema=None,
    ):
        self.as_mutable = as_mutable
        self.as_input = as_input
        self.registry = registry or {}
        self.reverse_registry = reverse_registry or {}
        self.suffix = suffix
        self.meta = {}
        self.input_type_mapper = None
        self.schema = schema
        self.applied_schema_directives = []

    def types(self) -> Set[GraphQLType]:
        return set(self.registry.values())

    def map_to_field(self, function_type: Callable, name="", key="") -> GraphQLField:
        type_hints = typing.get_type_hints(function_type)
        description = to_camel_case_text(inspect.getdoc(function_type))

        return_type = type_hints.pop("return", None)

        # This is a bit nasty - looking up the function source code to determine this
        if has_single_type_union_return(function_type):
            return_type = Union[return_type, UnionFlagType]

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
                f"Field '{name}.{key}' with function ({function_type}) did "
                f"not specify a valid return type."
            )

        assert return_graphql_type is not None

        if not isinstance(
            return_graphql_type,
            (
                GraphQLScalarType,
                GraphQLObjectType,
                GraphQLInterfaceType,
                GraphQLUnionType,
                GraphQLEnumType,
                GraphQLList,
                GraphQLNonNull,
            ),
        ):
            raise GraphQLTypeMapError(
                f"Field '{name}.{key}' with function '{function_type}' return "
                f"type '{return_type}' could not be mapped to a valid GraphQL "
                f"output type, was mapped to {return_graphql_type}."
            )

        enum_return = None

        if isinstance(return_graphql_type, GraphQLEnumType):
            enum_return = return_type

        if not nullable and not isinstance(return_graphql_type, GraphQLNonNull):
            if is_nullable_type(return_graphql_type):
                return_graphql_type = GraphQLNonNull(return_graphql_type)

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
            schema=self.schema,
        )
        self.input_type_mapper = input_type_mapper
        arguments = {}
        enum_arguments = {}

        include_context = False

        for _key, hint in type_hints.items():
            if (
                _key == "context"
                and inspect.isclass(hint)
                and issubclass(hint, GraphQLContext)
            ):
                include_context = True
                continue

            arg_type = input_type_mapper.map(hint)

            if arg_type is None:
                raise GraphQLTypeMapError(f"Unable to map argument {name}.{key}.{_key}")

            if isinstance(arg_type, GraphQLEnumType):
                enum_arguments[_key] = hint

            nullable = _key in default_args
            if not nullable:
                arg_type = GraphQLNonNull(arg_type)  # type: ignore

            arguments[to_camel_case(_key)] = GraphQLArgument(
                type_=arg_type, default_value=default_args.get(_key, Undefined)  # type: ignore
            )

        # noinspection PyUnusedLocal
        def resolve(_self, info=None, context=None, *args, **kwargs):
            _args = {to_snake_case(_key): arg for _key, arg in kwargs.items()}

            if include_context and info:
                _args["context"] = info.context

            function_name = function_type.__name__
            parent_type = _self.__class__
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
                        response = function_type(_self, **_args)
                else:
                    response = getattr(_self, function_name, None)
            else:
                function_type_override = getattr(_self, function_name, None)

                if function_type_override is not None:
                    response = function_type_override(**_args)
                else:
                    response = function_type(_self, **_args)

            if enum_return:
                if isinstance(response, enum.Enum):
                    response = response.value

            return response

        field_class = GraphQLField
        func_type = get_value(function_type, self.schema, "graphql_type")
        if func_type == "mutable_field":
            field_class = GraphQLMutableField

        field = field_class(
            return_graphql_type, arguments, resolve, description=description
        )

        self.add_applied_directives(field, f"{name}.{key}", function_type)
        return field

    def map_to_union(self, union_type: Any) -> GraphQLType:
        union_args = typing_inspect.get_args(union_type, evaluate=True)
        union_args = [arg for arg in union_args if arg != UnionFlagType]
        none_type = type(None)
        union_map = {
            arg: self.map(arg) for arg in union_args if arg and arg != none_type
        }

        if len(union_map) == 1 and none_type in union_args:
            _, mapped_type = union_map.popitem()
            if mapped_type:
                return mapped_type

        # noinspection PyUnusedLocal
        def resolve_type(value, info, _type):
            from graphql_api.remote import GraphQLRemoteObject

            value_type = type(value)

            if isinstance(value, GraphQLRemoteObject):
                value_type = value.python_type

            for arg, _mapped_type in union_map.items():
                if (
                    inspect.isclass(arg)
                    and is_object_type(_mapped_type)
                    and issubclass(cast(type, value_type), arg)
                ):
                    return cast(GraphQLObjectType, _mapped_type).name

        names = [
            arg.__name__
            for arg in union_args
            if inspect.isclass(arg) and arg.__name__ != "NoneType"
        ]
        name = f"{''.join(names)}{self.suffix}Union"

        union = GraphQLUnionType(
            name,
            types=[
                cast(GraphQLObjectType, v)
                for v in union_map.values()
                if v and is_object_type(v)
            ],
            resolve_type=resolve_type,
        )
        self.add_applied_directives(union, name, union_type)

        return union

    def map_to_list(self, type_: List) -> GraphQLList:
        list_subtype = typing_inspect.get_args(type_)[0]

        origin = typing.get_origin(list_subtype)
        args = typing.get_args(list_subtype)
        nullable = False
        if origin == Union and type(None) in args:
            args = tuple(a for a in args if not isinstance(a, type(None)))
            if len(args) == 1:
                list_subtype = args[0]
            nullable = True

        subtype = self.map(list_subtype)

        if subtype is None:
            raise GraphQLTypeMapError(f"Unable to map list subtype {list_subtype}")

        if not nullable:
            GRAPHQL_NULLABLE_TYPES = (
                GraphQLScalarType,
                GraphQLObjectType,
                GraphQLInterfaceType,
                GraphQLUnionType,
                GraphQLEnumType,
                GraphQLList,
                GraphQLInputObjectType,
            )
            if isinstance(subtype, GRAPHQL_NULLABLE_TYPES):
                subtype = GraphQLNonNull(subtype)

        return GraphQLList(type_=subtype)

    def map_to_literal(self, type__) -> GraphQLType:
        literal_args = typing_inspect.get_args(type__, evaluate=True)
        _type = type(literal_args[0])
        if not all(isinstance(x, _type) for x in literal_args):
            raise TypeError("Literals must all be of the same type")

        mapped_type = self.map(_type)
        if mapped_type is None:
            raise GraphQLTypeMapError(f"Unable to map literal type {_type}")
        return mapped_type

    # noinspection PyMethodMayBeStatic
    def map_to_enum(self, type_: Type[enum.Enum]) -> GraphQLEnumType:
        enum_type = type_
        name = f"{type_.__name__}Enum"

        # Enums don't include a suffix as they are immutable
        description = to_camel_case_text(inspect.getdoc(type_))
        default_description = to_camel_case_text(inspect.getdoc(GraphQLGenericEnum))

        if not description or description == default_description:
            description = f"A {name}."

        enum_type = GraphQLMappedEnumType(
            name=name, values=enum_type, description=description
        )

        enum_type.enum_type = type_

        def serialize(_self, value) -> Union[str, None, UndefinedType]:
            if value and isinstance(value, collections.abc.Hashable):
                if isinstance(value, enum.Enum):
                    value = value.value

                # noinspection PyProtectedMember
                lookup_value = _self._value_lookup.get(value)
                if lookup_value:
                    return lookup_value
                else:
                    return Undefined

            return None

        enum_type.serialize = types.MethodType(serialize, enum_type)

        self.add_applied_directives(enum_type, name, type_)

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
        ([date], GraphQLDate),
        ([type(None)], None),
    ]

    def scalar_classes(self):
        classes = []
        for scalar_class_map in self.scalar_map:
            for scalar_class in scalar_class_map[0]:
                classes.append(scalar_class)
        return classes

    def map_to_scalar(self, class_type: Type) -> GraphQLScalarType:
        name = class_type.__name__
        for test_types, graphql_type in self.scalar_map:
            for test_type in test_types:
                if issubclass(class_type, test_type):
                    self.add_applied_directives(graphql_type, name, class_type)
                    return graphql_type
        raise GraphQLTypeMapError(f"Could not map scalar {class_type}")

    def map_to_interface(
        self,
        class_type: Type,
    ) -> GraphQLType:
        subclasses = class_type.__subclasses__()
        name = class_type.__name__

        for subclass in subclasses:
            if not is_abstract(subclass, self.schema):
                self.map(subclass)

        class_funcs = get_class_funcs(class_type, self.schema, self.as_mutable)

        interface_name = f"{name}{self.suffix}Interface"
        description = to_camel_case_text(inspect.getdoc(class_type))

        def local_resolve_type():
            local_self = self

            # noinspection PyUnusedLocal
            def resolve_type(value, info, _type):
                value = local_self.map(type(value))
                if is_object_type(value):
                    value = cast(GraphQLObjectType, value)
                    return value.name

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
                        func_, local_name, key_
                    )

                return fields_

            return fields

        interface = GraphQLInterfaceType(
            interface_name,
            fields=local_fields(),
            resolve_type=local_resolve_type(),
            description=description,
        )

        self.add_applied_directives(interface, interface_name, class_type)
        return interface

    def map_to_input(self, class_type: Type) -> GraphQLType:
        name = f"{class_type.__name__}{self.suffix}Input"

        if hasattr(class_type, "graphql_from_input"):
            creator = class_type.graphql_from_input
            func = creator

        else:
            creator = class_type
            # noinspection PyTypeChecker
            func = class_type.__init__

        description = to_camel_case_text(
            inspect.getdoc(func) or inspect.getdoc(class_type)
        )

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

                    if input_arg_type is None:
                        raise GraphQLTypeMapError(
                            f"Unable to map input argument {local_name}.{key}"
                        )

                    nullable = key in local_default_args
                    if not nullable:
                        # noinspection PyTypeChecker
                        input_arg_type = GraphQLNonNull(input_arg_type)  # type: ignore

                    default_value = local_default_args.get(key, None)

                    if default_value is not None:
                        try:
                            default_value = to_input_value(default_value)
                        except ValueError as _err:
                            raise ValueError(
                                f"Unable to map {local_name}.{key}, {_err}."
                            )

                    arguments[to_camel_case(key)] = GraphQLInputField(
                        type_=input_arg_type, default_value=default_value  # type: ignore
                    )
                return arguments

            return fields

        def local_container_type():
            local_creator = creator

            def container_type(data):
                data = {to_snake_case(key): value for key, value in data.items()}
                return local_creator(**data)

            return container_type

        input_object = GraphQLInputObjectType(
            name,
            fields=local_fields(),
            out_type=local_container_type(),
            description=description,
        )

        self.add_applied_directives(input_object, name, class_type)

        return input_object

    def add_applied_directives(
        self, graphql_type: GraphQLType | GraphQLField, key: str, value
    ):
        applied_directives = get_applied_directives(value)
        if applied_directives:
            self.applied_schema_directives.append(
                (key, graphql_type, applied_directives)
            )
            add_applied_directives(graphql_type, applied_directives)
            location: Optional[DirectiveLocation] = None
            type_str: Optional[str] = None
            if is_object_type(graphql_type):
                location = DirectiveLocation.OBJECT
                type_str = "Object"
            elif is_interface_type(graphql_type):
                location = DirectiveLocation.INTERFACE
                type_str = "Interface"
            elif is_enum_type(graphql_type):
                location = DirectiveLocation.ENUM
                type_str = "Enum"
            elif is_input_type(graphql_type):
                location = DirectiveLocation.INPUT_OBJECT
                type_str = "Input Object"
            elif is_union_type(graphql_type):
                location = DirectiveLocation.UNION
                type_str = "Union"
            elif is_scalar_type(graphql_type):
                location = DirectiveLocation.SCALAR
                type_str = "Scalar"
            elif is_abstract_type(graphql_type):
                type_str = "Abstract"
                # unsupported
                raise TypeError("Abstract types do not currently support directives")
            elif isinstance(graphql_type, GraphQLField):
                location = DirectiveLocation.FIELD_DEFINITION
                type_str = "Field"

            for applied_directive in applied_directives:
                from graphql_api import AppliedDirective

                applied_directive: AppliedDirective

                if location not in applied_directive.directive.locations:
                    raise TypeError(
                        f"Directive '{applied_directive.directive}' only supports "
                        f"{applied_directive.directive.locations} locations but was"
                        f" used on '{key}' which is a '{type_str}' and does not "
                        f"support {location} types, "
                    )

    def map_to_object(self, class_type: Type) -> GraphQLType:
        name = f"{class_type.__name__}{self.suffix}"
        description = to_camel_case_text(inspect.getdoc(class_type))

        class_funcs = get_class_funcs(class_type, self.schema, self.as_mutable)

        for key, func in class_funcs:
            func_meta = get_value(func, self.schema, "meta")
            func_meta["graphql_type"] = get_value(func, self.schema, "graphql_type")  # type: ignore

            self.meta[(name, to_snake_case(key))] = func_meta

        def local_interfaces():
            local_class_type = class_type
            local_self = self

            def interfaces():
                _interfaces = []
                superclasses = inspect.getmro(local_class_type)[1:]

                for superclass in superclasses:
                    if is_interface(superclass, local_self.schema):
                        value = local_self.map(superclass)
                        if isinstance(value, GraphQLInterfaceType):
                            interface: GraphQLInterfaceType = value
                            _interfaces.append(interface)

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
                    _field = local_self.map_to_field(func_, local_name, key_)

                    fields_[to_camel_case(key_)] = _field

                return fields_

            return fields

        obj = GraphQLObjectType(
            name,
            local_fields(),
            local_interfaces(),
            description=description,
            extensions={},
        )

        self.add_applied_directives(obj, name, class_type)
        return obj

    def rmap(self, graphql_type: GraphQLType) -> Optional[Type]:
        while isinstance(graphql_type, GraphQLWrappingType):
            graphql_type = graphql_type.of_type

        return self.reverse_registry.get(graphql_type)

    def map(self, type_, use_graphql_type=True) -> GraphQLType | None:
        def _map(type__) -> GraphQLType | None:
            if type_ == JsonType:
                return GraphQLJSON

            if use_graphql_type and inspect.isclass(type__):
                if issubclass(type__, GraphQLTypeWrapper):
                    return type__.graphql_type(mapper=self)

                if type_is_pydantic_model(type__):
                    return type_from_pydantic_model(type__, mapper=self)

                if type_is_dataclass(type__):
                    return type_from_dataclass(type__, mapper=self)

            if typing_inspect.is_union_type(type__):
                return self.map_to_union(type__)

            if typing_inspect.is_literal_type(type__):
                return self.map_to_literal(type__)

            origin_type = get_origin(type__)

            if origin_type is list or origin_type is set:
                return self.map_to_list(cast(List, type__))

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

        key_hash = abs(hash(str(type_))) % (10**8)
        suffix = {"|" + self.suffix if self.suffix else ""}
        generic_key = (
            f"Registry({key_hash})" f"{suffix}|{self.as_input}|{self.as_mutable}"
        )

        generic_registry_value = self.registry.get(generic_key, None)

        if generic_registry_value:
            return generic_registry_value

        value = _map(type_)
        if not value:
            return None
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

    def validate(self, type_: Optional[GraphQLType], evaluate=False) -> bool:
        if not type_:
            return False

        if not isinstance(type_, GraphQLType):
            return False

        if isinstance(type_, GraphQLNonNull):
            type_ = type_.of_type

        if self.as_input and not is_input_type(type_):
            return False

        if isinstance(type_, GraphQLObjectType):
            # noinspection PyProtectedMember
            if evaluate:
                try:
                    if len(type_.fields) == 0:
                        return False
                except AssertionError:
                    return False

            elif not callable(type_._fields) and len(type_._fields) == 0:
                return False

        return True


def get_class_funcs(class_type, schema, mutable=False) -> List[Tuple[Any, Any]]:
    members = []
    try:
        class_types = class_type.mro()
    except TypeError as e:
        if "unbound method" in str(e):
            raise ImportError(
                str(e) + ". This could be because type decorator is not correctly being"
                " imported from the graphql_api package."
            )
        else:
            raise e

    for _class_type in class_types:
        for key, member in inspect.getmembers(_class_type):
            if not (key.startswith("__") and key.endswith("__")):
                members.append((key, member))

    if hasattr(class_type, "graphql_fields"):
        members += [(func.__name__, func) for func in class_type.graphql_fields()]
    func_members = []

    for key, member in reversed(members):
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
        func_type = get_value(func, schema, "graphql_type")
        return func_type == "field" or (mutable and func_type == "mutable_field")

    callable_funcs = []

    inherited_fields = {}
    for key, member in func_members:
        if getattr(member, "_graphql", None) and key != "test_property":
            inherited_fields[key] = {**member.__dict__}
        elif key in inherited_fields:
            member.__dict__ = {**inherited_fields[key], "defined_on": member}

    done = []

    for key, member in reversed(func_members):
        if is_graphql(member, schema=schema) and matches_criterion(member):
            if not callable(member):
                type_hints = typing.get_type_hints(member)
                return_type = type_hints.pop("return", None)

                # noinspection PyProtectedMember
                def local_func():
                    local_key = key
                    local_member = member

                    def func(self) -> return_type:  # type: ignore
                        return getattr(self, local_key)

                    func._graphql = local_member._graphql
                    func._defined_on = local_member._defined_on
                    func._schemas = {
                        schema: {
                            "meta": local_member._meta,
                            "graphql_type": local_member._graphql_type,
                            "defined_on": local_member._defined_on,
                            "schema": schema,
                        }
                    }

                    return func

                func = local_func()

            else:
                func = member

            if key not in done:
                done.append(key)
                callable_funcs.append((key, func))

    return callable_funcs


def get_value(type_, schema, key):
    if is_graphql(type_, schema):
        # noinspection PyProtectedMember
        return type_._schemas.get(schema, type_._schemas.get(None)).get(key)


def is_graphql(type_, schema):
    graphql = getattr(type_, "_graphql", None)
    schemas = getattr(type_, "_schemas", {})
    # noinspection PyBroadException
    try:
        valid_schema = schema in schemas.keys() or None in schemas.keys()
    except Exception:
        valid_schema = False
    return graphql and schemas and valid_schema


def is_interface(type_, schema):
    if is_graphql(type_, schema):
        type_type = get_value(type_, schema, "graphql_type")
        type_defined_on = get_value(type_, schema, "defined_on")
        return type_type == "interface" and type_defined_on == type_


def is_abstract(type_, schema):
    if is_graphql(type_, schema):
        type_type = get_value(type_, schema, "graphql_type")
        type_defined_on = get_value(type_, schema, "defined_on")
        return type_type == "abstract" and type_defined_on == type_


def is_scalar(type_):
    for test_types, graphql_type in GraphQLTypeMapper.scalar_map:
        for test_type in test_types:
            if issubclass(type_, test_type):
                return True
    return False

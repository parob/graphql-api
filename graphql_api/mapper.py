import collections.abc
import enum
import inspect
import types
import typing
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union, cast
from uuid import UUID

import typing_inspect
from graphql import (DirectiveLocation, GraphQLBoolean, GraphQLField,
                     GraphQLFloat, GraphQLInt, GraphQLList, GraphQLObjectType,
                     GraphQLString, is_union_type)
from graphql.pyutils import Undefined, UndefinedType
from graphql.type.definition import (GraphQLArgument, GraphQLEnumType,
                                     GraphQLInputField, GraphQLInputObjectType, GraphQLInputType, # GraphQLInputObjectField removed
                                     GraphQLInterfaceType, GraphQLNonNull,
                                     GraphQLScalarType, GraphQLType,
                                     GraphQLUnionType,
                                     is_enum_type, is_input_type, # is_abstract_type removed
                                     is_interface_type, is_object_type,
                                     is_scalar_type, GraphQLNullableType)
from typing_inspect import get_origin

from graphql_api.context import GraphQLContext
from graphql_api.dataclass_mapping import (type_from_dataclass,
                                           type_is_dataclass)
from graphql_api.exception import GraphQLBaseException
from graphql_api.schema import add_applied_directives, get_applied_directives
from graphql_api.types import (GraphQLBytes, GraphQLDate, GraphQLDateTime,
                               GraphQLJSON, GraphQLMappedEnumType, GraphQLUUID,
                               JsonType)
from graphql_api.utils import (has_single_type_union_return, to_camel_case,
                               to_camel_case_text, to_input_value,
                               to_snake_case)


# Helper function definitions moved to before GraphQLTypeMapper class
def get_value(obj: Any, schema: Any, key: str) -> Any:
    """Safely get a value from _schemas dictionary."""
    if not is_graphql(obj, schema):
        return None
    schemas_dict: Dict[Any, Any] = getattr(obj, "_schemas", {})
    schema_info = schemas_dict.get(schema, schemas_dict.get(None))
    if schema_info:
        return schema_info.get(key)
    return None

def is_graphql(obj: Any, schema: Any) -> bool:
    """Check if an object is decorated for GraphQL and valid for the schema."""
    if not hasattr(obj, "_graphql") or not getattr(obj, "_graphql"):
        return False
    if not hasattr(obj, "_schemas") or not isinstance(getattr(obj, "_schemas"), dict):
        return False
    schemas_dict: Dict[Any, Any] = getattr(obj, "_schemas")
    return schema in schemas_dict or None in schemas_dict

def _matches_criterion(func_or_member: Any, schema: Any, mutable: bool) -> bool:
    """Helper to check if a function/member matches field criteria."""
    func_type = get_value(func_or_member, schema, "graphql_type")
    return func_type == "field" or (mutable and func_type == "mutable_field")

def get_class_funcs(class_type: Type, schema: Any, mutable: bool = False) -> List[Tuple[str, Callable[..., Any]]]:
    members: List[Tuple[str, Any]] = []
    try:
        class_mro = class_type.mro()
    except TypeError as e:
        if "unbound method" in str(e):
            raise ImportError(
                str(e) + ". This could be because type decorator is not correctly being"
                " imported from the graphql_api package."
            )
        else:
            raise e

    for _class_type_in_mro in class_mro:
        for key, member in inspect.getmembers(_class_type_in_mro):
            if not (key.startswith("__") and key.endswith("__")):
                if not any(item[0] == key for item in members):
                    members.append((key, member))

    if hasattr(class_type, "graphql_fields") and callable(class_type.graphql_fields):
        for func in class_type.graphql_fields(): # type: ignore
            if callable(func) and hasattr(func, '__name__'):
                 if not any(item[0] == func.__name__ for item in members):
                    members.append((func.__name__, func))

    processed_members: List[Tuple[str, Callable[..., Any]]] = []
    for key, member in members:
        if isinstance(member, property):
            if member.fget:
                if is_graphql(member.fget, schema) and _matches_criterion(member.fget, schema, mutable):
                    processed_members.append((key, member.fget))
            if mutable and member.fset:
                if is_graphql(member.fset, schema) and _matches_criterion(member.fset, schema, mutable):
                    processed_members.append((key, member.fset))
        elif callable(member):
            if is_graphql(member, schema) and _matches_criterion(member, schema, mutable):
                processed_members.append((key, member))
        elif is_graphql(member, schema) and _matches_criterion(member, schema, mutable) and not callable(member):
            pass

    final_funcs: List[Tuple[str, Callable[..., Any]]] = []
    seen_keys: Set[str] = set()
    for key, func in processed_members:
        if key not in seen_keys:
            final_funcs.append((key, func))
            seen_keys.add(key)

    return final_funcs

def is_interface(type_: Type, schema: Any) -> bool:
    if not inspect.isclass(type_): return False
    if is_graphql(type_, schema):
        graphql_type_val = get_value(type_, schema, "graphql_type")
        defined_on_val = get_value(type_, schema, "defined_on")
        return graphql_type_val == "interface" and defined_on_val == type_
    return False

def is_abstract(type_: Type, schema: Any) -> bool:
    if not inspect.isclass(type_): return False
    if is_graphql(type_, schema):
        graphql_type_val = get_value(type_, schema, "graphql_type")
        defined_on_val = get_value(type_, schema, "defined_on")
        return graphql_type_val == "abstract" and defined_on_val == type_
    return False

class UnionFlagType:
    pass

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
        self.registry: Dict[str, GraphQLType | None] = registry or {}
        self.reverse_registry: Dict[GraphQLType, Type] = reverse_registry or {}
        self.suffix = suffix
        self.meta = {}
        self.input_type_mapper = None
        self.schema = schema
        self.applied_schema_directives = []

    def types(self) -> Set[GraphQLType | None]:
        return set(self.registry.values())

    def map_to_field(self, function_type: Callable, name="", key="") -> GraphQLField | None:
        type_hints = typing.get_type_hints(function_type)
        description = to_camel_case_text(inspect.getdoc(function_type) or "")

        return_type = type_hints.pop("return", None)

        if has_single_type_union_return(function_type):
            return_type = Union[return_type, UnionFlagType]

        if not return_type:
            raise GraphQLTypeMapInvalid(
                f"Field '{name}.{key}' with function ({function_type}) did "
                f"not specify a valid return type."
            )

        return_graphql_type = cast(Optional[GraphQLType], self.map(return_type))

        nullable = False
        if typing_inspect.is_union_type(return_type):
            union_args = typing_inspect.get_args(return_type, evaluate=True)
            if type(None) in union_args:
                nullable = True

        if return_graphql_type is None and not nullable:
             raise GraphQLTypeMapError(
                f"Field '{name}.{key}' with function '{function_type}' return "
                f"type '{return_type}' mapped to None, but was not declared Optional."
            )

        if return_graphql_type is not None and not self.validate(return_graphql_type):
            raise GraphQLTypeMapError(
                f"Field '{name}.{key}' with function '{function_type}' return "
                f"type '{return_type}' could not be mapped to a valid GraphQL "
                f"type, was mapped to invalid type {return_graphql_type}."
            )
        elif return_graphql_type is None and nullable: # If it's nullable and mapped to None
            return None # map_to_field itself returns None

        enum_return = None
        if isinstance(return_graphql_type, GraphQLEnumType):
            enum_return = return_type

        if not nullable and return_graphql_type is not None:
            return_graphql_type = GraphQLNonNull(cast(GraphQLNullableType, return_graphql_type))
        elif return_graphql_type is None and not nullable:
            raise GraphQLTypeMapError(
                f"Field '{name}.{key}' mapped to None but was not declared Optional and not caught by prior checks."
            )

        signature = inspect.signature(function_type)
        default_args = {
            key_param: value.default
            for key_param, value in signature.parameters.items()
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

        include_context = False
        for _key, hint in type_hints.items():
            if (_key == "context" and inspect.isclass(hint) and issubclass(hint, GraphQLContext)):
                include_context = True
                continue

            arg_type: GraphQLType | None = input_type_mapper.map(hint)
            if arg_type is None:
                 raise GraphQLTypeMapError(
                    f"Argument '{_key}' in '{name}.{key}' mapped to None."
                )

            # Removed unused enum_arguments dictionary logic here

            is_arg_nullable = _key in default_args
            if not is_arg_nullable and arg_type is not None:
                arg_type = GraphQLNonNull(cast(GraphQLNullableType, arg_type))

            if not is_input_type(arg_type) and not isinstance(arg_type, GraphQLNonNull) or \
               (isinstance(arg_type, GraphQLNonNull) and not is_input_type(arg_type.of_type)):
                raise GraphQLTypeMapError(
                    f"Argument '{_key}' in '{name}.{key}' mapped to non-input type '{arg_type}'."
                )

            arguments[to_camel_case(_key)] = GraphQLArgument(
                type_=cast(GraphQLInputType, arg_type), default_value=default_args.get(_key, Undefined)
            )

        def resolve(_self_res, info: Any = None, context: Any = None, *args_res: Any, **kwargs_res: Any) -> Any:
            _args = {to_snake_case(_key_res): arg_val for _key_res, arg_val in kwargs_res.items()}
            if include_context:
                if info is not None and hasattr(info, 'context'):
                    _args["context"] = info.context

            function_name = function_type.__name__
            parent_type = _self_res.__class__
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
                        response = function_type(_self_res, **_args)
                else:
                    response = getattr(_self_res, function_name, None)
            else:
                function_type_override = getattr(_self_res, function_name, None)
                if function_type_override is not None:
                    response = function_type_override(**_args)
                else:
                    response = function_type(_self_res, **_args)

            if enum_return:
                if isinstance(response, enum.Enum):
                    response = response.value
            return response

        field_class = GraphQLField
        func_type_val = get_value(function_type, self.schema, "graphql_type")
        if func_type_val == "mutable_field":
            field_class = GraphQLMutableField

        if return_graphql_type is None:
             raise GraphQLTypeMapError(f"Cannot create field '{name}.{key}' because its type resolved to None unexpectedly (post-nullable checks).")

        field = field_class(
            return_graphql_type, arguments, resolve, description=description
        )
        self.add_applied_directives(field, f"{name}.{key}", function_type)
        return field

    def map_to_union(self, union_type: Union) -> GraphQLType | None:
        union_args = typing_inspect.get_args(union_type, evaluate=True)
        union_args = [arg for arg in union_args if arg != UnionFlagType]
        none_type = type(None)
        union_map: Dict[type, GraphQLType | None] = { # Value can be None
            arg: self.map(arg) for arg in union_args if arg and arg != none_type
        }

        if len(union_map) == 1 and none_type in union_args:
            _, mapped_type = union_map.popitem()
            return mapped_type # This could be GraphQLType or None

        def resolve_type(value, info, _type):
            from graphql_api.remote import GraphQLRemoteObject
            value_type = type(value)
            if isinstance(value, GraphQLRemoteObject):
                value_type = value.python_type
            for arg, mapped_union_member_type in union_map.items():
                if mapped_union_member_type and issubclass(value_type, arg) and hasattr(mapped_union_member_type, "name"):
                    return mapped_union_member_type.name
            return None # Ensure a default string or None is returned

        names = [arg.__name__ for arg in union_args if hasattr(arg, '__name__') and arg.__name__ != "NoneType"]
        name = f"{''.join(names)}{self.suffix}Union"

        valid_union_types = [t for t in union_map.values() if t is not None and isinstance(t, GraphQLObjectType)] # Must be ObjectType for GraphQLUnionType
        if not valid_union_types:
            return None

        union = GraphQLUnionType(
            name, types=valid_union_types, resolve_type=resolve_type
        )
        self.add_applied_directives(union, name, union_type)
        return union

    def map_to_list(self, type_: List) -> GraphQLList | None:
        list_args = typing_inspect.get_args(type_)
        if not list_args:
            return None
        list_subtype_hint = list_args[0]

        origin = typing_inspect.get_origin(list_subtype_hint)
        args = typing_inspect.get_args(list_subtype_hint)
        is_subtype_nullable = False
        if origin == Union and type(None) in args:
            actual_args = tuple(a for a in args if a is not type(None))
            if len(actual_args) == 1:
                list_subtype_hint = actual_args[0]
            else:
                pass
            is_subtype_nullable = True

        subtype: GraphQLType | None = self.map(list_subtype_hint)

        if subtype is None:
            return None

        if not is_subtype_nullable:
            if subtype is None: # Should be caught by previous 'if subtype is None'
                 raise GraphQLTypeMapError(f"Cannot make a non-nullable list from a None subtype for {list_subtype_hint}")
            subtype = GraphQLNonNull(cast(GraphQLNullableType, subtype))

        return GraphQLList(type_=subtype) # Removed unnecessary cast

    def map_to_literal(self, type__) -> GraphQLType | None:
        literal_args = typing_inspect.get_args(type__, evaluate=True)
        _type = type(literal_args[0])
        if not all(isinstance(x, _type) for x in literal_args):
            raise TypeError("Literals must all be of the same type")
        return self.map(_type)

    def map_to_enum(self, type_: Type[enum.Enum]) -> GraphQLEnumType | None:
        enum_type_val = type_ # renamed to avoid conflict
        name = f"{type_.__name__}Enum"
        doc = inspect.getdoc(type_)
        description = to_camel_case_text(doc or "")
        default_doc = inspect.getdoc(GraphQLGenericEnum)
        default_description = to_camel_case_text(default_doc or "")

        if not description or description == default_description:
            description = f"A {name}."

        mapped_enum_type = GraphQLMappedEnumType( # Renamed variable
            name=name, values=enum_type_val, description=description
        )
        mapped_enum_type.enum_type = enum_type_val # Use consistent variable

        def serialize(_self, value) -> Union[str, None, UndefinedType]:
            if value and isinstance(value, collections.abc.Hashable):
                if isinstance(value, enum.Enum):
                    value = value.value
                lookup_value = _self._value_lookup.get(value)
                if lookup_value:
                    return lookup_value
                else:
                    return Undefined
            return None
        mapped_enum_type.serialize = types.MethodType(serialize, mapped_enum_type)
        self.add_applied_directives(mapped_enum_type, name, type_)
        return mapped_enum_type

    scalar_map = [
        ([UUID], GraphQLUUID), ([str], GraphQLString), ([bytes], GraphQLBytes),
        ([bool], GraphQLBoolean), ([int], GraphQLInt), ([dict, list, set], GraphQLJSON),
        ([float], GraphQLFloat), ([datetime], GraphQLDateTime), ([date], GraphQLDate),
        ([type(None)], None),
    ]

    def scalar_classes(self):
        classes = []
        for scalar_class_map in self.scalar_map:
            for scalar_class in scalar_class_map[0]:
                classes.append(scalar_class)
        return classes

    def map_to_scalar(self, class_type: Type) -> GraphQLScalarType | None:
        name = class_type.__name__
        for test_types, graphql_type_cls in self.scalar_map:
            for test_type in test_types:
                if class_type is test_type or (inspect.isclass(class_type) and issubclass(class_type, test_type)):
                    if graphql_type_cls is None:
                        return None
                    graphql_instance = graphql_type_cls() if inspect.isclass(graphql_type_cls) else graphql_type_cls
                    self.add_applied_directives(graphql_instance, name, class_type)
                    return graphql_instance
        return None

    def map_to_interface(self, class_type: Type) -> GraphQLType | None:
        subclasses = class_type.__subclasses__()
        name = class_type.__name__
        for subclass in subclasses:
            if not is_abstract(subclass, self.schema):
                self.map(subclass)

        class_funcs = get_class_funcs(class_type, self.schema, self.as_mutable)
        interface_name = f"{name}{self.suffix}Interface"
        doc = inspect.getdoc(class_type)
        description = to_camel_case_text(doc or "")

        def local_resolve_type():
            local_self = self
            def resolve_type(value: Any, info: Any, _type: Any) -> str | None:
                mapped_value: GraphQLType | None = local_self.map(type(value))
                if mapped_value is not None and hasattr(mapped_value, "name") and isinstance(mapped_value.name, str):
                    return mapped_value.name
                return None
            return resolve_type

        def local_fields():
            local_self = self
            local_class_funcs_ = class_funcs # renamed
            local_class_type = class_type
            local_name = name
            def fields():
                fields_ = {}
                for key_, func_ in local_class_funcs_:
                    local_class_name = local_class_type.__name__
                    # Ensure func_ has __globals__ if it's a function, might need adjustment for other callables
                    if hasattr(func_, '__globals__'):
                        func_.__globals__[local_class_name] = local_class_type
                    fields_[to_camel_case(key_)] = local_self.map_to_field(
                        func_, local_name, key_
                    )
                return fields_
            return fields

        interface = GraphQLInterfaceType(
            interface_name, fields=local_fields(),
            resolve_type=local_resolve_type(), description=description,
        )
        self.add_applied_directives(interface, interface_name, class_type)
        return interface

    def map_to_input(self, class_type: Type) -> GraphQLType | None:
        name = f"{class_type.__name__}{self.suffix}Input"
        creator: Callable[..., Any]
        func: Callable[..., Any]
        if hasattr(class_type, "graphql_from_input"):
            creator = class_type.graphql_from_input # type: ignore
            func = creator
        else:
            creator = class_type
            func = class_type.__init__

        doc_func = inspect.getdoc(func)
        doc_class = inspect.getdoc(class_type)
        description = to_camel_case_text(doc_func or doc_class or "")

        try:
            type_hints = typing.get_type_hints(func)
        except Exception as err:
            raise TypeError(
                f"Unable to build input type '{name}' for '{class_type}', "
                f"check the '{class_type}.__init__' method or "
                f"'{class_type}.graphql_from_input' method, {err}."
            )
        type_hints.pop("return", None)

        signature = inspect.signature(func)
        default_args = {
            key: value.default for key, value in signature.parameters.items()
            if value.default is not inspect.Parameter.empty
        }

        def local_fields():
            local_name_ = name # renamed
            local_self = self
            local_type_hints_ = type_hints # renamed
            local_default_args_ = default_args # renamed
            def fields():
                arguments = {}
                for key, hint in local_type_hints_.items():
                    input_arg_type: GraphQLType | None = local_self.map(hint)
                    if input_arg_type is None:
                        raise GraphQLTypeMapInvalid(f"Cannot map input field '{key}' of type '{hint}' in '{local_name_}'")
                    is_field_nullable = key in local_default_args_
                    if not is_field_nullable:
                        input_arg_type = GraphQLNonNull(cast(GraphQLNullableType, input_arg_type))
                    final_type_for_field = cast(GraphQLInputType, input_arg_type)
                    default_value = local_default_args_.get(key, Undefined)
                    if default_value is not Undefined and default_value is not None:
                        try:
                            default_value = to_input_value(default_value)
                        except ValueError as _err:
                            raise ValueError(
                                f"Unable to map default value for {local_name_}.{key}, {_err}."
                            )
                    arguments[to_camel_case(key)] = GraphQLInputField(
                        type_=final_type_for_field, default_value=default_value
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
            name, fields=local_fields(), out_type=local_container_type(), description=description,
        )
        self.add_applied_directives(input_object, name, class_type)
        return input_object

    def add_applied_directives(
        self, graphql_type: GraphQLType | GraphQLField, key: str, value: Any # value is the original Python type/func
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
                location = DirectiveLocation.OBJECT; type_str = "Object"
            elif is_interface_type(graphql_type):
                location = DirectiveLocation.INTERFACE; type_str = "Interface"
            elif is_enum_type(graphql_type):
                location = DirectiveLocation.ENUM; type_str = "Enum"
            elif is_input_type(graphql_type): # This covers GraphQLInputObjectType
                location = DirectiveLocation.INPUT_OBJECT; type_str = "Input Object"
            elif is_union_type(graphql_type):
                location = DirectiveLocation.UNION; type_str = "Union"
            elif is_scalar_type(graphql_type):
                location = DirectiveLocation.SCALAR; type_str = "Scalar"
            elif isinstance(value, type) and is_abstract(value, self.schema): # Check original Python type for abstract
                type_str = "Abstract (Python type)"
                # Directives on abstract Python types might not map directly or be supported
                # raise TypeError("Directives on abstract Python types are not directly applied to a specific GraphQL type location.")
            elif isinstance(graphql_type, GraphQLField):
                location = DirectiveLocation.FIELD_DEFINITION; type_str = "Field"

            if location is None and type_str != "Abstract (Python type)": # Only raise if not handled abstract
                 raise TypeError(f"Unsupported GraphQL type for directives: {graphql_type} on key '{key}'")

            for applied_directive in applied_directives:
                from graphql_api import AppliedDirective
                applied_directive: AppliedDirective
                if location and location not in applied_directive.directive.locations:
                    raise TypeError(
                        f"Directive '{applied_directive.directive}' only supports "
                        f"{applied_directive.directive.locations} locations but was"
                        f" used on '{key}' which is a '{type_str}' ({location}) and does not "
                        f"support it."
                    )

    def map_to_object(self, class_type: Type) -> GraphQLType:
        name = f"{class_type.__name__}{self.suffix}"
        description = to_camel_case_text(inspect.getdoc(class_type))
        class_funcs = get_class_funcs(class_type, self.schema, self.as_mutable)

        for key, func in class_funcs:
            func_meta = get_value(func, self.schema, "meta")
            if func_meta: # Ensure func_meta is not None
                func_meta["graphql_type"] = get_value(func, self.schema, "graphql_type")
                self.meta[(name, to_snake_case(key))] = func_meta

        def local_interfaces():
            local_class_type = class_type
            local_self = self
            def interfaces():
                _interfaces = []
                superclasses = inspect.getmro(local_class_type)[1:]
                for superclass in superclasses:
                    if is_interface(superclass, local_self.schema):
                        value_ = local_self.map(superclass) # Renamed value to value_
                        if isinstance(value_, GraphQLInterfaceType):
                            interface: GraphQLInterfaceType = value_
                            _interfaces.append(interface)
                return _interfaces
            return interfaces

        def local_fields():
            local_self = self
            local_class_funcs_ = class_funcs # Renamed
            local_class_type = class_type
            local_name = name
            def fields():
                fields_ = {}
                for key_, func_ in local_class_funcs_:
                    local_class_name = local_class_type.__name__
                    if hasattr(func_, '__globals__'):
                        func_.__globals__[local_class_name] = local_class_type
                    _field = local_self.map_to_field(func_, local_name, key_)
                    if _field: # map_to_field can return None
                        fields_[to_camel_case(key_)] = _field
                return fields_
            return fields

        obj = GraphQLObjectType(
            name, local_fields(), local_interfaces(), description=description, extensions={},
        )
        self.add_applied_directives(obj, name, class_type)
        return obj

    def rmap(self, graphql_type: GraphQLType) -> Type | None:
        current_type = graphql_type
        while hasattr(current_type, "of_type"):
            if isinstance(getattr(current_type, 'of_type'), GraphQLType):
                current_type = getattr(current_type, 'of_type')
            else:
                break
        return self.reverse_registry.get(current_type)

    def map(self, type_: Type, use_graphql_type=True) -> GraphQLType | None:
        if type_ is type(None):
            return None

        def _map(type__) -> GraphQLType | None:
            if type__ == JsonType: return GraphQLJSON
            if use_graphql_type and inspect.isclass(type__) and type__ is not Any:
                if hasattr(type__, 'graphql_type') and callable(type__.graphql_type) and issubclass(type__, GraphQLTypeWrapper):
                    return type__.graphql_type(mapper=self) # type: ignore
                if type_is_dataclass(type__):
                    return type_from_dataclass(type__, mapper=self)
            if typing_inspect.is_union_type(type__):
                return self.map_to_union(type__)
            if typing_inspect.is_literal_type(type__):
                return self.map_to_literal(type__)
            origin_type = get_origin(type__)
            if inspect.isclass(origin_type) and issubclass(origin_type, (List, Set)):
                return self.map_to_list(type__)
            if inspect.isclass(type__):
                if issubclass(type__, GraphQLType):
                    try: return type__() # type: ignore
                    except TypeError: pass
                scalar_mapped_type = self.map_to_scalar(type__)
                if scalar_mapped_type: return scalar_mapped_type
                if issubclass(type__, enum.Enum): return self.map_to_enum(type__)
                if is_interface(type__, self.schema): return self.map_to_interface(type__)
                if self.as_input: return self.map_to_input(type__)
                else: return self.map_to_object(type__)
            if isinstance(type__, GraphQLType): return type__
            return None

        try: type_repr = str(type_)
        except Exception: type_repr = object.__repr__(type_)

        key_hash = hash((type_repr, self.as_input, self.as_mutable, self.suffix))
        generic_key_parts = [f"Registry({key_hash})"]
        if self.suffix: generic_key_parts.append(f"|{self.suffix}")
        generic_key_parts.append(f"|{self.as_input}")
        generic_key_parts.append(f"|{self.as_mutable}")
        generic_key = "".join(generic_key_parts)

        if generic_key in self.registry: return self.registry[generic_key]
        value = _map(type_)
        if value is None:
            self.registry[generic_key] = None
            return None
        if self.validate(value):
            self.registry[generic_key] = value
            if isinstance(value, collections.abc.Hashable):
                 self.reverse_registry[value] = type_
            return value
        else:
            return None

    def register(self, python_type: Type, key: str, value: GraphQLType | None):
        self.registry[key] = value
        if value is not None and isinstance(value, collections.abc.Hashable):
            self.reverse_registry[value] = python_type

    def validate(self, type_: GraphQLType | None, evaluate=False) -> bool:
        if type_ is None: return False
        if not isinstance(type_, GraphQLType): return False
        current_type = type_
        if isinstance(current_type, GraphQLNonNull):
            current_type = current_type.of_type
        if self.as_input and not is_input_type(current_type): return False
        if isinstance(current_type, GraphQLObjectType):
            if evaluate:
                try:
                    if len(current_type.fields) == 0: return False
                except AssertionError: return False
            elif not callable(current_type._fields) and len(current_type._fields) == 0: # type: ignore
                return False
        return True

def _get_actual_type_from_type_hint(type_: Type) -> Type[Any] | None:
    origin_type = get_origin(type_)
    if origin_type is Union:
        args = typing_inspect.get_args(type_, evaluate=True)
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1: return non_none_args[0]
        elif len(non_none_args) > 1: return type_
    return origin_type if origin_type else type_

def _get_type_from_type_hint_direct(self: "GraphQLTypeMapper",type_hint: Type) -> GraphQLType | None:
    actual_type_to_map = _get_actual_type_from_type_hint(type_hint)
    if actual_type_to_map is None: return None
    origin_of_th = get_origin(type_hint)
    if inspect.isclass(origin_of_th) and issubclass(origin_of_th, (List, Set)):
        return self.map_to_list(type_hint)
    if inspect.isclass(actual_type_to_map) and issubclass(actual_type_to_map, enum.Enum):
        return self.map_to_enum(actual_type_to_map)
    if is_scalar(actual_type_to_map):
        return self.map_to_scalar(actual_type_to_map)
    if typing_inspect.is_union_type(actual_type_to_map):
        return self.map_to_union(actual_type_to_map)
    if actual_type_to_map is not None and (inspect.isclass(actual_type_to_map) or isinstance(actual_type_to_map, GraphQLType) or typing_inspect.is_union_type(actual_type_to_map) or typing_inspect.is_literal_type(actual_type_to_map)):
         return self.map(actual_type_to_map)
    return None

def is_scalar(type_):
    if not inspect.isclass(type_) and type_ is not Any:
        return type_ in (str, int, float, bool, bytes, datetime, date, UUID)
    elif type_ is Any:
        return False
    for test_types, _ in GraphQLTypeMapper.scalar_map:
        for test_type in test_types:
            if test_type is None: continue
            if inspect.isclass(test_type) and inspect.isclass(type_) and issubclass(type_, test_type):
                return True
    return False

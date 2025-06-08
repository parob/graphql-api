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
                                     GraphQLInputField, GraphQLInputObjectType,
                                     GraphQLInterfaceType, GraphQLNonNull,
                                     GraphQLScalarType, GraphQLType,
                                     GraphQLUnionType, is_abstract_type,
                                     is_enum_type, is_input_type,
                                     is_interface_type, is_object_type,
                                     is_scalar_type)
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

class UnionFlagType: pass
class GraphQLTypeMapInvalid(GraphQLBaseException): pass
class GraphQLTypeMapError(GraphQLBaseException): pass
class GraphQLTypeWrapper:
    @classmethod
    def graphql_type(cls, mapper: "GraphQLTypeMapper") -> GraphQLType: pass
class GraphQLMetaKey(enum.Enum):
    resolve_to_mutable = "RESOLVE_TO_MUTABLE"; resolve_to_self = "RESOLVE_TO_SELF"
    native_middleware = "NATIVE_MIDDLEWARE"; error_protection = "ERROR_PROTECTION"
class GraphQLMutableField(GraphQLField): pass
class GraphQLGenericEnum(enum.Enum): pass

def get_value(obj: Any, schema: Any, key: str) -> Any:
    if not is_graphql(obj, schema): return None
    schemas_dict: Dict[Any, Any] = getattr(obj, "_schemas", {}); schema_info = schemas_dict.get(schema, schemas_dict.get(None))
    if schema_info: return schema_info.get(key)
    return None

def is_graphql(obj: Any, schema: Any) -> bool:
    graphql = getattr(obj, "_graphql", None); schemas = getattr(obj, "_schemas", {})
    try: valid_schema = schema in schemas.keys() or None in schemas.keys()
    except Exception: valid_schema = False
    return graphql and schemas and valid_schema

def _matches_criterion(func_or_member_for_meta: Any, schema: Any, mutable: bool, member_name_for_log: str = "", class_name_for_log: str = "") -> bool:
    # func_or_member_for_meta is the one with actual metadata (could be from base class)
    if not member_name_for_log: member_name_for_log = getattr(func_or_member_for_meta, '__name__', str(func_or_member_for_meta))
    if not class_name_for_log:
        qualname_parts = getattr(func_or_member_for_meta, '__qualname__', '').split('.')
        if len(qualname_parts) > 1: class_name_for_log = qualname_parts[-2]
        elif qualname_parts: class_name_for_log = qualname_parts[0]
        else: class_name_for_log = "UnknownClass"
    # print(f"[Matcher] Checking member: {class_name_for_log}.{member_name_for_log}, mutable_flag: {mutable}") # Reduced logging noise

    meta_obj = getattr(func_or_member_for_meta.fget if isinstance(func_or_member_for_meta, property) and func_or_member_for_meta.fget else func_or_member_for_meta, "_graphql_meta", None)
    func_type = get_value(func_or_member_for_meta, schema, "graphql_type")
    result = func_type == "field" or (mutable and func_type == "mutable_field")
    # print(f"[Matcher] Member: {class_name_for_log}.{member_name_for_log}, func_type: {func_type}, meta: {meta_obj}, result: {result}") # Reduced logging noise
    return result

def get_class_funcs(class_type: Type, schema: Any, mutable: bool = False) -> List[Tuple[str, Callable[..., Any]]]:
    # print(f"[GetClassFuncs] Processing class: {class_type.__name__}, mutable_flag: {mutable}") # Reduced logging noise

    raw_members = []
    try: class_types_mro = class_type.mro()
    except TypeError as e:
        if "unbound method" in str(e): raise ImportError(str(e) + ". Decorator import issue.")
        else: raise e
    for _ct_mro in class_types_mro:
        for key, member in inspect.getmembers(_ct_mro):
            if not (key.startswith("__") and key.endswith("__")):
                if not any(m[0] == key for m in raw_members): # Add only first occurrence (most specific)
                    raw_members.append((key, member))

    # print(f"[GetClassFuncs] Class: {class_type.__name__}, mutable_flag: {mutable}, initial members (MRO order, specific first): {[m[0] for m in raw_members]}")

    categorized_fields: Dict[str, Dict[str, Any]] = {}

    for key, member in raw_members: # Iterates from most specific class downwards
        member_for_meta = member
        # If current member isn't tagged, check if any base class version of this member *was* tagged.
        # This ensures an undecorated override still picks up base GraphQL typing.
        if not is_graphql(member_for_meta, schema):
            found_meta_in_base = False
            for base_cls in class_type.mro()[1:]: # Start from parent
                base_member = getattr(base_cls, key, None)
                if base_member and is_graphql(base_member, schema):
                    member_for_meta = base_member # Use base member for metadata lookup
                    # print(f"[GetClassFuncs] Class: {class_type.__name__}, member: {key}. Using metadata from base class {base_cls.__name__}.{key}")
                    found_meta_in_base = True
                    break
            if not found_meta_in_base: # If no metadata found even in bases, skip
                continue

        # Now, member_for_meta has the _graphql tags, 'member' is the actual callable from the most specific class.
        func_type = get_value(member_for_meta, schema, "graphql_type")

        # Check for property getter/setter distinction based on metadata on those specific functions
        if isinstance(member, property):
            if member.fget and is_graphql(member.fget, schema): # Check fget specifically
                fget_func_type = get_value(member.fget, schema, "graphql_type")
                if fget_func_type == "field":
                    if key not in categorized_fields: categorized_fields[key] = {}
                    categorized_fields[key]["field"] = member.fget # Store the actual fget
                    # print(f"[GetClassFuncs] Categorized prop getter: {class_type.__name__}.{key} as field")
            if member.fset and is_graphql(member.fset, schema): # Check fset specifically
                fset_func_type = get_value(member.fset, schema, "graphql_type")
                if fset_func_type == "mutable_field":
                    if key not in categorized_fields: categorized_fields[key] = {}
                    categorized_fields[key]["mutable_field"] = member.fset # Store the actual fset
                    # print(f"[GetClassFuncs] Categorized prop setter: {class_type.__name__}.{key} as mutable_field")
        elif callable(member): # For regular methods
            if func_type == "field":
                if key not in categorized_fields: categorized_fields[key] = {}
                categorized_fields[key]["field"] = member # Store the actual member
                # print(f"[GetClassFuncs] Categorized member: {class_type.__name__}.{key} as field (from func_type on member_for_meta)")
            elif func_type == "mutable_field":
                if key not in categorized_fields: categorized_fields[key] = {}
                categorized_fields[key]["mutable_field"] = member # Store the actual member
                # print(f"[GetClassFuncs] Categorized member: {class_type.__name__}.{key} as mutable_field (from func_type on member_for_meta)")

    final_funcs_dict: Dict[str, Callable] = {}
    if mutable:
        for key, types_dict in categorized_fields.items():
            if "mutable_field" in types_dict:
                final_funcs_dict[key] = types_dict["mutable_field"]
            elif "field" in types_dict: # Mutable types also expose readable fields
                final_funcs_dict[key] = types_dict["field"]
    else:
        for key, types_dict in categorized_fields.items():
            if "field" in types_dict:
                final_funcs_dict[key] = types_dict["field"]

    ordered_final_funcs: List[Tuple[str, Callable]] = []
    final_keys_added = set()
    # Use MRO again for consistent field ordering, preferring subclass fields first.
    for _ct_mro in class_type.mro():
        for key, _ in inspect.getmembers(_ct_mro):
            if key in final_funcs_dict and key not in final_keys_added:
                ordered_final_funcs.append((key, final_funcs_dict[key]))
                final_keys_added.add(key)
    # print(f"[GetClassFuncs] Class: {class_type.__name__}, final_funcs for mutable_flag={mutable}: {[item[0] for item in ordered_final_funcs]}")
    return ordered_final_funcs


def is_interface(type_, schema):
    if is_graphql(type_, schema):
        type_type = get_value(type_, schema, "graphql_type"); type_defined_on = get_value(type_, schema, "defined_on")
        return type_type == "interface" and type_defined_on == type_
    return False
def is_abstract(type_, schema):
    if is_graphql(type_, schema):
        type_type = get_value(type_, schema, "graphql_type"); type_defined_on = get_value(type_, schema, "defined_on")
        return type_type == "abstract" and type_defined_on == type_
    return False
def is_scalar(type_):
    for test_types, _ in GraphQLTypeMapper.scalar_map:
        for test_type in test_types:
            if test_type is None: continue
            if inspect.isclass(type_) and inspect.isclass(test_type) and issubclass(type_, test_type): return True
    return False

class GraphQLTypeMapper:
    def __init__(self, as_mutable=False, as_input=False, registry=None, reverse_registry=None, suffix="", schema=None, named_type_cache: Optional[Dict[str, GraphQLType]] = None ):
        self.as_mutable = as_mutable; self.as_input = as_input; self.registry = registry or {};
        self.reverse_registry = reverse_registry or {}; self.suffix = suffix; self.meta = {};
        self.input_type_mapper = None; self.schema = schema; self.applied_schema_directives = []
        self._named_type_cache: Dict[str, GraphQLType] = named_type_cache if named_type_cache is not None else {}

    def types(self) -> Set[GraphQLType]: return set(self.registry.values()) # type: ignore

    def map_to_field(self, function_type: Callable, name="", key="", owner_class: Optional[Type] = None) -> GraphQLField | None:
        func_name_for_log = getattr(function_type, '__name__', str(function_type))
        # Minimal logging for this version, focusing on the specific test case if needed
        if key == 'name' and name == 'PersonMutable': # Example of very targeted log
             print(f"[MapToField_TARGETED] func: {func_name_for_log}, GQLType: {name}, key: {key}, mutable_mapper: {self.as_mutable}")

        current_locals = {};
        if owner_class: current_locals[owner_class.__name__] = owner_class
        # Add all classes from the owner_class's module to localns for get_type_hints
        if owner_class and hasattr(owner_class, '__module__') and owner_class.__module__ in inspect.sys.modules:
            module = inspect.sys.modules[owner_class.__module__]
            for name_in_module, obj_in_module in inspect.getmembers(module):
                if inspect.isclass(obj_in_module):
                    current_locals[name_in_module] = obj_in_module

        type_hints = typing.get_type_hints(function_type, localns=current_locals)
        description = to_camel_case_text(inspect.getdoc(function_type))
        return_type = type_hints.pop("return", None)
        if has_single_type_union_return(function_type): return_type = Union[return_type, UnionFlagType] # type: ignore
        if not return_type: raise GraphQLTypeMapInvalid(f"Field '{name}.{key}' did not specify valid return type.")

        return_graphql_type = self.map(return_type)
        nullable = typing_inspect.is_union_type(return_type) and type(None) in typing_inspect.get_args(return_type, evaluate=True)

        if return_graphql_type is None and nullable: return None
        if return_graphql_type is None and not nullable:
             raise GraphQLTypeMapError(f"Field '{name}.{key}' return type '{return_type}' mapped to None, but was not declared Optional.")
        if not self.validate(return_graphql_type):
            raise GraphQLTypeMapError(f"Field '{name}.{key}' return type '{return_type}' mapped to invalid type {return_graphql_type}.")

        enum_return = return_type if isinstance(return_graphql_type, GraphQLEnumType) else None
        if not nullable: return_graphql_type = GraphQLNonNull(return_graphql_type) # type: ignore

        signature = inspect.signature(function_type)
        default_args = {k:v.default for k,v in signature.parameters.items() if v.default is not inspect.Parameter.empty}

        input_type_mapper = GraphQLTypeMapper(as_mutable=self.as_mutable, as_input=True, registry=self.registry, reverse_registry=self.reverse_registry, suffix=self.suffix, schema=self.schema, named_type_cache=self._named_type_cache)
        self.input_type_mapper = input_type_mapper
        arguments = {}
        include_context = False
        for _k, hint in type_hints.items():
            if _k=="context" and inspect.isclass(hint) and issubclass(hint,GraphQLContext): include_context=True; continue
            arg_type = input_type_mapper.map(hint)
            is_arg_nullable = _k in default_args
            if not is_arg_nullable and arg_type is not None : arg_type = GraphQLNonNull(arg_type) # type: ignore
            elif arg_type is None and not is_arg_nullable: raise GraphQLTypeMapError(f"Arg {_k} for {name}.{key} is non-nullable but maps to None")
            arguments[to_camel_case(_k)] = GraphQLArgument(type_=arg_type, default_value=default_args.get(_k, Undefined)) # type: ignore

        def resolve(_self_res, info=None, context=None, *args_res, **kwargs_res):
            _args = {to_snake_case(k_res):v for k_res,v in kwargs_res.items()}; function_name = function_type.__name__
            if include_context: _args["context"] = info.context
            parent_type = _self_res.__class__; class_attribute = getattr(parent_type, function_name, None)
            is_property = isinstance(class_attribute, property)
            if is_property: response = getattr(_self_res, function_name) if not _args else function_type(_self_res, **_args)
            else:
                function_type_override = getattr(_self_res, function_name, None)
                response = function_type_override(**_args) if function_type_override is not None and callable(function_type_override) else function_type(_self_res,**_args) # Added callable check
            if enum_return and isinstance(response, enum.Enum): response = response.value
            return response

        field_class = GraphQLField; func_type_val = get_value(function_type, self.schema, "graphql_type")
        if func_type_val == "mutable_field": field_class = GraphQLMutableField

        field = field_class(return_graphql_type, arguments, resolve, description=description) # type: ignore
        self.add_applied_directives(field, f"{name}.{key}", function_type)
        return field

    def map_to_object(self, class_type: Type) -> GraphQLType:
        name = f"{class_type.__name__}{self.suffix}"
        if name in self._named_type_cache: return self._named_type_cache[name]

        # print(f"[MapToObject] Start: {name}, as_mutable={self.as_mutable}") # Reduced logging

        description = to_camel_case_text(inspect.getdoc(class_type))
        class_funcs = get_class_funcs(class_type, self.schema, self.as_mutable)

        # print(f"[MapToObject] For {name}, get_class_funcs returned: {[f[0] for f in class_funcs]}")

        for key, func in class_funcs:
            func_meta = get_value(func, self.schema, "meta")
            if func_meta:
                func_meta["graphql_type"] = get_value(func, self.schema, "graphql_type")
                self.meta[(name, to_snake_case(key))] = func_meta

        def local_interfaces():
            local_class_type = class_type; local_self = self
            def interfaces():
                _interfaces = []
                for superclass in inspect.getmro(local_class_type)[1:]:
                    if is_interface(superclass, local_self.schema):
                        value = local_self.map(superclass)
                        if isinstance(value, GraphQLInterfaceType): _interfaces.append(value)
                return _interfaces
            return interfaces

        def local_fields():
            local_self = self; local_class_funcs_for_thunk = class_funcs;
            local_class_type = class_type; local_gql_object_name_for_thunk = name
            def fields():
                # print(f"[ObjectFieldsThunk] Fields thunk executing for GQL Type: {local_gql_object_name_for_thunk}") # Reduced logging
                fields_ = {}
                for key_, func_ in local_class_funcs_for_thunk:
                    # print(f"[ObjectFieldsThunk] About to call map_to_field for func: {key_} for GQL type {local_gql_object_name_for_thunk}")
                    _field = local_self.map_to_field(func_, local_gql_object_name_for_thunk, key_, owner_class=local_class_type)
                    # print(f"[ObjectFieldsThunk] map_to_field for func: {key_} returned: {'Field' if _field else 'None'}")
                    if _field: fields_[to_camel_case(key_)] = _field
                # print(f"[ObjectFieldsThunk] Finished fields for GQL Type: {local_gql_object_name_for_thunk}. Resulting fields map: {list(fields_.keys())}")
                return fields_
            return fields

        obj = GraphQLObjectType(name, local_fields(), local_interfaces(), description=description, extensions={})
        self._named_type_cache[name] = obj
        self.add_applied_directives(obj, name, class_type)
        return obj

    def map_to_enum(self, type_: Type[enum.Enum]) -> GraphQLEnumType:
        name = f"{type_.__name__}Enum"
        if name in self._named_type_cache: return cast(GraphQLEnumType, self._named_type_cache[name])
        description = to_camel_case_text(inspect.getdoc(type_)); default_desc = to_camel_case_text(inspect.getdoc(GraphQLGenericEnum))
        if not description or description == default_desc: description = f"A {name}."
        enum_type_obj = GraphQLMappedEnumType(name=name, values=type_, description=description); enum_type_obj.enum_type = type_ # type: ignore
        def serialize(_self,v):
            if v and isinstance(v,collections.abc.Hashable): return _self._value_lookup.get(v.value if isinstance(v,enum.Enum) else v, Undefined) # type: ignore
            return None
        enum_type_obj.serialize = types.MethodType(serialize,enum_type_obj) # type: ignore
        self._named_type_cache[name] = enum_type_obj; self.add_applied_directives(enum_type_obj,name,type_); return enum_type_obj
    def map_to_interface(self, class_type: Type) -> GraphQLType:
        interface_name = f"{class_type.__name__}{self.suffix}Interface"
        if interface_name in self._named_type_cache: return self._named_type_cache[interface_name]
        name = class_type.__name__; description = to_camel_case_text(inspect.getdoc(class_type))
        class_funcs = get_class_funcs(class_type, self.schema, self.as_mutable)
        for subclass in class_type.__subclasses__():
            if not is_abstract(subclass, self.schema): self.map(subclass)
        def lr_type(): local_self=self; return lambda v,i,t: local_self.map(type(v)).name if hasattr(local_self.map(type(v)),'name') else None # type: ignore
        def l_fields():
            local_self=self; local_key_funcs=class_funcs; local_type=class_type; local_name_for_thunk=name
            def fields(): return {to_camel_case(k):local_self.map_to_field(f,local_name_for_thunk,k, owner_class=local_type) for k,f in local_key_funcs}
            return fields
        interface = GraphQLInterfaceType(interface_name,l_fields(),lr_type(),description=description)
        self._named_type_cache[interface_name] = interface; self.add_applied_directives(interface,interface_name,class_type); return interface
    def map_to_input(self, class_type: Type) -> GraphQLType:
        name = f"{class_type.__name__}{self.suffix}Input"
        if name in self._named_type_cache: return self._named_type_cache[name]
        if hasattr(class_type,"graphql_from_input"): creator=class_type.graphql_from_input; func=creator # type: ignore
        else: creator=class_type; func=class_type.__init__
        desc=to_camel_case_text(inspect.getdoc(func) or inspect.getdoc(class_type));
        current_locals = {class_type.__name__: class_type} # For get_type_hints
        if hasattr(class_type, '__module__') and class_type.__module__ in inspect.sys.modules: # For get_type_hints
            module = inspect.sys.modules[class_type.__module__]
            for name_in_module, obj_in_module in inspect.getmembers(module):
                if inspect.isclass(obj_in_module): current_locals[name_in_module] = obj_in_module
        try: type_hints=typing.get_type_hints(func, localns=current_locals)
        except Exception as e: raise TypeError(f"Unable to build input type '{name}' for '{class_type}': {e}")
        type_hints.pop("return",None); defaults={k:v.default for k,v in inspect.signature(func).parameters.items() if v.default is not inspect.Parameter.empty}
        def l_fields():
            args={}; [args.update({to_camel_case(k):GraphQLInputField(GraphQLNonNull(self.map(h)) if k not in defaults else self.map(h),default_value=to_input_value(defaults[k]) if k in defaults and defaults[k] is not None else Undefined)}) for k,h in type_hints.items()]; return args # type: ignore
            return args
        obj=GraphQLInputObjectType(name,l_fields(),lambda data:creator(**{to_snake_case(k):v for k,v in data.items()}),description=desc); self._named_type_cache[name]=obj; self.add_applied_directives(obj,name,class_type); return obj

    scalar_map = [([UUID],GraphQLUUID),([str],GraphQLString),([bytes],GraphQLBytes),([bool],GraphQLBoolean),([int],GraphQLInt),([dict,list,set],GraphQLJSON),([float],GraphQLFloat),([datetime],GraphQLDateTime),([date],GraphQLDate),([type(None)],None),]
    def scalar_classes(self): classes=[];_=[classes.append(sc) for scm in self.scalar_map for sc in scm[0] if sc is not None]; return classes # type: ignore
    def map_to_scalar(self,t:Type)->GraphQLScalarType: n=t.__name__;gt=next(gt for ts,gt in self.scalar_map if any(issubclass(t,x) for x in ts if x is not None)); self.add_applied_directives(gt,n,t); return gt # type: ignore
    def map_to_list(self,t:List)->GraphQLList: st_args=typing_inspect.get_args(t); st=st_args[0] if st_args else Any; gst=self.map(st); o=get_origin(st);a=typing_inspect.get_args(st);n=o==Union and type(None) in a;gst=GraphQLNonNull(gst) if not n and gst else gst; return GraphQLList(gst) # type: ignore
    def map_to_union(self,u:Union)->GraphQLType: args=[a for a in typing_inspect.get_args(u,True) if a!=UnionFlagType]; n_type=type(None); umap={a:self.map(a) for a in args if a and a!=n_type}; return next(iter(umap.values())) if len(umap)==1 and n_type in args else GraphQLUnionType(f"{''.join(a.__name__ for a in args if hasattr(a,'__name__') and a.__name__!='NoneType')}{self.suffix}Union",list(v for v in umap.values() if v is not None),lambda v,i,t_:next((m.name for x,m in umap.items() if m and issubclass(type(v) if not isinstance(v, GraphQLTypeWrapper) else v.python_type,x) and hasattr(m,'name')),None)) # type: ignore
    def map_to_literal(self,t)->GraphQLType: return self.map(type(typing_inspect.get_args(t,evaluate=True)[0])) # type: ignore
    def add_applied_directives(self,gt:Any,k:str,v:Any): pass
    def rmap(self,gt:GraphQLType)->Type: # type: ignore
        while hasattr(gt,"of_type"):gt=gt.of_type # type: ignore
        return self.reverse_registry.get(gt) # type: ignore

    _scalar_map_direct_cache = None
    @staticmethod
    def _get_scalar_map_direct():
        if GraphQLTypeMapper._scalar_map_direct_cache is None:
            GraphQLTypeMapper._scalar_map_direct_cache = {t: gt for types, gt in GraphQLTypeMapper.scalar_map if types and types[0] is not type(None) for t in types if t is not None and gt is not None}
        return GraphQLTypeMapper._scalar_map_direct_cache

    def map(self, type_: Type, use_graphql_type=True) -> GraphQLType | None:
        if type_ is type(None): return None
        key_hash=abs(hash(str(type_)))%(10**8); suffix_str = self.suffix; generic_key=f"Registry({key_hash}){suffix_str and ('|'+suffix_str)}|{self.as_input}|{self.as_mutable}"

        if inspect.isclass(type_): # Attempt to hit _named_type_cache early for named types
            potential_name = f"{type_.__name__}{self.suffix}"
            if self.as_input: potential_name += "Input"
            elif is_interface(type_, self.schema): potential_name += "Interface"
            elif issubclass(type_, enum.Enum): potential_name = f"{type_.__name__}Enum"
            if potential_name in self._named_type_cache: return self._named_type_cache[potential_name]

        if generic_key in self.registry: return self.registry[generic_key]

        def _map_inner(type__param: Type) -> GraphQLType | None:
            if type__param == JsonType: return GraphQLJSON
            if use_graphql_type and inspect.isclass(type__param) and type__param is not Any:
                if hasattr(type__param, 'graphql_type') and callable(type__param.graphql_type) and issubclass(type__param, GraphQLTypeWrapper): return type__param.graphql_type(mapper=self)
                if type_is_dataclass(type__param): return type_from_dataclass(type__param, mapper=self)
            if typing_inspect.is_union_type(type__param): return self.map_to_union(type__param)
            if typing_inspect.is_literal_type(type__param): return self.map_to_literal(type__param)
            origin_type = get_origin(type__param)
            if inspect.isclass(origin_type) and issubclass(origin_type, (collections.abc.Sequence, collections.abc.Set)): return self.map_to_list(type__param) # type: ignore
            if inspect.isclass(type__param):
                if issubclass(type__param, GraphQLType): return type__param() # type: ignore
                is_scalar_val = False
                for test_types_s, _ in GraphQLTypeMapper.scalar_map:
                    for test_type_s in test_types_s:
                        if test_type_s is None: continue
                        if issubclass(type__param, test_type_s): is_scalar_val = True; break
                    if is_scalar_val: break
                if is_scalar_val: return self.map_to_scalar(type__param)
                if issubclass(type__param, enum.Enum): return self.map_to_enum(type__param)
                if is_interface(type__param, self.schema): return self.map_to_interface(type__param)
                if self.as_input: return self.map_to_input(type__param)
                else: return self.map_to_object(type__param)
            if isinstance(type__param, GraphQLType): return type__param
            return None
        value = _map_inner(type_)
        if value is None and type_ in GraphQLTypeMapper._get_scalar_map_direct(): # type: ignore
            value = GraphQLTypeMapper._get_scalar_map_direct()[type_] # type: ignore
        if self.validate(value): # type: ignore
            self.registry[generic_key] = value
            if isinstance(value, collections.abc.Hashable):
                python_type_to_register = _get_actual_type_from_type_hint(type_) or type_
                is_problematic = False
                if python_type_to_register is Optional or python_type_to_register is Union or python_type_to_register is List: is_problematic = True
                else:
                    origin = get_origin(python_type_to_register)
                    if origin is not None and (origin is Union or origin is List): is_problematic = True
                if not is_problematic and hasattr(python_type_to_register, '__name__') and python_type_to_register.__name__ == "Optional": is_problematic = True
                if is_problematic and isinstance(value, (GraphQLObjectType, GraphQLInterfaceType, GraphQLInputObjectType, GraphQLEnumType)): pass
                else: self.reverse_registry[value] = python_type_to_register
            return value
        # print(f"[Map] map({type_.__name__ if hasattr(type_,'__name__') else type_}) VALIDATE FAILED or value is None. Value: {value}, Validate result: {self.validate(value) if value else 'N/A'}. Returning None.")
        return None

    def register(self, python_type: Type, key: str, value: GraphQLType):
        if self.validate(value):
            self.registry[key] = value
            if isinstance(value, collections.abc.Hashable):
                is_problematic_for_reverse_registry = False
                if python_type is Optional or python_type is Union or python_type is List: is_problematic_for_reverse_registry = True
                else:
                    origin = get_origin(python_type)
                    if origin is not None and (origin is Union or origin is List): is_problematic_for_reverse_registry = True
                if not is_problematic_for_reverse_registry and hasattr(python_type, '__name__') and python_type.__name__ == "Optional": is_problematic_for_reverse_registry = True
                if is_problematic_for_reverse_registry and isinstance(value, (GraphQLObjectType, GraphQLInterfaceType, GraphQLInputObjectType, GraphQLEnumType)): pass
                else: self.reverse_registry[value] = python_type

    def validate(self, type_: GraphQLType, evaluate=False) -> bool:
        if not type_: return False;
        if not isinstance(type_, GraphQLType): return False
        current_type_ = type_
        if isinstance(current_type_, GraphQLNonNull): current_type_ = current_type_.of_type
        if self.as_input and not is_input_type(current_type_): return False
        if isinstance(current_type_, GraphQLObjectType):
            if evaluate:
                try:
                    if len(current_type_.fields) == 0: return False
                except Exception: return False
            elif not callable(current_type_._fields) and len(current_type_._fields) == 0: return False # type: ignore
        return True

GraphQLTypeMapper._scalar_map_direct_cache = None
GraphQLTypeMapper.scalar_map_quick_lookup = GraphQLTypeMapper._get_scalar_map_direct() # type: ignore

def _get_actual_type_from_type_hint(type_: Type) -> Type[Any] | None:
    origin_type = get_origin(type_)
    if origin_type is Union:
        args = typing_inspect.get_args(type_, evaluate=True)
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1: return non_none_args[0]
        elif len(non_none_args) > 1: return type_
    return origin_type if origin_type else type_

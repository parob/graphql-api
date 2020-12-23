from typing import Type, get_type_hints
import typing_inspect

from graphql.type.definition import \
    GraphQLType, \
    GraphQLObjectType, \
    GraphQLField, \
    GraphQLInputField, \
    GraphQLNonNull

from graphql_api.utils import to_camel_case


def type_is_dataclass(_class: Type):
    try:
        from dataclasses import is_dataclass
    except ImportError:
        return False
    else:
        return is_dataclass(_class)


def type_from_dataclass(_class: Type, mapper) -> GraphQLType:
    dataclass_fields = dict(_class.__dataclass_fields__)
    dataclass_types = get_type_hints(_class)
    base_type: GraphQLObjectType = mapper.map(_class, use_graphql_type=False)

    # Remove any modifiers
    while hasattr(base_type, 'of_type'):
        base_type = base_type.of_type

    if mapper.as_input:
        return base_type

    exclude_fields = _class.graphql_exclude_fields() \
        if hasattr(_class, 'graphql_exclude_fields') else []

    properties = {
        name: (field, dataclass_types.get(name))
        for name, field in dataclass_fields.items()
        if not name.startswith("_") and name not in exclude_fields
    }

    def local_fields_callback():
        local_type = base_type
        local_properties = properties
        local_mapper = mapper

        # noinspection PyProtectedMember
        local_type_fields = local_type._fields

        def fields_callback():
            local_fields = {}

            for prop_name, (field, field_type) in local_properties.items():

                def local_resolver():
                    local_prop_name = prop_name

                    def resolver(
                        self,
                        info=None,
                        context=None,
                        *args,
                        **kwargs
                    ):
                        return getattr(self, local_prop_name)
                    return resolver

                type_: GraphQLType = local_mapper.map(type_=field_type)

                nullable = False

                if typing_inspect.is_union_type(field_type):
                    union_args = typing_inspect.get_args(
                        field_type,
                        evaluate=True
                    )
                    if type(None) in union_args:
                        nullable = True

                if not nullable:
                    type_: GraphQLType = GraphQLNonNull(type_)

                if local_mapper.as_input:
                    field = GraphQLInputField(type_=type_)
                else:
                    field = GraphQLField(type_=type_, resolve=local_resolver())

                local_fields[to_camel_case(prop_name)] = field

            if local_type_fields:
                try:
                    fields_ = local_type_fields()
                    for name, field in fields_.items():
                        if name not in local_fields:
                            local_fields[name] = field
                except AssertionError:
                    pass

            return local_fields
        return fields_callback

    base_type._fields = local_fields_callback()
    return base_type

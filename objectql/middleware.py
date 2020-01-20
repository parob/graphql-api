import enum

from graphql import GraphQLObjectType, GraphQLNonNull

from objectql.context import ObjectQLContext
from objectql.utils import to_snake_case


def middleware_local_proxy(next):
    value = next()

    # Compatibility with LocalProxy from Werkzeug
    try:
        if hasattr(value, '_get_current_object'):
            value = value._get_current_object()

    except Exception:
        pass

    if isinstance(value, Exception):
        raise value

    return value


def middleware_adapt_enum(next):
    """
    GraphQL middleware, by default enums return the value
    """
    value = next()
    if isinstance(value, enum.Enum):
        value = value.value

    return value


def middleware_request_context(next, context: ObjectQLContext):
    from objectql.schema import ObjectQLRequestContext

    info = context.resolve_args.get('info')
    args = context.resolve_args.get('args')

    if info.context.request:
        return next()

    args = {to_snake_case(key): arg for key, arg in args.items()}
    graphql_request = ObjectQLRequestContext(args=args, info=info)

    info.context.request = graphql_request

    try:
        value = next()
    finally:
        info.context.request = None

    return value


def middleware_field_context(next, context: ObjectQLContext):
    from objectql.schema import ObjectQLFieldContext

    info = context.resolve_args.get('info')

    field_meta = info.context.meta.get(
        (info.parent_type.name, to_snake_case(info.field_name)),
        {}
    )
    return_type = info.return_type

    if field_meta is None:
        field_meta = {}

    if return_type and isinstance(return_type, GraphQLNonNull):
        return_type = return_type.of_type

    kwargs = {}
    if return_type and isinstance(return_type, GraphQLObjectType):
        sub_loc = info.field_nodes[0].selection_set.loc
        kwargs['query'] = sub_loc.source.body[sub_loc.start:sub_loc.end]

    info.context.field = ObjectQLFieldContext(meta=field_meta, **kwargs)

    try:
        value = next()
    finally:
        info.context.field = None

    return value

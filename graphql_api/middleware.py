import asyncio
import enum
import inspect
import sys
import traceback

from graphql import GraphQLNonNull, GraphQLObjectType, TypeKind

from graphql_api.error import GraphQLError
from graphql_api.mapper import GraphQLMetaKey
from graphql_api.utils import to_snake_case


def middleware_catch_exception(next_, root, info, **args):
    """
    GraphQL middleware, unwrap the LocalProxy if using Werkzeug.
    """
    try:
        value = next_(root, info, **args)
    except Exception as err:
        from graphql_api.executor import ErrorProtectionExecutionContext

        field_meta = info.context.field.meta
        if field_meta.get(GraphQLMetaKey.error_protection) is not None:
            setattr(
                err,
                ErrorProtectionExecutionContext.error_protection,
                field_meta.get(GraphQLMetaKey.error_protection),
            )

        return_type = info.return_type
        ignored = isinstance(return_type, GraphQLNonNull)

        print(
            f"GraphQLField '{info.field_name}' on '{info.parent_type.name}' "
            f"resolver {'(ignored) ' if ignored else ''}Exception: {err} ",
            file=sys.stderr,
        )
        traceback.print_exc()
        raise err

    return value


def middleware_local_proxy(next_, root, info, **args):
    """
    GraphQL middleware, unwrap the LocalProxy if using Werkzeug.
    """
    value = next_(root, info, **args)
    try:
        if hasattr(value, "_get_current_object"):
            # noinspection PyProtectedMember
            value = value._get_current_object()
    except GraphQLError:
        # hasattr calls getattr and remote.getattr() can raise a GraphQLError if
        # the object doesn't have the attr
        pass

    if isinstance(value, Exception):
        raise value

    return value


def middleware_call_coroutine(next_, root, info, **args):
    """
    GraphQL middleware, call coroutine
    """
    value = next_(root, info, **args)
    if inspect.iscoroutine(value):
        value = asyncio.run(value)

    return value


def middleware_adapt_enum(next_, root, info, **args):
    """
    GraphQL middleware, by default enums return the value
    """
    value = next_(root, info, **args)
    if isinstance(value, enum.Enum):
        if isinstance(value, TypeKind):
            value = value
        else:
            value = value.value

    return value


def middleware_request_context(next_, root, info, **args):
    """
    GraphQL middleware, add the GraphQLRequestContext
    """
    from graphql_api.api import GraphQLRequestContext

    if info.context.request:
        return next_(root, info, **args)

    graphql_request = GraphQLRequestContext(
        args={to_snake_case(key): arg for key, arg in args.items()}, info=info
    )

    info.context.request = graphql_request

    try:
        value = next_(root, info, **args)
    finally:
        info.context.request = None

    return value


def middleware_field_context(next_, root, info, **args):
    """
    GraphQL middleware, add the GraphQLFieldContext
    """
    from graphql_api.api import GraphQLFieldContext

    field_meta = info.context.meta.get(
        (info.parent_type.name, to_snake_case(info.field_name)), {}
    )
    return_type = info.return_type

    if field_meta is None:
        field_meta = {}

    if return_type and isinstance(return_type, GraphQLNonNull):
        return_type = return_type.of_type

    kwargs = {}
    if return_type and isinstance(return_type, GraphQLObjectType):
        sub_loc = info.field_nodes[0].selection_set.loc
        kwargs["query"] = sub_loc.source.body[sub_loc.start: sub_loc.end]

    info.context.field = GraphQLFieldContext(meta=field_meta, **kwargs)

    try:
        value = next_(root, info, **args)
    finally:
        info.context.field = None

    return value

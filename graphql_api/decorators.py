from graphql_api.api import decorator


def field(meta=None, mutable=False):
    _type = "query"
    if mutable:
        _type = "mutation"

    return decorator(None, meta, _type=_type)


def type(meta=None, abstract=False, interface=False):
    _type = "object"
    if interface:
        _type = "interface"
    elif abstract:
        _type = "abstract"

    return decorator(None, meta, _type=_type)

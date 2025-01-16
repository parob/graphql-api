from graphql_api.api import decorator


def field(meta=None, mutable=False, directives=None):
    _type = "query"
    if mutable:
        _type = "mutation"

    return decorator(None, meta, type=_type, directives=directives)


def type(meta=None, abstract=False, interface=False, root=False, directives=None):
    _type = "object"
    if interface:
        _type = "interface"
    elif abstract:
        _type = "abstract"

    return decorator(None, meta, type=_type, root=root, directives=directives)

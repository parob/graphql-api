from graphql_api.api import build_decorator


def field(meta=None, mutable=False, directives=None):
    return build_decorator(None, meta, type="field", mutable=mutable, directives=directives)


def type(meta=None, abstract=False, interface=False, directives=None):
    return build_decorator(None, meta, type="object", abstract=abstract, interface=interface, directives=directives)

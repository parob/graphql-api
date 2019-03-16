def object_decorator_factory(query_type):

    def decorator(meta=None):
        value = None

        if not meta:
            meta = {}

        if callable(meta):
            value = meta
            meta = {}

        def _decorator(f):
            f.graphql = True
            f.meta = meta
            f.type = query_type
            f.defined_on = f
            return f

        # See if we're being called as @decorator or @decorator().
        if value:
            return _decorator(value)

        # We're called as @decorator without parens.
        return _decorator

    return decorator


query = object_decorator_factory("query")
mutation = object_decorator_factory("mutation")
interface = object_decorator_factory("interface")
abstract = object_decorator_factory("abstract")

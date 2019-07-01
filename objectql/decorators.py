def object_decorator_factory(query_type, schema=False):

    def decorator(schema, meta=None):
        value = None

        if not meta:
            meta = {}

        if callable(meta):
            value = meta
            meta = {}

        def _decorator(schema, f):
            f.graphql = True
            f.defined_on = f

            api = {
                "defined_on": f,
                "meta": meta,
                "type": query_type,
                "schema": schema
            }

            if not hasattr(f, "schemas"):
                f.schemas = {}

            f.schemas[schema] = api
            return f

        # See if we're being called as @decorator or @decorator().
        if value:
            return _decorator(schema, value)

        # We're called as @decorator without parens.
        return lambda f: _decorator(schema, f)

    if schema:
        return decorator

    return lambda value: decorator(None, value)


query = object_decorator_factory("query")
mutation = object_decorator_factory("mutation")
interface = object_decorator_factory("interface")
abstract = object_decorator_factory("abstract")

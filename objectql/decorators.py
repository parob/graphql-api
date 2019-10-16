from typing import Callable


def decorator_factory(type_):

    def decorator(cls_or_schema, method=None):
        method = None

        def decorator_(schema, f: Callable):
            f.graphql = True
            f.defined_on = f

            api = {
                "defined_on": f,
                "meta": {},
                "type": type_,
                "schema": schema
            }

            if not hasattr(f, "schemas"):
                f.schemas = {}

            if hasattr(f, "schemas"):
                f.schemas[schema] = api

            return f

        # # See if we're being called as @decorator or @decorator().
        # if func:
        #     return decorator_(cls_or_schema, func)

        # We're called as @decorator without parens.
        return lambda f: decorator_(cls_or_schema, method)

    return decorator


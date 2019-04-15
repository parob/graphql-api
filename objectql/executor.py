import inspect

from typing import Any, List, Dict, Callable

from graphql import graphql

from graphql.execution import ExecutionResult
from graphql.type.schema import GraphQLSchema

from objectql.context import ObjectQLContext
from objectql.middleware import \
    middleware_field_context, \
    middleware_request_context, \
    middleware_local_proxy


class ObjectQLBaseExecutor:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validate()

    def validate(self):
        pass

    def execute(
        self,
        query,
        variable_values=None,
        operation_name=None
    ) -> ExecutionResult:
        pass


class ObjectQLExecutor(ObjectQLBaseExecutor):

    def __init__(
        self,
        schema: GraphQLSchema,
        meta: Dict = None,
        root: Any = None,
        middleware: List[Callable[[Callable, ObjectQLContext], Any]] = None,
        middleware_on_introspection: bool = False
    ):
        super().__init__()

        if meta is None:
            meta = {}

        if middleware is None:
            middleware = []

        middleware.insert(0, middleware_field_context)
        middleware.insert(0, middleware_request_context)
        middleware.insert(0, middleware_local_proxy)

        self.meta = meta
        self.schema = schema
        self.middleware = middleware
        self.root = root
        self.middleware_on_introspection = middleware_on_introspection

    def execute(
        self,
        query,
        variables=None,
        operation_name=None,
        root=None,
        context=None
    ) -> ExecutionResult:

        context = ObjectQLContext(
            schema=self.schema,
            meta=self.meta,
            executor=self
        )

        if root is None:
            root = self.root

        if context is None:
            context = self.context

        value = graphql(
            self.schema,
            query,
            context=context,
            variables=variables,
            operation_name=operation_name,
            middleware=self.adapt_middleware(self.middleware),
            root=root
        )
        return value

    @staticmethod
    def adapt_middleware(
        middleware,
        middleware_on_introspection: bool = False
    ):

        def simplify(_middleware: Callable[[Callable, ObjectQLContext], Any]):
            def graphql_middleware(next, root, info, **args):
                kwargs = {}
                if "context" in inspect.signature(_middleware).parameters:
                    context: ObjectQLContext = info.context
                    kwargs["context"] = context
                    context.resolve_args['root'] = root
                    context.resolve_args['info'] = info
                    context.resolve_args['args'] = args

                return _middleware(lambda: next(root, info, **args), **kwargs)

            return graphql_middleware

        def skip_if_introspection(_middleware):
            def middleware_with_skip(next, root, info, **args):
                skip = info.operation.name and \
                       info.operation.name.value == 'IntrospectionQuery'
                if skip:
                    return next(root, info, **args)
                return _middleware(next, root, info, **args)

            return middleware_with_skip

        adapters = [simplify]

        if middleware_on_introspection is False:
            adapters.append(skip_if_introspection)

        adapted_middleware = []

        for middleware in reversed(middleware):
            for adapter in adapters:
                middleware = adapter(middleware)
            adapted_middleware.append(middleware)

        return adapted_middleware

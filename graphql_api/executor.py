from typing import Any, List, Dict

from graphql import (
    graphql,
    graphql_sync,
    ExecutionContext,
    GraphQLError,
    GraphQLOutputType,
)

from graphql.execution import ExecutionResult
from graphql.type.schema import GraphQLSchema

from graphql_api.context import GraphQLContext
from graphql_api.middleware import (
    middleware_field_context,
    middleware_request_context,
    middleware_local_proxy,
    middleware_adapt_enum,
    middleware_catch_exception,
    middleware_call_coroutine,
    GraphQLMiddleware,
)


class GraphQLBaseExecutor:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validate()

    def validate(self):
        pass

    def execute(self, query, variables=None, operation_name=None) -> ExecutionResult:
        pass

    async def execute_async(
        self, query, variables=None, operation_name=None
    ) -> ExecutionResult:
        pass


class ErrorProtectionExecutionContext(ExecutionContext):
    default_error_protection = True

    error_protection = "ERROR_PROTECTION"

    def handle_field_error(
        self,
        error: GraphQLError,
        return_type: GraphQLOutputType,
    ) -> None:
        error_protection = self.default_error_protection
        original_error = error.original_error
        if hasattr(error, self.error_protection):
            error_protection = getattr(error, self.error_protection)

        elif hasattr(original_error, self.error_protection):
            error_protection = getattr(original_error, self.error_protection)

        if not error_protection:
            raise error.original_error

        return super().handle_field_error(error=error, return_type=return_type)


class NoErrorProtectionExecutionContext(ErrorProtectionExecutionContext):
    default_error_protection = False


class GraphQLExecutor(GraphQLBaseExecutor):
    def __init__(
        self,
        schema: GraphQLSchema,
        meta: Dict = None,
        root_value: Any = None,
        middleware: List[GraphQLMiddleware] = None,
        ignore_middleware_during_introspection: bool = True,
        error_protection: bool = True,
    ):
        super().__init__()

        if meta is None:
            meta = {}

        if middleware is None:
            middleware = []

        self.meta = meta
        self.schema = schema
        self.middleware = [
            middleware_call_coroutine,
            middleware_adapt_enum,
            middleware_local_proxy,
            middleware_request_context,
            middleware_field_context,
            middleware_catch_exception,
        ] + middleware
        self.root_value = root_value
        self.ignore_middleware_during_introspection = (
            ignore_middleware_during_introspection
        )
        self.execution_context_class = (
            ErrorProtectionExecutionContext
            if error_protection
            else NoErrorProtectionExecutionContext
        )

    def execute(
        self, query, variables=None, operation_name=None, root_value=None
    ) -> ExecutionResult:
        context = GraphQLContext(schema=self.schema, meta=self.meta, executor=self)

        if root_value is None:
            root_value = self.root_value

        value = graphql_sync(
            self.schema,
            query,
            context_value=context,
            variable_values=variables,
            operation_name=operation_name,
            middleware=adapt_middleware(self.middleware),
            root_value=root_value,
            execution_context_class=self.execution_context_class,
        )
        return value

    async def execute_async(
        self, query, variables=None, operation_name=None, root_value=None
    ) -> ExecutionResult:
        context = GraphQLContext(schema=self.schema, meta=self.meta, executor=self)

        if root_value is None:
            root_value = self.root_value

        value = await graphql(
            self.schema,
            query,
            context_value=context,
            variable_values=variables,
            operation_name=operation_name,
            middleware=adapt_middleware(self.middleware),
            root_value=root_value,
            execution_context_class=self.execution_context_class,
        )
        return value


def adapt_middleware(middleware, ignore_middleware_during_introspection: bool = True):
    adapters = [adapter_middleware_simplify_args]

    if ignore_middleware_during_introspection:
        adapters.append(adapter_ignore_middleware_during_introspection)

    adapted_middleware = []

    for middleware in reversed(middleware):
        for adapter in adapters:
            middleware = adapter(middleware)
        adapted_middleware.append(middleware)

    return adapted_middleware


def adapter_ignore_middleware_during_introspection(middleware: GraphQLMiddleware):
    def middleware_with_skip(next, root, info, **args):
        skip = info.operation.name and info.operation.name.value == "IntrospectionQuery"
        if skip:
            return next(root, info, **args)
        return middleware(next, root, info, **args)

    return middleware_with_skip


def adapter_middleware_simplify_args(middleware: GraphQLMiddleware):
    def graphql_middleware(next, root, info, **args):
        kwargs = {}
        context: GraphQLContext = info.context
        kwargs["context"] = context
        context.resolve_args["root"] = root
        context.resolve_args["info"] = info
        context.resolve_args["args"] = args

        return middleware(lambda: next(root, info, **args), context)

    return graphql_middleware

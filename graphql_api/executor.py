from functools import lru_cache
from inspect import isawaitable
from typing import Any, Dict, Optional, List, Callable, AsyncIterator, Tuple

from graphql import (
    GraphQLError,
    GraphQLOutputType,
    execute,
    execute_sync,
    subscribe,
    parse,
    validate,
    validate_schema,
)
from graphql.execution import ExecutionResult
from graphql.execution.executor import Executor
from graphql.execution.middleware import MiddlewareManager
from graphql.pyutils import Path
from graphql.language import DocumentNode
from graphql.type.schema import GraphQLSchema

from graphql_api.context import GraphQLContext
from graphql_api.middleware import middleware_combined


class GraphQLBaseExecutor:
    """
    A base class for GraphQL executors, placeholders for validation and execution.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validate()

    def validate(self):
        """
        Validate the executor. Override this method in subclasses if needed.
        """
        pass

    def execute(self, query, variables=None, operation_name=None) -> ExecutionResult:
        """
        Synchronous execution of a GraphQL query.
        Override in subclasses to implement custom logic.
        """
        raise NotImplementedError

    async def execute_async(
        self, query, variables=None, operation_name=None
    ) -> ExecutionResult:
        """
        Asynchronous execution of a GraphQL query.
        Override in subclasses to implement custom logic.
        """
        raise NotImplementedError


class ErrorProtectionExecutionContext(Executor):
    """
    A custom graphql-core Executor that can selectively suppress or raise errors
    based on an 'error_protection' attribute in the error or its original error.
    """

    # Default to True, meaning errors are protected by default (not raised directly).
    default_error_protection = True
    error_protection = "ERROR_PROTECTION"

    def handle_field_error(
        self,
        raw_error: Exception,
        return_type: GraphQLOutputType,
        field_details_list: Any,
        path: Path,
    ) -> None:
        """
        Intercept field errors to decide whether to raise or suppress them based on the
        'error_protection' attribute, either on the error or its original error.

        graphql-core passes the error as raised. That is usually the resolver's own
        exception, but it can be a GraphQLError that wraps one (e.g. from a nested
        executor), so the flag is looked up on both.
        """
        error_protection = self.default_error_protection
        original_error = (
            raw_error.original_error if isinstance(raw_error, GraphQLError) else None
        )

        # Check if this error or its original error has a custom error_protection flag
        if hasattr(raw_error, self.error_protection):
            error_protection = getattr(raw_error, self.error_protection)
        elif hasattr(original_error, self.error_protection):
            error_protection = getattr(original_error, self.error_protection)

        # If error protection is disabled, re-raise the original error
        if not error_protection:
            raise original_error if original_error is not None else raw_error

        # Otherwise, let graphql-core locate and collect the error.
        return super().handle_field_error(
            raw_error, return_type, field_details_list, path
        )


class NoErrorProtectionExecutionContext(ErrorProtectionExecutionContext):
    """
    A variant of the ErrorProtectionExecutionContext that disables
    error protection by default, meaning all errors are raised.
    """

    default_error_protection = False


class GraphQLExecutor(GraphQLBaseExecutor):
    """
    A GraphQL executor that manages the schema, context, middleware, and error handling
    for executing GraphQL queries and mutations, both synchronously and asynchronously.
    """

    def __init__(
        self,
        schema: GraphQLSchema,
        meta: Optional[Dict] = None,
        root_value: Any = None,
        middleware: Optional[List[Callable]] = None,
        error_protection: bool = True,
    ):
        """
        :param schema: The GraphQLSchema instance used for validation and execution.
        :param meta: A dictionary of metadata that can be accessed within resolvers.
        :param root_value: The root value passed to the resolver.
        :param middleware: A list of middleware functions to process incoming requests.
        :param error_protection: Whether to protect (suppress) errors by default.
        """
        super().__init__()
        self.schema = schema
        self.meta = meta if meta is not None else {}
        self.root_value = root_value

        # The six built-in middleware are merged into one function: they run
        # on every field resolution, and separate functions cost five extra
        # call frames per field. Custom middleware stay innermost (closest to
        # the resolver), exactly as with the individual built-ins.
        self.middleware = [
            *(middleware if middleware else []),
            middleware_combined,
        ]

        # Build the middleware chain once. graphql-core constructs a fresh
        # MiddlewareManager per execution when handed a raw list, throwing away
        # its per-resolver wrapped-chain cache every request. Middleware here
        # holds no request state (that lives on info.context), so one manager
        # can serve every execution.
        self._middleware_manager = MiddlewareManager(*self.middleware)

        # Set the custom Executor class to handle error protection
        self.executor_class = (
            ErrorProtectionExecutionContext
            if error_protection
            else NoErrorProtectionExecutionContext
        )

        # The schema is fixed for the lifetime of this executor, so validate it
        # once here instead of on every execute() call.
        self._schema_validation_errors = validate_schema(schema)

        # Query parse + validation depend only on the (fixed) schema and the
        # query string, so cache them per executor. lru_cache is thread-safe
        # and does not cache raised exceptions (syntax errors re-raise).
        @lru_cache(maxsize=256)
        def _parse_and_validate(
            query: str,
        ) -> Tuple[DocumentNode, Tuple[GraphQLError, ...]]:
            document = parse(query)
            return document, tuple(validate(schema, document))

        self._parse_and_validate = _parse_and_validate

    def _prepare(
        self, query
    ) -> Tuple[Optional[DocumentNode], Optional[List[GraphQLError]]]:
        """
        Parse and validate a query using the per-executor cache, mirroring the
        early-exit behaviour of graphql-core's graphql()/graphql_sync().
        Returns (document, errors); errors is non-None when execution must not
        proceed.
        """
        if self._schema_validation_errors:
            return None, list(self._schema_validation_errors)
        try:
            document, validation_errors = self._parse_and_validate(query)
        except GraphQLError as error:
            return None, [error]
        if validation_errors:
            return None, list(validation_errors)
        return document, None

    def execute(
        self, query, variables=None, operation_name=None, root_value=None
    ) -> ExecutionResult:
        """
        Synchronously execute a GraphQL query.
        """
        # Build the context shared by resolvers
        context = GraphQLContext(
            schema=self.schema, meta=self.meta, executor=self)

        if root_value is None:
            root_value = self.root_value

        document, errors = self._prepare(query)
        if errors is not None or document is None:
            return ExecutionResult(data=None, errors=errors)

        # Execute synchronously with our custom adapters and context
        result = execute_sync(
            schema=self.schema,
            document=document,
            context_value=context,
            variable_values=variables,
            operation_name=operation_name,
            middleware=self._middleware_manager,
            root_value=root_value,
            executor_class=self.executor_class,
        )
        return result

    async def execute_async(
        self, query, variables=None, operation_name=None, root_value=None
    ) -> ExecutionResult:
        """
        Asynchronously execute a GraphQL query.
        """
        context = GraphQLContext(
            schema=self.schema, meta=self.meta, executor=self)
        if root_value is None:
            root_value = self.root_value

        document, errors = self._prepare(query)
        if errors is not None or document is None:
            return ExecutionResult(data=None, errors=errors)

        result = execute(
            schema=self.schema,
            document=document,
            context_value=context,
            variable_values=variables,
            operation_name=operation_name,
            middleware=self._middleware_manager,
            root_value=root_value,
            executor_class=self.executor_class,
        )
        if isawaitable(result):
            result = await result
        return result

    async def subscribe(
        self, query: str, variables=None, operation_name=None, root_value=None
    ) -> AsyncIterator[ExecutionResult]:
        """
        Start a GraphQL subscription and return an async iterator of results.
        """
        context = GraphQLContext(
            schema=self.schema, meta=self.meta, executor=self)
        if root_value is None:
            root_value = self.root_value
        # graphql-core subscribe expects a parsed document
        document = parse(query)
        # Use the same middleware and execution context where applicable
        async_iter = subscribe(
            schema=self.schema,
            document=document,
            variable_values=variables,
            operation_name=operation_name,
            context_value=context,
            root_value=root_value,
        )
        # graphql-core >= 3.3 returns the result directly when it can.
        if isawaitable(async_iter):
            async_iter = await async_iter
        return async_iter  # type: ignore

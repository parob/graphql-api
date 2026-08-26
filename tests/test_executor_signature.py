"""The error path must survive graphql-core changing under us.

`ErrorProtectionExecutionContext` overrides `handle_field_error`, which
graphql-core calls positionally from inside the executor. graphql-core added a
`path` argument to it in 3.2.8; the override kept its three-argument shape, and
the result was that **every** field error became a `TypeError` raised from
inside the executor. A resolver raising `ValueError("title is required")` came
back to the caller as a crash with no message — the one thing an error path
must never do.

It went unnoticed because this library's own environment resolves an older
graphql-core than its consumers do, so the existing error tests all pass here
and fail there. Asserting against a pinned signature would repeat that mistake,
so these tests ask the *installed* graphql-core what it expects and check the
override against that.
"""

from __future__ import annotations

import inspect

from graphql import GraphQLError, GraphQLInt
from graphql.execution.execute import ExecutionContext
from graphql.pyutils import Path

from graphql_api.api import GraphQLAPI
from graphql_api.executor import (
    ErrorProtectionExecutionContext,
    NoErrorProtectionExecutionContext,
)


def _accepted_arity(func) -> int:
    """How many positional arguments this method takes, `self` excluded."""
    parameters = [
        p for name, p in inspect.signature(func).parameters.items()
        if name != "self"
    ]
    return sum(
        1 for p in parameters
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    )


class TestHandleFieldErrorSignature:
    def test_override_accepts_everything_graphql_core_passes(self) -> None:
        """The override must be callable however the installed version calls it."""
        expected = _accepted_arity(ExecutionContext.handle_field_error)
        override = inspect.signature(
            ErrorProtectionExecutionContext.handle_field_error
        )
        # Either the arities match, or the override absorbs the difference.
        absorbs = any(
            p.kind is p.VAR_POSITIONAL for p in override.parameters.values()
        )
        assert absorbs or _accepted_arity(
            ErrorProtectionExecutionContext.handle_field_error
        ) == expected, (
            f"graphql-core passes {expected} positional argument(s) to "
            f"handle_field_error; the override does not accept them"
        )

    def test_survives_being_called_the_way_the_executor_calls_it(self) -> None:
        """A direct call with graphql-core's own argument list.

        This is the exact call that was raising TypeError in production.
        """
        context = ErrorProtectionExecutionContext.__new__(
            ErrorProtectionExecutionContext
        )
        error = GraphQLError("boom", original_error=ValueError("boom"))
        args = [error, GraphQLInt]
        if _accepted_arity(ExecutionContext.handle_field_error) > 2:
            # graphql-core >= 3.2.8 also passes the field's path.
            args.append(Path(None, "field", None))

        # Nullable return type, so the error is collected rather than re-raised;
        # the point is only that the call itself is well-formed.
        context.errors = []
        try:
            context.handle_field_error(*args)
        except TypeError as exc:  # pragma: no cover - this is the regression
            raise AssertionError(
                f"handle_field_error rejected graphql-core's own call: {exc}"
            ) from exc
        except Exception:
            # Any GraphQL-level outcome is fine; a TypeError is not.
            pass

    def test_the_no_protection_variant_inherits_the_same_shape(self) -> None:
        assert (
            NoErrorProtectionExecutionContext.handle_field_error
            is ErrorProtectionExecutionContext.handle_field_error
        )


class TestResolverErrorsReachTheCaller:
    def test_a_raising_resolver_produces_a_graphql_error_not_a_crash(self) -> None:
        """End to end: the shape every consumer actually depends on.

        A validating resolver — "status must be one of …" — has to come back as
        a GraphQL error carrying its message, or callers cannot tell a bad
        argument from a broken server.
        """
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Root:
            @api.field
            def set_status(self, status: str) -> bool:
                raise ValueError(f"status must be one of ['open', 'closed'], got {status!r}")

        result = api.execute('query { setStatus(status: "banana") }')

        assert result.errors, "the resolver's error never reached the caller"
        assert "status must be one of" in str(result.errors[0])

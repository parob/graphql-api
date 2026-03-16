# GraphQL-API

> Compatibility note: `AGENTS.md` and `CLAUDE.md` are both supported in this repo.
> Keep these files identical. Any change in one must be mirrored in the other.

Code-first, decorator-based GraphQL framework for Python. Published on [PyPI](https://pypi.org/project/graphql-api/).

## Project Structure

| Directory | Description |
|-----------|-------------|
| `graphql_api/` | Main package source |
| `tests/` | Test suite (34 files, pytest) |
| `docs/` | Sphinx documentation |

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linter
uv run flake8 graphql_api tests
```

## Key Patterns

- **Automatic snake_case to camelCase**: All Python field names, arguments, and dataclass/Pydantic fields are auto-converted to camelCase in GraphQL. Input arguments are converted back to snake_case. Conversion lives in `graphql_api/utils.py` (`to_camel_case()`, `to_snake_case()`)
- `@field` marks a method as a query; `@field(mutable=True)` makes it a mutation; `AsyncGenerator` return type or `subscription=True` makes it a subscription
- Python types auto-map: `str`→String, `int`→Int, `bool`→Boolean, `float`→Float, `UUID`→UUID scalar, `datetime`→DateTime, `Optional[T]`→nullable, `List[T]`→list, dataclasses/Pydantic models→object types, enums→enum types
- Schema setup: `GraphQLAPI(query_type=Q, mutation_type=M, subscription_type=S)` or legacy `root_type=Root`

## Releasing

See the ecosystem-level `CLAUDE.md` in the parent workspace for the full release process. In short:

```bash
# Ensure CI is green on main, then:
git tag X.Y.Z
git push origin X.Y.Z
```

CI publishes to PyPI and creates a GitHub Release automatically.

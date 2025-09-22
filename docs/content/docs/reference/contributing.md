---
title: "Contributing"
weight: 3
description: >
  How to contribute to the graphql-api project
---

# Contributing to GraphQL API

Thank you for your interest in contributing to `graphql-api`! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

---

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and constructive in all interactions.

### Our Standards

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

---

## Getting Started

### Prerequisites

- Python 3.11 or newer
- Git
- A GitHub account

### Areas for Contribution

We welcome contributions in several areas:

- **Bug fixes**: Fix issues reported in GitHub Issues
- **Features**: Implement new functionality
- **Documentation**: Improve or expand documentation
- **Tests**: Add test coverage or improve existing tests
- **Performance**: Optimize performance bottlenecks
- **Examples**: Create new examples or improve existing ones

---

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/graphql-api.git
cd graphql-api

# Add the original repository as upstream
git remote add upstream https://github.com/parob/graphql-api.git
```

### 2. Set Up Development Environment

```bash
# Install dependencies using uv (recommended)
pip install uv
uv sync --all-extras

# Alternatively, use pip
pip install -e .[dev]
```

### 3. Verify Setup

```bash
# Run tests to ensure everything is working
python -m pytest

# Run linting
flake8

# Check types (if using a type checker)
mypy graphql_api
```

---

## Making Changes

### Branching Strategy

1. Create a feature branch from `main`:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/your-feature-name
   ```

2. Make your changes in small, logical commits
3. Write clear commit messages

### Coding Standards

#### Python Style

- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return values
- Maximum line length: 170 characters (as configured in pyproject.toml)
- Use descriptive variable and function names

#### Code Examples

**Good:**
```python
def resolve_user_posts(
    self,
    user_id: int,
    published_only: bool = False
) -> List[Post]:
    """Resolve posts for a given user.

    Args:
        user_id: The ID of the user
        published_only: Whether to filter for published posts only

    Returns:
        List of posts for the user
    """
    posts = get_posts_by_user_id(user_id)
    if published_only:
        posts = [p for p in posts if p.is_published]
    return posts
```

**Avoid:**
```python
def get_posts(uid, pub=False):  # No type hints, unclear names
    p = get_posts(uid)
    if pub:
        p = [x for x in p if x.pub]  # Unclear variable names
    return p
```

#### Documentation Strings

- Use docstrings for all public functions, classes, and methods
- Follow Google or NumPy docstring format
- Include parameter types and descriptions
- Include return value description
- Add examples for complex functions

### Architecture Guidelines

#### Type System

- Leverage Python's type system extensively
- Use Pydantic models for data validation when appropriate
- Support both dataclasses and Pydantic models
- Maintain compatibility with standard Python types

#### GraphQL Schema Design

- Follow GraphQL best practices
- Support both unified and explicit schema approaches
- Maintain backwards compatibility when possible
- Use descriptive field and type names

#### Error Handling

- Use `GraphQLError` for GraphQL-specific errors
- Provide clear, actionable error messages
- Include relevant context in error messages
- Handle edge cases gracefully

---

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=graphql_api

# Run specific test file
python -m pytest tests/test_api.py

# Run specific test
python -m pytest tests/test_api.py::TestGraphQLAPI::test_basic_query
```

### Writing Tests

#### Test Structure

- Put tests in the `tests/` directory
- Use descriptive test names that explain what is being tested
- Group related tests in classes
- Use fixtures for common setup

#### Test Examples

```python
import pytest
from graphql_api.api import GraphQLAPI

class TestGraphQLAPI:
    """Tests for basic GraphQLAPI functionality."""

    def test_simple_query_execution(self):
        """Test that a simple query executes successfully."""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def hello(self) -> str:
                return "world"

        result = api.execute('{ hello }')
        assert result.data == {"hello": "world"}
        assert result.errors is None

    def test_query_with_arguments(self):
        """Test query execution with arguments."""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def greet(self, name: str) -> str:
                return f"Hello, {name}!"

        result = api.execute('{ greet(name: "Alice") }')
        assert result.data == {"greet": "Hello, Alice!"}

    def test_error_handling(self):
        """Test that errors are properly handled."""
        api = GraphQLAPI()

        @api.type(is_root_type=True)
        class Query:
            @api.field
            def failing_field(self) -> str:
                raise ValueError("Something went wrong")

        result = api.execute('{ failingField }')
        assert result.data is None
        assert len(result.errors) == 1
        assert "Something went wrong" in str(result.errors[0])
```

#### Test Coverage

- Aim for high test coverage (>90%)
- Test both happy paths and error conditions
- Test edge cases and boundary conditions
- Include integration tests for complex features

### Test Categories

1. **Unit Tests**: Test individual functions and methods
2. **Integration Tests**: Test feature workflows end-to-end
3. **Performance Tests**: Verify performance requirements
4. **Compatibility Tests**: Test with different Python versions

---

## Documentation

### Types of Documentation

1. **API Documentation**: Docstrings in code
2. **User Guide**: Tutorial-style documentation
3. **Reference Documentation**: Complete API reference
4. **Examples**: Practical usage examples

### Documentation Standards

- Write clear, concise documentation
- Include code examples where helpful
- Keep documentation up-to-date with code changes
- Use proper Markdown formatting

### Building Documentation Locally

```bash
# Install documentation dependencies
pip install sphinx sphinxcontrib-fulltoc guzzle_sphinx_theme

# Build HTML documentation
sphinx-build docs ./public -b html

# Open documentation
open public/index.html
```

---

## Submitting Changes

### Pull Request Process

1. **Ensure Quality**:
   ```bash
   # Run tests
   python -m pytest

   # Check code style
   flake8

   # Verify types
   mypy graphql_api
   ```

2. **Update Documentation**:
   - Update relevant docstrings
   - Add examples if introducing new features
   - Update the changelog if applicable

3. **Create Pull Request**:
   - Push your branch to your fork
   - Open a pull request against the `main` branch
   - Use a clear, descriptive title
   - Fill out the pull request template

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] Added tests for new functionality
- [ ] Updated documentation

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Docstrings updated
- [ ] Examples added/updated if applicable
```

### Review Process

1. **Automated Checks**: CI will run tests and linting
2. **Code Review**: Maintainers will review your code
3. **Feedback**: Address any requested changes
4. **Merge**: Once approved, your PR will be merged

---

## Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backwards compatible
- **Patch** (0.0.X): Bug fixes, backwards compatible

### Release Checklist

1. Update version in `VERSION` file
2. Update `CHANGELOG.md`
3. Ensure all tests pass
4. Create release tag
5. Build and publish to PyPI
6. Update documentation

---

## Getting Help

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **Email**: Contact maintainers directly for sensitive issues

### Asking Good Questions

When asking for help:

1. **Be Specific**: Describe the exact problem
2. **Provide Context**: Include relevant code and error messages
3. **Show Research**: Mention what you've already tried
4. **Be Patient**: Maintainers are volunteers

### Reporting Bugs

Use the GitHub issue template and include:

- Python version
- graphql-api version
- Minimal reproduction example
- Expected vs. actual behavior
- Full error traceback

---

## Recognition

Contributors are recognized in several ways:

- Listed in `CONTRIBUTORS.md`
- Mentioned in release notes for significant contributions
- GitHub contributor statistics
- Special recognition for major features or fixes

---

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to GraphQL API! Your efforts help make this project better for everyone. 🚀
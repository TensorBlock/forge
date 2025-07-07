# Contributing to Forge

Thank you for considering contributing to Forge! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Contributing to Forge](#contributing-to-forge)
  - [Table of Contents](#table-of-contents)
  - [Code of Conduct](#code-of-conduct)
  - [Getting Started](#getting-started)
  - [Development Workflow](#development-workflow)
  - [Pull Request Process](#pull-request-process)
  - [Coding Standards](#coding-standards)
  - [Testing](#testing)
  - [Documentation](#documentation)
  - [Issue Reporting](#issue-reporting)
  - [Release Process](#release-process)
  - [Thank You!](#thank-you)

## Code of Conduct

By participating in this project, you agree to uphold our Code of Conduct:

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/forge.git
   cd forge
   ```
3. **Set up the development environment**:
   ```bash
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt

   # Install development dependencies
   pip install -r requirements-dev.txt
   ```
4. **Add the upstream repository**:
   ```bash
   git remote add upstream https://github.com/originalowner/forge.git
   ```

## Development Workflow

1. **Create a branch** for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-you-are-fixing
   ```

2. **Make your changes** and commit them with clear, descriptive commit messages:
   ```bash
   git add .
   git commit -m "Add feature: concise description of changes"
   ```

3. **Keep your branch updated** with the upstream repository:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

4. **Push your changes** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

## Pull Request Process

1. **Submit a pull request** from your forked repository to the main Forge repository
2. **Describe your changes** in detail, including the issue number if applicable
3. **Update documentation** to reflect any changes you've made
4. **Ensure all tests pass** and add new tests for new functionality
5. **Request a review** from a maintainer
6. **Address review feedback** and make requested changes
7. **Once approved**, a maintainer will merge your PR

## Coding Standards

We follow Python's PEP 8 style guide with some adjustments:

- Use 4 spaces for indentation
- Maximum line length of 100 characters
- Use docstrings for all public modules, functions, classes, and methods
- Use type hints where appropriate
- Use descriptive variable names

We use pre-commit hooks to ensure code quality. To set up:

```bash
pip install pre-commit
pre-commit install
```

## Testing

We use pytest for testing. Please write tests for new code you create:

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=app
```

Guidelines for writing tests:
- Each test should be independent and not rely on the state from previous tests
- Use fixtures for setup and teardown
- Name tests clearly: `test_should_do_something_when_something()`
- Aim for high test coverage of new code

## Documentation

- Update documentation for any changes to functionality
- Use clear, concise language
- Include code examples where helpful
- Keep the README.md up-to-date
- Document API endpoints clearly

## Issue Reporting

When reporting issues, please use the issue templates provided and include:

1. **Steps to reproduce** the problem
2. **Expected behavior**
3. **Actual behavior**
4. **Version information**:
   - Forge version
   - Python version
   - Operating system
   - Any other relevant environment details

For feature requests, describe:
1. The problem you're trying to solve
2. Your proposed solution
3. Any alternatives you've considered

## Release Process

For maintainers only:

1. Update the version in setup.py and app/version.py
2. Update the CHANGELOG.md
3. Create a new GitHub release with release notes
4. Push a new tag matching the version number

## Thank You!

Your contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

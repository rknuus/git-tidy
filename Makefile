.PHONY: help install install-dev clean lint format typecheck test quality-checks build publish dev-setup
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

help: ## Show this help message
	@echo "$(BLUE)Git-tidy Development Tasks$(RESET)"
	@echo ""
	@echo "$(GREEN)Available targets:$(RESET)"
	@awk 'BEGIN {FS = ":.*##"; printf ""} /^[a-zA-Z_-]+:.*?##/ { printf "  $(BLUE)%-15s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

# Installation targets
install: ## Install package for production use
	@echo "$(GREEN)Installing git-tidy...$(RESET)"
	uv pip install .

install-dev: dev-setup ## Install package in development mode with all dependencies

dev-setup: ## Set up development environment
	@echo "$(GREEN)Setting up development environment...$(RESET)"
	uv sync --dev
	@echo "$(GREEN)Development environment ready!$(RESET)"

# Code quality targets
lint: ## Run linting with ruff
	@echo "$(GREEN)Running linting checks...$(RESET)"
	uv run ruff check .

lint-fix: ## Run linting with automatic fixes
	@echo "$(GREEN)Running linting with fixes...$(RESET)"
	uv run ruff check --fix .

format: ## Format code with black
	@echo "$(GREEN)Formatting code...$(RESET)"
	uv run black .

format-check: ## Check code formatting without making changes
	@echo "$(GREEN)Checking code formatting...$(RESET)"
	uv run black --check .

typecheck: ## Run type checking with mypy
	@echo "$(GREEN)Running type checks...$(RESET)"
	uv run mypy src/

# Testing targets
test: ## Run tests
	@echo "$(GREEN)Running tests...$(RESET)"
	uv run pytest

test-verbose: ## Run tests with verbose output
	@echo "$(GREEN)Running tests (verbose)...$(RESET)"
	uv run pytest -v

test-coverage: ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(RESET)"
	uv run pytest --cov=git_tidy --cov-report=html --cov-report=term

# Quality check combinations
quality-checks: lint typecheck format-check ## Run all quality checks (lint, typecheck, format-check)
	@echo "$(GREEN)All quality checks passed!$(RESET)"

quality-fix: lint-fix format ## Run all quality fixes (lint-fix, format)
	@echo "$(GREEN)All quality fixes applied!$(RESET)"

ci-checks: quality-checks test ## Run all CI checks (quality-checks + test)
	@echo "$(GREEN)All CI checks passed!$(RESET)"

# CLI testing targets
cli-help: ## Test CLI help output
	@echo "$(GREEN)Testing CLI help...$(RESET)"
	uv run python -m git_tidy.cli --help

cli-version: ## Test CLI version output
	@echo "$(GREEN)Testing CLI version...$(RESET)"
	uv run python -m git_tidy.cli --version

cli-test: cli-help cli-version ## Test basic CLI functionality
	@echo "$(GREEN)Testing subcommand help...$(RESET)"
	uv run python -m git_tidy.cli group-commits --help
	@echo "$(GREEN)CLI tests passed!$(RESET)"

# Build and publish targets
build: clean ## Build distribution packages
	@echo "$(GREEN)Building package...$(RESET)"
	uv build

build-check: build ## Build and check package
	@echo "$(GREEN)Checking built package...$(RESET)"
	uv run twine check dist/*

publish-test: build-check ## Publish to test PyPI
	@echo "$(YELLOW)Publishing to test PyPI...$(RESET)"
	uv run twine upload --repository testpypi dist/*

publish: build-check ## Publish to PyPI
	@echo "$(RED)Publishing to PyPI...$(RESET)"
	@echo "$(YELLOW)Are you sure? This will publish to production PyPI.$(RESET)"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = y ] || exit 1
	uv run twine upload dist/*

# Cleanup targets
clean: ## Clean up build artifacts and caches
	@echo "$(GREEN)Cleaning up...$(RESET)"
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

clean-all: clean ## Clean everything including uv cache
	@echo "$(GREEN)Cleaning everything...$(RESET)"
	uv cache clean

# Development workflow targets
dev: dev-setup quality-fix test ## Full development setup and check
	@echo "$(GREEN)Development workflow complete!$(RESET)"

pre-commit: quality-checks test ## Run pre-commit checks
	@echo "$(GREEN)Pre-commit checks passed!$(RESET)"

# Information targets
info: ## Show project information
	@echo "$(BLUE)Git-tidy Project Information$(RESET)"
	@echo "$(GREEN)Python version:$(RESET) $$(python --version)"
	@echo "$(GREEN)UV version:$(RESET) $$(uv --version)"
	@echo "$(GREEN)Project structure:$(RESET)"
	@tree -I '__pycache__|*.pyc|.git|.mypy_cache|.pytest_cache|.ruff_cache|htmlcov|*.egg-info|build|dist' -L 3 . || ls -la

# Utility targets
watch-test: ## Run tests in watch mode (requires entr)
	@echo "$(GREEN)Running tests in watch mode...$(RESET)"
	@echo "$(YELLOW)Install 'entr' if not available: brew install entr$(RESET)"
	find src tests -name "*.py" | entr -c uv run pytest

deps-update: ## Update dependencies
	@echo "$(GREEN)Updating dependencies...$(RESET)"
	uv sync --upgrade

# Git workflow helpers
git-clean-branches: ## Clean up merged branches
	@echo "$(GREEN)Cleaning up merged branches...$(RESET)"
	git branch --merged | grep -v "\*\|main\|master" | xargs -n 1 git branch -d || true

git-status: ## Show detailed git status
	@echo "$(GREEN)Git status:$(RESET)"
	@git status --short --branch
	@echo ""
	@echo "$(GREEN)Recent commits:$(RESET)"
	@git log --oneline -10
# Makefile — Zero Trust Network Simulation
# Run all tests, individual suites, load tests, and dev utilities.

.PHONY: all test test-unit test-integration test-security test-load test-all \
        test-opa lint format build up down logs clean help

# ── Configuration ──────────────────────────────────────────────────────────────
PYTHON        := python3
PYTEST        := $(PYTHON) -m pytest
LOCUST        := $(PYTHON) -m locust
GATEWAY_URL   := http://localhost:8000
LOCUST_USERS  := 100
LOCUST_RATE   := 10
LOCUST_TIME   := 60s

# HTML report directory
REPORT_DIR    := test-reports
TIMESTAMP     := $(shell date +%Y%m%d_%H%M%S)

# Colors
GREEN  := \033[0;32m
YELLOW := \033[1;33m
RED    := \033[0;31m
NC     := \033[0m
BOLD   := \033[1m

# ── Default target ─────────────────────────────────────────────────────────────
all: test

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "$(BOLD)Zero Trust Network Simulation — Test Commands$(NC)"
	@echo ""
	@echo "  $(GREEN)make test$(NC)              Run unit tests only (fast, no services needed)"
	@echo "  $(GREEN)make test-unit$(NC)         Same as make test"
	@echo "  $(GREEN)make test-security$(NC)     Run security tests (injection, privilege escalation)"
	@echo "  $(GREEN)make test-integration$(NC)  Run integration tests (requires Docker stack running)"
	@echo "  $(GREEN)make test-load$(NC)         Run Locust load test (requires running gateway)"
	@echo "  $(GREEN)make test-opa$(NC)          Run OPA Rego unit tests"
	@echo "  $(GREEN)make test-all$(NC)          Run ALL test suites"
	@echo ""
	@echo "  $(YELLOW)make build$(NC)             Build all Docker images"
	@echo "  $(YELLOW)make up$(NC)               Start full stack with Docker Compose"
	@echo "  $(YELLOW)make down$(NC)             Stop all containers"
	@echo "  $(YELLOW)make logs$(NC)             Tail logs from all containers"
	@echo ""
	@echo "  $(YELLOW)make lint$(NC)             Lint Python code (ruff)"
	@echo "  $(YELLOW)make format$(NC)           Format Python code (black)"
	@echo "  $(YELLOW)make clean$(NC)            Remove test artifacts and caches"
	@echo ""

# ── Test targets ───────────────────────────────────────────────────────────────

## Unit tests — fast, no external dependencies
test: test-unit

test-unit:
	@echo "$(BOLD)$(GREEN)Running Unit Tests...$(NC)"
	@mkdir -p $(REPORT_DIR)
	PYTHONPATH=gateway:services/service-a:services/service-b:services/service-c \
	$(PYTEST) tests/unit/ \
		--asyncio-mode=auto \
		--tb=short \
		--verbose \
		--html=$(REPORT_DIR)/unit_$(TIMESTAMP).html \
		--self-contained-html \
		-q
	@echo "$(GREEN)✓ Unit tests complete. Report: $(REPORT_DIR)/unit_$(TIMESTAMP).html$(NC)"

## Security tests — injection, privilege escalation, cert attacks
test-security:
	@echo "$(BOLD)$(RED)Running Security Tests...$(NC)"
	@mkdir -p $(REPORT_DIR)
	PYTHONPATH=gateway:services/service-a:services/service-b:services/service-c \
	$(PYTEST) tests/security/ \
		--asyncio-mode=auto \
		--tb=short \
		--verbose \
		--html=$(REPORT_DIR)/security_$(TIMESTAMP).html \
		--self-contained-html \
		-v
	@echo "$(GREEN)✓ Security tests complete. Report: $(REPORT_DIR)/security_$(TIMESTAMP).html$(NC)"

## Integration tests — require running Docker stack
test-integration:
	@echo "$(BOLD)$(YELLOW)Running Integration Tests...$(NC)"
	@echo "$(YELLOW)Ensure docker compose up is running first.$(NC)"
	@mkdir -p $(REPORT_DIR)
	PYTHONPATH=gateway \
	$(PYTEST) tests/integration/ \
		--asyncio-mode=auto \
		--tb=short \
		--verbose \
		-m integration \
		--html=$(REPORT_DIR)/integration_$(TIMESTAMP).html \
		--self-contained-html \
		-v
	@echo "$(GREEN)✓ Integration tests complete.$(NC)"

## OPA Rego unit tests
test-opa:
	@echo "$(BOLD)$(GREEN)Running OPA Policy Tests...$(NC)"
	@if command -v opa >/dev/null 2>&1; then \
		opa test policies/ -v --coverage; \
	else \
		echo "$(RED)OPA CLI not found. Install from https://openpolicyagent.org/docs/latest/#1-download-opa$(NC)"; \
		exit 1; \
	fi

## Load test — 100 concurrent users
test-load:
	@echo "$(BOLD)$(YELLOW)Running Load Tests ($(LOCUST_USERS) users, $(LOCUST_TIME))...$(NC)"
	@echo "$(YELLOW)Ensure gateway is running at $(GATEWAY_URL)$(NC)"
	@mkdir -p $(REPORT_DIR)
	$(LOCUST) \
		-f tests/load/locustfile.py \
		--host=$(GATEWAY_URL) \
		--users=$(LOCUST_USERS) \
		--spawn-rate=$(LOCUST_RATE) \
		--run-time=$(LOCUST_TIME) \
		--headless \
		--csv=$(REPORT_DIR)/load_$(TIMESTAMP) \
		--html=$(REPORT_DIR)/load_$(TIMESTAMP).html
	@echo "$(GREEN)✓ Load test complete. Report: $(REPORT_DIR)/load_$(TIMESTAMP).html$(NC)"

## All tests
test-all: test-unit test-security test-opa
	@echo ""
	@echo "$(GREEN)$(BOLD)✓ All test suites complete.$(NC)"
	@echo "  Reports available in $(REPORT_DIR)/"

# ── Docker Compose ──────────────────────────────────────────────────────────────

## Build all Docker images
build:
	@echo "$(BOLD)Building Docker images...$(NC)"
	docker compose build --no-cache
	@echo "$(GREEN)✓ Build complete$(NC)"

## Start full stack
up:
	@echo "$(BOLD)Starting Zero Trust stack...$(NC)"
	cp -n .env.example .env 2>/dev/null || true
	docker compose up -d
	@echo "$(GREEN)✓ Stack started. Dashboard: http://localhost:3000$(NC)"
	@echo "  Gateway:    http://localhost:8000"
	@echo "  OPA:        http://localhost:8181"
	@echo "  Vault:      http://localhost:8200"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana:    http://localhost:3001  (admin/zerotrust)"

## Stop stack
down:
	docker compose down
	@echo "$(GREEN)✓ Stack stopped$(NC)"

## Tail container logs
logs:
	docker compose logs -f --tail=50

## Setup Vault PKI and issue certs
setup-certs:
	@echo "$(BOLD)Setting up Vault PKI...$(NC)"
	cd certs && bash setup_vault.sh
	cd certs && bash issue_certs.sh
	cd certs && bash verify_mtls.sh

# ── Code Quality ───────────────────────────────────────────────────────────────

lint:
	@echo "$(BOLD)Linting Python code...$(NC)"
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check gateway/ services/ tests/; \
	else \
		$(PYTHON) -m flake8 gateway/ services/ tests/ --max-line-length=100; \
	fi

format:
	@echo "$(BOLD)Formatting Python code...$(NC)"
	@if command -v black >/dev/null 2>&1; then \
		black gateway/ services/ tests/ --line-length=100; \
	else \
		echo "$(YELLOW)black not installed. Run: pip install black$(NC)"; \
	fi

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	@echo "$(BOLD)Cleaning test artifacts...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf $(REPORT_DIR) 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete$(NC)"

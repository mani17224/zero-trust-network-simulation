# Zero Trust Network Simulation

A production-grade demonstration of Zero Trust Architecture using WireGuard VPN, HashiCorp Vault PKI, Open Policy Agent, FastAPI microservices, and a React 18 dashboard.

```
╔══════════════════════════════════════════════════════════════════════╗
║                  ZERO TRUST NETWORK SIMULATION                       ║
║                                                                      ║
║   [Client]──WireGuard──▶[Gateway:8000]──mTLS──▶[Service-A:8001]    ║
║                              │                  [Service-B:8002]    ║
║                              ▼                  [Service-C:8003]    ║
║                           [OPA:8181]                                ║
║                           [Vault:8200]                              ║
║                           [Prometheus:9090]──▶[Grafana:3001]       ║
║                           [Frontend:3000]                           ║
╚══════════════════════════════════════════════════════════════════════╝
```

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| VPN Tunnel | WireGuard | Encrypted overlay network between all nodes |
| PKI / Certificates | HashiCorp Vault | Root CA, Intermediate CA, 24h service certs |
| Authorization | Open Policy Agent (OPA) | Rego-based RBAC — every request evaluated |
| API Gateway | FastAPI (Python 3.12) | mTLS enforcement, OPA query, reverse proxy |
| Auth Service | FastAPI (Python 3.12) | JWT issuance + verification |
| Data Service | FastAPI (Python 3.12) | Paginated records CRUD |
| Admin Service | FastAPI (Python 3.12) | User management + audit logs |
| Frontend | React 18 + Vite | Dashboard: metrics, policies, certs, topology |
| Styling | Tailwind CSS + shadcn/ui | Dark-mode UI components |
| Charts | Recharts | Real-time request rate line chart |
| State | Zustand | Global settings + live metrics store |
| Data Fetching | React Query | API calls with caching + loading states |
| Orchestration | Docker Compose | Full stack with fixed IPs + healthchecks |
| Metrics | Prometheus | Scrapes all services every 15 seconds |
| Dashboards | Grafana | Auto-provisioned Zero Trust dashboard |
| Testing | pytest + locust | Unit, integration, security, load tests |

## Quick Start (5 commands)

```bash
# 1. Clone and enter the project
git clone <repo-url> zero-trust-simulation && cd zero-trust-simulation

# 2. Copy environment file
cp .env.example .env

# 3. Build and start all services
docker compose up -d --build

# 4. Issue certificates (wait ~30s for Vault to start first)
cd certs && bash setup_vault.sh && bash issue_certs.sh && cd ..

# 5. Open the dashboard
open http://localhost:3000
```

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Docker | ≥ 24.0 | https://docs.docker.com/get-docker/ |
| Docker Compose | ≥ 2.20 | Included with Docker Desktop |
| Bash | ≥ 4.0 | Pre-installed on Linux/macOS |
| WireGuard tools | any | `apt install wireguard-tools` (optional, for VPN) |
| OPA CLI | ≥ 0.65 | https://openpolicyagent.org (optional, for policy tests) |
| Python | ≥ 3.12 | https://python.org (for running tests locally) |

## Full Setup Guide

### Step 1: Environment Configuration

```bash
cp .env.example .env
# Edit .env and set:
# JWT_SECRET=<random 256-bit hex string>
# GRAFANA_PASSWORD=<your password>
```

### Step 2: Start the Stack

```bash
docker compose up -d --build
# Watch startup:
docker compose logs -f --tail=20
```

### Step 3: Initialize Vault PKI

```bash
# Wait for Vault to be healthy
docker compose ps vault

cd certs
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=root-token-dev   # From .env VAULT_DEV_TOKEN

bash setup_vault.sh     # Create Root CA + Intermediate CA
bash issue_certs.sh     # Issue 24h certs for all services
bash verify_mtls.sh     # Verify handshakes
cd ..
```

### Step 4: (Optional) WireGuard VPN

```bash
# On the gateway node:
cd wireguard
export GATEWAY_HOST=<public-ip>
export SERVICE_NODE_HOST=<service-node-ip>
export CLIENT_NODE_HOST=<client-ip>

bash setup_wireguard.sh --activate gateway
bash check_tunnel.sh
```

### Step 5: Run Tests

```bash
# Install Python test dependencies
pip install pytest pytest-asyncio pytest-html httpx locust

# Unit + security tests (no stack required)
make test-unit
make test-security

# OPA policy tests (requires opa CLI)
make test-opa

# Load test (requires running stack)
make test-load
```

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Frontend Dashboard | http://localhost:3000 | React UI |
| API Gateway | http://localhost:8000 | Main entry point |
| Gateway Health | http://localhost:8000/health | Health check |
| Gateway Metrics | http://localhost:8000/metrics | Prometheus metrics |
| Auth Service | http://localhost:8001 | JWT login/verify |
| Data Service | http://localhost:8002 | Records CRUD |
| Admin Service | http://localhost:8003 | Users + audit logs |
| OPA | http://localhost:8181 | Policy engine |
| Vault | http://localhost:8200 | PKI / secrets |
| Prometheus | http://localhost:9090 | Metrics collection |
| Grafana | http://localhost:3001 | Dashboards (admin/zerotrust) |

## API Reference

### Gateway (port 8000)

All requests require a valid client CN in `X-Client-Cert-CN` header (set by mTLS terminator).

| Method | Path | Required Role | Description |
|--------|------|--------------|-------------|
| GET | /health | none | Service health |
| GET | /metrics | monitoring | Prometheus metrics |
| POST | /login | gateway only | Authenticate user |
| GET | /verify | any registered | Verify JWT |
| GET | /records | reader+ | List records |
| POST | /records | writer+ | Create record |
| DELETE | /records/{id} | admin | Delete record |
| GET | /users | admin | List users |
| POST | /users | admin | Create user |
| GET | /audit-logs | admin | Audit log entries |

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | (required) | JWT signing secret — change in production |
| `LOG_LEVEL` | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR |
| `DEBUG` | `false` | Enable FastAPI docs at /docs |
| `OPA_URL` | `http://opa:8181` | OPA server address |
| `OPA_CACHE_TTL_SECONDS` | `10` | OPA decision cache TTL |
| `VAULT_DEV_TOKEN` | `root-token-dev` | Vault root token (dev mode) |
| `VAULT_ADDR` | `http://vault:8200` | Vault server address |
| `GRAFANA_USER` | `admin` | Grafana admin username |
| `GRAFANA_PASSWORD` | `zerotrust` | Grafana admin password |
| `GATEWAY_HOST` | `10.0.0.1` | WireGuard gateway node IP |
| `SERVICE_NODE_HOST` | `10.0.0.2` | WireGuard service node IP |
| `CLIENT_NODE_HOST` | `10.0.0.3` | WireGuard client node IP |
| `ALLOWED_CLIENT_CNS` | (comma list) | Allowlisted mTLS client CNs |
| `RENEW_THRESHOLD` | `86400` | Cert renewal threshold (seconds) |
| `VITE_GATEWAY_URL` | `http://localhost:8000` | Gateway URL for React build |

## Top 10 Troubleshooting Issues

| # | Problem | Fix |
|---|---------|-----|
| 1 | `Gateway returns 503` | OPA not healthy yet — run `docker compose ps opa` and wait |
| 2 | `Certificate verify failed` | Re-run `certs/issue_certs.sh` — 24h certs may have expired |
| 3 | `401 on all requests` | Set `X-Client-Cert-CN` header or ensure mTLS cert is attached |
| 4 | `OPA returns 500` | Check `policies/data.json` for valid JSON — no trailing commas |
| 5 | `Vault is sealed` | Run `certs/setup_vault.sh` — it auto-unseals with saved key |
| 6 | `Frontend shows no data` | Check `VITE_GATEWAY_URL` in `.env` and rebuild frontend |
| 7 | `Port already in use` | Run `docker compose down` then `docker compose up -d` |
| 8 | `WireGuard handshake fails` | Verify UDP 51820 is open in cloud firewall and endpoint IPs are correct |
| 9 | `Grafana shows no metrics` | Wait 30s for Prometheus to scrape; verify targets at localhost:9090/targets |
| 10 | `pytest ImportError` | Set `PYTHONPATH=gateway:services/service-a:services/service-b:services/service-c` |




# Zero Trust Network Simulation — Complete Setup Guide

## Requirements

Install these before running:

### 1. Git

Check:

```bash
git --version
```

### 2. Python 3.11+

Check:

```bash
python --version
```

### 3. Node.js (18+)

Check:

```bash
node -v
npm -v
```

### 4. Docker Desktop (Optional for container deployment)

Check:

```bash
docker --version
docker compose version
```

### 5. Open Policy Agent (OPA)

Download and place:

```text
opa.exe
```

Check:

```bash
opa version
```

---

# Clone Project

```bash
git clone https://github.com/mani17224/zero-trust-network-simulation.git

cd zero-trust-network-simulation
```

---

# Project Structure

```text
frontend/
gateway/
services/
 ├── service-a/
 ├── service-b/
 └── service-c/
policies/
monitoring/
tests/
wireguard/
```

---

# Step 1 — Start OPA

Move to project root:

```bash
cd zero-trust-network-simulation
```

Run:

```bash
opa.exe run --server --addr :8181 policies
```

Verify:

```bash
curl http://localhost:8181/v1/data
```

Expected:

```text
JSON response
```

---

# Step 2 — Start Gateway

Create environment:

```bash
set OPA_URL=http://localhost:8181
set SERVICE_A_URL=http://localhost:8001
set SERVICE_B_URL=http://localhost:8002
set SERVICE_C_URL=http://localhost:8003
```

Install:

```bash
cd gateway

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

Run:

```bash
cd ..

python -m uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify:

```bash
curl http://localhost:8000/health
```

Expected:

```json
{
"status":"healthy"
}
```

---

# Step 3 — Start Service A

```bash
cd services/service-a

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

set JWT_SECRET=local-dev-secret

python -m uvicorn main:app --port 8001 --reload
```

---

# Step 4 — Start Service B

```bash
cd services/service-b

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

python -m uvicorn main:app --port 8002 --reload
```

Verify:

```bash
curl http://localhost:8002/health
```

---

# Step 5 — Start Service C

```bash
cd services/service-c

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

python -m uvicorn main:app --port 8003 --reload
```

---

# Step 6 — Start Frontend

```bash
cd frontend

npm install
```

Create:

```text
.env
```

Add:

```env
VITE_GATEWAY_URL=http://localhost:8000
VITE_OPA_URL=http://localhost:8181
```

Run:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

---

# Verify System

Gateway:

```bash
curl http://localhost:8000/health
```

OPA:

```bash
curl http://localhost:8181/v1/data
```

Authorized:

```bash
curl -H "X-Client-Cert-CN: gateway.zerotrust.local" http://localhost:8000/records
```

Denied:

```bash
curl http://localhost:8000/records
```

Policy Test:

```bash
curl -X POST http://localhost:8181/v1/data/zerotrust/authz ^
-H "Content-Type: application/json" ^
-d "{\"input\":{\"subject\":\"gateway\",\"service\":\"service-b\",\"resource\":\"/records\",\"method\":\"GET\"}}"
```

Expected:

```json
{
"allow": true
}
```

---

# Features

* Zero Trust Architecture
* OPA Authorization
* RBAC
* mTLS Simulation
* API Gateway
* Certificate Management
* Monitoring Dashboard
* Audit Logging
* WireGuard Simulation
* Frontend Policy Tester


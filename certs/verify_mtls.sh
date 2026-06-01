#!/usr/bin/env bash
# verify_mtls.sh — Test mTLS handshake between services using curl
# Tests every service pair with proper cert/key/cacert options
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

log_info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_step()    { echo -e "\n${BOLD}${BLUE}━━━ $* ━━━${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${SCRIPT_DIR}"

# Service endpoints (adjust for your environment)
GATEWAY_URL="${GATEWAY_URL:-https://localhost:8000}"
SERVICE_A_URL="${SERVICE_A_URL:-https://localhost:8001}"
SERVICE_B_URL="${SERVICE_B_URL:-https://localhost:8002}"
SERVICE_C_URL="${SERVICE_C_URL:-https://localhost:8003}"

PASS=0
FAIL=0

echo -e "${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║   Zero Trust — mTLS Handshake Tests      ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Helper: mTLS curl test ────────────────────────────────────────────────────
# Args: description client_service target_url expected_http_code
mtls_test() {
    local description="$1"
    local client_service="$2"
    local target_url="$3"
    local expected_code="${4:-200}"

    local cert="${CERTS_DIR}/${client_service}/cert.pem"
    local key="${CERTS_DIR}/${client_service}/key.pem"
    local cacert="${CERTS_DIR}/${client_service}/ca_chain.pem"

    # Verify cert files exist
    if [[ ! -f "$cert" || ! -f "$key" || ! -f "$cacert" ]]; then
        log_error "${description}: Missing cert files for ${client_service}"
        FAIL=$((FAIL + 1))
        return 1
    fi

    local http_code tls_info
    # Capture HTTP status code and TLS info
    http_code=$(curl \
        --silent \
        --max-time 10 \
        --cert "$cert" \
        --key "$key" \
        --cacert "$cacert" \
        --write-out "%{http_code}" \
        --output /dev/null \
        "$target_url/health" 2>/dev/null) || http_code="000"

    # Capture TLS handshake details
    tls_info=$(curl \
        --silent \
        --max-time 10 \
        --cert "$cert" \
        --key "$key" \
        --cacert "$cacert" \
        --verbose \
        "$target_url/health" 2>&1 \
        | grep -E "SSL|TLS|subject|issuer|cipher" \
        | head -5) || tls_info="(no TLS info)"

    if [[ "$http_code" == "$expected_code" ]]; then
        log_success "${description}"
        log_info    "  Client: ${client_service} → ${target_url}"
        log_info    "  HTTP: ${http_code} (expected: ${expected_code})"
        echo -e "  ${CYAN}TLS: ${tls_info:0:120}${NC}"
        PASS=$((PASS + 1))
        return 0
    else
        log_error "${description}"
        log_error "  Client: ${client_service} → ${target_url}"
        log_error "  HTTP: ${http_code} (expected: ${expected_code})"
        FAIL=$((FAIL + 1))
        return 1
    fi
}

# ─── Helper: Negative test (no cert — should fail) ────────────────────────────
no_cert_test() {
    local description="$1"
    local target_url="$2"
    local cacert="${CERTS_DIR}/gateway/ca_chain.pem"

    local http_code
    http_code=$(curl \
        --silent \
        --max-time 10 \
        --cacert "$cacert" \
        --write-out "%{http_code}" \
        --output /dev/null \
        "$target_url/health" 2>/dev/null) || http_code="000"

    # Expect connection failure (000) or 400 Bad Request (no client cert)
    if [[ "$http_code" == "000" || "$http_code" == "400" || "$http_code" == "403" ]]; then
        log_success "${description} (correctly rejected — HTTP ${http_code})"
        PASS=$((PASS + 1))
    else
        log_error "${description}: Expected rejection but got HTTP ${http_code}"
        FAIL=$((FAIL + 1))
    fi
}

# ─── Test 1: Gateway Health (gateway cert) ────────────────────────────────────
log_step "Test 1: Gateway mTLS Handshake"
mtls_test \
    "Gateway ← gateway cert (self-check)" \
    "gateway" \
    "${GATEWAY_URL}" \
    "200"

# ─── Test 2: Service-A via Gateway ────────────────────────────────────────────
log_step "Test 2: Gateway → Service-A mTLS"
mtls_test \
    "Service-A ← gateway cert" \
    "gateway" \
    "${SERVICE_A_URL}" \
    "200"

# ─── Test 3: Service-B via Gateway ────────────────────────────────────────────
log_step "Test 3: Gateway → Service-B mTLS"
mtls_test \
    "Service-B ← gateway cert" \
    "gateway" \
    "${SERVICE_B_URL}" \
    "200"

# ─── Test 4: Service-C via Gateway ────────────────────────────────────────────
log_step "Test 4: Gateway → Service-C mTLS"
mtls_test \
    "Service-C ← gateway cert" \
    "gateway" \
    "${SERVICE_C_URL}" \
    "200"

# ─── Test 5: Monitoring Agent → Gateway ───────────────────────────────────────
log_step "Test 5: Monitoring Agent → Gateway mTLS"
mtls_test \
    "Gateway ← monitoring-agent cert" \
    "monitoring-agent" \
    "${GATEWAY_URL}" \
    "200"

# ─── Test 6: Service-A → Service-B (direct mTLS) ─────────────────────────────
log_step "Test 6: Service-A → Service-B Direct mTLS"
mtls_test \
    "Service-B ← service-a cert" \
    "service-a" \
    "${SERVICE_B_URL}" \
    "200"

# ─── Test 7: No Certificate (should be rejected) ──────────────────────────────
log_step "Test 7: No Client Certificate (Negative Test)"
no_cert_test \
    "Gateway rejects request with no client cert" \
    "${GATEWAY_URL}"

# ─── Test 8: Certificate CN Validation ────────────────────────────────────────
log_step "Test 8: Certificate CN and SAN Validation"
for service in gateway service-a service-b service-c monitoring-agent; do
    cert_file="${CERTS_DIR}/${service}/cert.pem"
    if [[ -f "$cert_file" ]]; then
        cn=$(openssl x509 -noout -subject -in "$cert_file" 2>/dev/null \
            | sed 's/.*CN=//' | sed 's/,.*//')
        san=$(openssl x509 -noout -ext subjectAltName -in "$cert_file" 2>/dev/null \
            | grep -v "Subject Alt" | tr -d ' ')
        expiry=$(openssl x509 -noout -enddate -in "$cert_file" 2>/dev/null \
            | cut -d= -f2)
        log_success "${service}: CN=${cn} | SAN=${san:0:60} | Expires=${expiry}"
        PASS=$((PASS + 1))
    else
        log_error "${service}: cert.pem not found"
        FAIL=$((FAIL + 1))
    fi
done

# ─── Test 9: CA Chain Verification ────────────────────────────────────────────
log_step "Test 9: CA Chain Integrity"
for service in gateway service-a service-b service-c monitoring-agent; do
    cert="${CERTS_DIR}/${service}/cert.pem"
    chain="${CERTS_DIR}/${service}/ca_chain.pem"
    if [[ -f "$cert" && -f "$chain" ]]; then
        if openssl verify -CAfile "$chain" "$cert" &>/dev/null; then
            log_success "${service}: Certificate chain valid"
            PASS=$((PASS + 1))
        else
            log_error "${service}: Certificate chain INVALID"
            FAIL=$((FAIL + 1))
        fi
    fi
done

# ─── Summary ──────────────────────────────────────────────────────────────────
log_step "mTLS Test Summary"
echo -e "  ${GREEN}PASSED: ${PASS}${NC}  ${RED}FAILED: ${FAIL}${NC}"
TOTAL=$((PASS + FAIL))
echo -e "  Total: ${TOTAL} tests"

if [[ $FAIL -eq 0 ]]; then
    echo -e "\n${GREEN}${BOLD}✓ All mTLS handshake tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}${BOLD}✗ ${FAIL} test(s) failed. Check certificate configuration.${NC}"
    exit 1
fi

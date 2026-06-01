#!/usr/bin/env bash
# setup_vault.sh — Initialize HashiCorp Vault, enable PKI, create Root + Intermediate CA
# Domain: zerotrust.local | Root: 10yr | Intermediate: 1yr
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

log_info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_step()    { echo -e "\n${BOLD}${BLUE}━━━ $* ━━━${NC}"; }

# ─── Configuration ─────────────────────────────────────────────────────────────
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_TOKEN_FILE="${VAULT_TOKEN_FILE:-./vault_root_token}"
VAULT_UNSEAL_FILE="${VAULT_UNSEAL_FILE:-./vault_unseal_keys}"
DOMAIN="${DOMAIN:-zerotrust.local}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export VAULT_ADDR

echo -e "${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║   Zero Trust — Vault PKI Setup           ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Prerequisites ─────────────────────────────────────────────────────────────
check_prerequisites() {
    log_step "Checking Prerequisites"
    for cmd in vault curl jq; do
        if command -v "$cmd" &>/dev/null; then
            log_success "$cmd: $(command -v $cmd)"
        else
            log_error "$cmd not found"
            exit 1
        fi
    done
}

# ─── Wait for Vault ────────────────────────────────────────────────────────────
wait_for_vault() {
    log_step "Waiting for Vault to be Ready"
    local retries=30
    while [[ $retries -gt 0 ]]; do
        if curl -sf "${VAULT_ADDR}/v1/sys/health" &>/dev/null; then
            log_success "Vault is reachable at ${VAULT_ADDR}"
            return 0
        fi
        log_info "Waiting... ($retries retries left)"
        sleep 2
        retries=$((retries - 1))
    done
    log_error "Vault did not become ready. Is it running?"
    exit 1
}

# ─── Initialize Vault ─────────────────────────────────────────────────────────
init_vault() {
    log_step "Initializing Vault"

    local health
    health=$(curl -sf "${VAULT_ADDR}/v1/sys/health" | jq -r '.initialized')

    if [[ "$health" == "true" ]]; then
        log_warn "Vault already initialized — loading existing token"
        if [[ -f "$VAULT_TOKEN_FILE" ]]; then
            export VAULT_TOKEN
            VAULT_TOKEN=$(cat "$VAULT_TOKEN_FILE")
            log_success "Root token loaded from ${VAULT_TOKEN_FILE}"
        else
            log_error "Vault initialized but no token file found. Set VAULT_TOKEN manually."
            exit 1
        fi
        return 0
    fi

    log_info "Initializing Vault (1 key share for dev simplicity)..."
    local init_output
    init_output=$(vault operator init -key-shares=1 -key-threshold=1 -format=json)

    local unseal_key root_token
    unseal_key=$(echo "$init_output" | jq -r '.unseal_keys_b64[0]')
    root_token=$(echo "$init_output" | jq -r '.root_token')

    echo "$unseal_key" > "$VAULT_UNSEAL_FILE"
    echo "$root_token" > "$VAULT_TOKEN_FILE"
    chmod 600 "$VAULT_TOKEN_FILE" "$VAULT_UNSEAL_FILE"

    export VAULT_TOKEN="$root_token"
    log_success "Vault initialized. Token saved to ${VAULT_TOKEN_FILE}"

    # Unseal immediately
    vault operator unseal "$unseal_key"
    log_success "Vault unsealed"
}

# ─── Unseal Vault ─────────────────────────────────────────────────────────────
unseal_vault() {
    log_step "Unsealing Vault"
    local sealed
    sealed=$(curl -sf "${VAULT_ADDR}/v1/sys/health" | jq -r '.sealed')

    if [[ "$sealed" == "false" ]]; then
        log_warn "Vault already unsealed — skipping"
        return 0
    fi

    if [[ ! -f "$VAULT_UNSEAL_FILE" ]]; then
        log_error "Unseal key file not found: ${VAULT_UNSEAL_FILE}"
        exit 1
    fi

    vault operator unseal "$(cat "$VAULT_UNSEAL_FILE")"
    log_success "Vault unsealed"
}

# ─── Load Token ────────────────────────────────────────────────────────────────
load_token() {
    if [[ -z "${VAULT_TOKEN:-}" ]]; then
        if [[ -f "$VAULT_TOKEN_FILE" ]]; then
            export VAULT_TOKEN
            VAULT_TOKEN=$(cat "$VAULT_TOKEN_FILE")
        else
            log_error "VAULT_TOKEN not set and no token file found"
            exit 1
        fi
    fi
    log_info "Using Vault token: ${VAULT_TOKEN:0:8}..."
}

# ─── Enable PKI — Root CA (10 years) ─────────────────────────────────────────
setup_root_ca() {
    log_step "Setting Up Root CA (10-year validity)"

    if vault secrets list -format=json | jq -r 'keys[]' | grep -q "^pki/$"; then
        log_warn "PKI secrets engine already enabled at pki/ — skipping"
    else
        vault secrets enable -path=pki pki
        log_success "PKI secrets engine enabled at pki/"
    fi

    # Set max TTL to 10 years
    vault secrets tune -max-lease-ttl=87600h pki

    # Check if root CA already exists
    if vault read pki/cert/ca &>/dev/null; then
        log_warn "Root CA already exists — skipping generation"
    else
        log_info "Generating root CA certificate..."
        vault write -format=json pki/root/generate/internal \
            common_name="${DOMAIN} Root CA" \
            ttl="87600h" \
            key_type="rsa" \
            key_bits="4096" \
            organization="Zero Trust Simulation" \
            country="US" \
            | jq -r '.data.certificate' > "${SCRIPT_DIR}/root_ca.pem"

        log_success "Root CA generated and saved to ${SCRIPT_DIR}/root_ca.pem"
    fi

    # Configure CRL and OCSP URLs
    vault write pki/config/urls \
        issuing_certificates="${VAULT_ADDR}/v1/pki/ca" \
        crl_distribution_points="${VAULT_ADDR}/v1/pki/crl"

    log_success "Root CA URLs configured"
}

# ─── Enable PKI — Intermediate CA (1 year) ────────────────────────────────────
setup_intermediate_ca() {
    log_step "Setting Up Intermediate CA (1-year validity)"

    if vault secrets list -format=json | jq -r 'keys[]' | grep -q "^pki_int/$"; then
        log_warn "Intermediate PKI engine already enabled — skipping"
    else
        vault secrets enable -path=pki_int pki
        log_success "Intermediate PKI engine enabled at pki_int/"
    fi

    vault secrets tune -max-lease-ttl=8760h pki_int

    # Check if intermediate CA already signed
    if vault read pki_int/cert/ca &>/dev/null; then
        log_warn "Intermediate CA already exists — skipping"
        return 0
    fi

    # Generate intermediate CSR
    log_info "Generating intermediate CA CSR..."
    local csr
    csr=$(vault write -format=json pki_int/intermediate/generate/internal \
        common_name="${DOMAIN} Intermediate CA" \
        key_type="rsa" \
        key_bits="2048" \
        organization="Zero Trust Simulation" \
        | jq -r '.data.csr')

    # Sign the CSR with root CA
    log_info "Signing intermediate CSR with root CA..."
    local signed_cert
    signed_cert=$(vault write -format=json pki/root/sign-intermediate \
        csr="$csr" \
        common_name="${DOMAIN} Intermediate CA" \
        ttl="8760h" \
        format="pem_bundle" \
        | jq -r '.data.certificate')

    # Import signed certificate
    vault write pki_int/intermediate/set-signed \
        certificate="$signed_cert"

    # Save intermediate cert
    echo "$signed_cert" > "${SCRIPT_DIR}/intermediate_ca.pem"
    log_success "Intermediate CA signed and saved to ${SCRIPT_DIR}/intermediate_ca.pem"

    # Configure intermediate URLs
    vault write pki_int/config/urls \
        issuing_certificates="${VAULT_ADDR}/v1/pki_int/ca" \
        crl_distribution_points="${VAULT_ADDR}/v1/pki_int/crl"

    log_success "Intermediate CA URLs configured"
}

# ─── Create PKI Role for Services ─────────────────────────────────────────────
create_pki_role() {
    log_step "Creating PKI Role for Service Certificates"

    if vault read pki_int/roles/zerotrust-services &>/dev/null; then
        log_warn "PKI role 'zerotrust-services' already exists — skipping"
    else
        vault write pki_int/roles/zerotrust-services \
            allowed_domains="${DOMAIN}" \
            allow_subdomains=true \
            allow_localhost=true \
            max_ttl="24h" \
            key_type="rsa" \
            key_bits="2048" \
            require_cn=true \
            server_flag=true \
            client_flag=true \
            code_signing_flag=false \
            email_protection_flag=false

        log_success "PKI role 'zerotrust-services' created (max TTL: 24h)"
    fi
}

# ─── Create Vault Policy ───────────────────────────────────────────────────────
create_vault_policy() {
    log_step "Creating Vault Access Policies"

    vault policy write zerotrust-pki - <<'POLICY'
# Policy for Zero Trust services to issue and renew their own certificates
path "pki_int/issue/zerotrust-services" {
  capabilities = ["create", "update"]
}

path "pki_int/cert/ca" {
  capabilities = ["read"]
}

path "pki/cert/ca" {
  capabilities = ["read"]
}

path "pki_int/crl" {
  capabilities = ["read"]
}
POLICY

    log_success "Policy 'zerotrust-pki' created"
}

# ─── Summary ──────────────────────────────────────────────────────────────────
print_summary() {
    log_step "Vault PKI Setup Complete"
    echo -e "${BOLD}PKI Hierarchy:${NC}"
    echo -e "  ${CYAN}Root CA:${NC}          pki/ (10 years)"
    echo -e "  ${CYAN}Intermediate CA:${NC}  pki_int/ (1 year)"
    echo -e "  ${CYAN}Service certs:${NC}    pki_int/roles/zerotrust-services (24h)"
    echo ""
    echo -e "${BOLD}Files:${NC}"
    echo -e "  ${SCRIPT_DIR}/root_ca.pem"
    echo -e "  ${SCRIPT_DIR}/intermediate_ca.pem"
    echo ""
    echo -e "Run ${YELLOW}./issue_certs.sh${NC} to issue service certificates."
}

# ─── Main ──────────────────────────────────────────────────────────────────────
main() {
    check_prerequisites
    wait_for_vault
    init_vault
    unseal_vault
    load_token
    setup_root_ca
    setup_intermediate_ca
    create_pki_role
    create_vault_policy
    print_summary
}

main "$@"

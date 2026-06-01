#!/usr/bin/env bash
# issue_certs.sh — Issue mTLS certificates for all Zero Trust services via Vault PKI
# Services: gateway, service-a, service-b, service-c, monitoring-agent
# Saves: cert.pem, key.pem, ca_chain.pem to ./certs/<service>/
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

log_info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_step()    { echo -e "\n${BOLD}${BLUE}━━━ $* ━━━${NC}"; }

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_TOKEN_FILE="${VAULT_TOKEN_FILE:-./vault_root_token}"
DOMAIN="${DOMAIN:-zerotrust.local}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="${SCRIPT_DIR}"

export VAULT_ADDR

# Services to issue certs for: "common_name:alt_names"
SERVICES=(
    "gateway:gateway.${DOMAIN},localhost,127.0.0.1,172.20.0.10"
    "service-a:service-a.${DOMAIN},localhost,127.0.0.1,172.20.0.11"
    "service-b:service-b.${DOMAIN},localhost,127.0.0.1,172.20.0.12"
    "service-c:service-c.${DOMAIN},localhost,127.0.0.1,172.20.0.13"
    "monitoring-agent:monitoring.${DOMAIN},localhost,127.0.0.1,172.20.0.20"
)

echo -e "${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║   Zero Trust — Certificate Issuance      ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Load Vault Token ──────────────────────────────────────────────────────────
load_token() {
    if [[ -z "${VAULT_TOKEN:-}" ]]; then
        if [[ -f "$VAULT_TOKEN_FILE" ]]; then
            export VAULT_TOKEN
            VAULT_TOKEN=$(cat "$VAULT_TOKEN_FILE")
            log_info "Loaded Vault token from ${VAULT_TOKEN_FILE}"
        else
            log_error "VAULT_TOKEN not set. Run setup_vault.sh first."
            exit 1
        fi
    fi
}

# ─── Check Vault Health ────────────────────────────────────────────────────────
check_vault() {
    log_step "Verifying Vault Connectivity"
    local health
    health=$(curl -sf "${VAULT_ADDR}/v1/sys/health" 2>/dev/null) || {
        log_error "Cannot reach Vault at ${VAULT_ADDR}"
        exit 1
    }
    local sealed
    sealed=$(echo "$health" | jq -r '.sealed')
    if [[ "$sealed" == "true" ]]; then
        log_error "Vault is sealed. Run setup_vault.sh to unseal."
        exit 1
    fi
    log_success "Vault healthy and unsealed at ${VAULT_ADDR}"
}

# ─── Issue Certificate for One Service ────────────────────────────────────────
issue_cert() {
    local service="$1"
    local alt_names="$2"
    local out_dir="${CERTS_DIR}/${service}"

    log_step "Issuing Certificate: ${service}"
    mkdir -p "$out_dir"
    chmod 700 "$out_dir"

    local cn="${service}.${DOMAIN}"

    log_info "CN: ${cn}"
    log_info "SANs: ${alt_names}"

    # Issue certificate from Vault
    local response
    response=$(vault write -format=json pki_int/issue/zerotrust-services \
        common_name="${cn}" \
        alt_names="${alt_names}" \
        ip_sans="127.0.0.1" \
        ttl="24h" \
        format="pem") || {
        log_error "Failed to issue cert for ${service}"
        exit 1
    }

    # Extract certificate components
    echo "$response" | jq -r '.data.certificate'       > "${out_dir}/cert.pem"
    echo "$response" | jq -r '.data.private_key'       > "${out_dir}/key.pem"
    echo "$response" | jq -r '.data.ca_chain | join("\n")' > "${out_dir}/ca_chain.pem"
    echo "$response" | jq -r '.data.issuing_ca'        > "${out_dir}/issuing_ca.pem"

    # Also write the full bundle (cert + chain) for nginx/services
    cat "${out_dir}/cert.pem" "${out_dir}/ca_chain.pem" > "${out_dir}/fullchain.pem"

    # Copy root CA
    if [[ -f "${SCRIPT_DIR}/root_ca.pem" ]]; then
        cp "${SCRIPT_DIR}/root_ca.pem" "${out_dir}/root_ca.pem"
    fi

    # Secure private key
    chmod 600 "${out_dir}/key.pem"
    chmod 644 "${out_dir}/cert.pem" "${out_dir}/ca_chain.pem" "${out_dir}/fullchain.pem"

    # Extract and show expiry
    local expiry
    expiry=$(openssl x509 -noout -enddate -in "${out_dir}/cert.pem" 2>/dev/null \
        | cut -d= -f2 || echo "unknown")

    log_success "Certificate issued for ${service}"
    log_info    "  File:   ${out_dir}/cert.pem"
    log_info    "  Expiry: ${expiry}"
}

# ─── Verify Issued Certificates ────────────────────────────────────────────────
verify_certs() {
    log_step "Verifying All Issued Certificates"

    local all_ok=true
    for entry in "${SERVICES[@]}"; do
        local service="${entry%%:*}"
        local cert_file="${CERTS_DIR}/${service}/cert.pem"
        local ca_file="${CERTS_DIR}/${service}/ca_chain.pem"

        if [[ ! -f "$cert_file" ]]; then
            log_error "Missing cert: ${cert_file}"
            all_ok=false
            continue
        fi

        # Verify cert against CA chain
        if openssl verify -CAfile "$ca_file" "$cert_file" &>/dev/null; then
            local cn expiry
            cn=$(openssl x509 -noout -subject -in "$cert_file" | sed 's/.*CN=//')
            expiry=$(openssl x509 -noout -enddate -in "$cert_file" | cut -d= -f2)
            log_success "${service}: CN=${cn} | Expires: ${expiry}"
        else
            log_error "${service}: Certificate verification FAILED"
            all_ok=false
        fi
    done

    [[ "$all_ok" == "true" ]] && return 0 || return 1
}

# ─── Print Summary Table ───────────────────────────────────────────────────────
print_summary() {
    log_step "Certificate Issuance Summary"
    printf "\n${BOLD}%-20s %-45s %-35s${NC}\n" "Service" "Certificate Path" "Expires"
    printf "%-20s %-45s %-35s\n" "-------" "----------------" "-------"

    for entry in "${SERVICES[@]}"; do
        local service="${entry%%:*}"
        local cert_file="${CERTS_DIR}/${service}/cert.pem"

        if [[ -f "$cert_file" ]]; then
            local expiry
            expiry=$(openssl x509 -noout -enddate -in "$cert_file" 2>/dev/null \
                | cut -d= -f2 || echo "unknown")
            printf "%-20s %-45s %-35s\n" \
                "$service" \
                "${CERTS_DIR}/${service}/cert.pem" \
                "$expiry"
        else
            printf "%-20s %-45s %-35s\n" "$service" "MISSING" "N/A"
        fi
    done

    echo ""
    echo -e "${GREEN}${BOLD}✓ All certificates issued.${NC}"
    echo -e "  Run ${YELLOW}./renew_certs.sh${NC} before they expire (< 24h TTL)."
    echo -e "  Run ${YELLOW}./verify_mtls.sh${NC} to test mTLS handshakes."
}

# ─── Main ──────────────────────────────────────────────────────────────────────
main() {
    load_token
    check_vault

    log_step "Issuing Service Certificates"
    for entry in "${SERVICES[@]}"; do
        local service="${entry%%:*}"
        local alt_names="${entry##*:}"
        issue_cert "$service" "$alt_names"
    done

    verify_certs
    print_summary
}

main "$@"

#!/usr/bin/env bash
# renew_certs.sh — Check cert expiry and auto-renew if < 24h remaining
# Safe to run as a cron job: * * * * * /path/to/renew_certs.sh
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

# Renew threshold: seconds before expiry to trigger renewal (default: 24h = 86400s)
RENEW_THRESHOLD="${RENEW_THRESHOLD:-86400}"

export VAULT_ADDR

SERVICES=(
    "gateway:gateway.${DOMAIN},localhost,127.0.0.1,172.20.0.10"
    "service-a:service-a.${DOMAIN},localhost,127.0.0.1,172.20.0.11"
    "service-b:service-b.${DOMAIN},localhost,127.0.0.1,172.20.0.12"
    "service-c:service-c.${DOMAIN},localhost,127.0.0.1,172.20.0.13"
    "monitoring-agent:monitoring.${DOMAIN},localhost,127.0.0.1,172.20.0.20"
)

RENEWED=0
SKIPPED=0
FAILED=0

echo -e "${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║   Zero Trust — Certificate Renewal       ║"
echo "║   $(date -u '+%Y-%m-%dT%H:%M:%SZ')          ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Load Vault Token ──────────────────────────────────────────────────────────
load_token() {
    if [[ -z "${VAULT_TOKEN:-}" ]]; then
        if [[ -f "$VAULT_TOKEN_FILE" ]]; then
            export VAULT_TOKEN
            VAULT_TOKEN=$(cat "$VAULT_TOKEN_FILE")
        else
            log_error "VAULT_TOKEN not set. Cannot renew certs."
            exit 1
        fi
    fi
}

# ─── Get Seconds Until Expiry ──────────────────────────────────────────────────
seconds_until_expiry() {
    local cert_file="$1"
    local expiry_date
    expiry_date=$(openssl x509 -noout -enddate -in "$cert_file" 2>/dev/null \
        | cut -d= -f2)

    if [[ -z "$expiry_date" ]]; then
        echo "-1"
        return
    fi

    local expiry_epoch now_epoch
    expiry_epoch=$(date -d "$expiry_date" +%s 2>/dev/null \
        || date -j -f "%b %d %T %Y %Z" "$expiry_date" +%s 2>/dev/null \
        || echo "0")
    now_epoch=$(date +%s)

    echo $((expiry_epoch - now_epoch))
}

# ─── Renew a Single Certificate ────────────────────────────────────────────────
renew_cert() {
    local service="$1"
    local alt_names="$2"
    local out_dir="${CERTS_DIR}/${service}"
    local cn="${service}.${DOMAIN}"

    log_info "Renewing certificate for ${service}..."
    mkdir -p "$out_dir"

    local response
    response=$(vault write -format=json pki_int/issue/zerotrust-services \
        common_name="${cn}" \
        alt_names="${alt_names}" \
        ip_sans="127.0.0.1" \
        ttl="24h" \
        format="pem") || {
        log_error "Vault renewal failed for ${service}"
        return 1
    }

    # Atomic write: write to temp files first, then rename
    local tmp_cert tmp_key tmp_chain
    tmp_cert=$(mktemp)
    tmp_key=$(mktemp)
    tmp_chain=$(mktemp)

    echo "$response" | jq -r '.data.certificate'            > "$tmp_cert"
    echo "$response" | jq -r '.data.private_key'            > "$tmp_key"
    echo "$response" | jq -r '.data.ca_chain | join("\n")'  > "$tmp_chain"

    chmod 644 "$tmp_cert" "$tmp_chain"
    chmod 600 "$tmp_key"

    mv "$tmp_cert"  "${out_dir}/cert.pem"
    mv "$tmp_key"   "${out_dir}/key.pem"
    mv "$tmp_chain" "${out_dir}/ca_chain.pem"

    cat "${out_dir}/cert.pem" "${out_dir}/ca_chain.pem" > "${out_dir}/fullchain.pem"

    local new_expiry
    new_expiry=$(openssl x509 -noout -enddate -in "${out_dir}/cert.pem" \
        | cut -d= -f2)
    log_success "Renewed ${service} → expires: ${new_expiry}"

    # Signal service to reload cert if possible (send SIGHUP or call reload endpoint)
    reload_service "$service" || true

    return 0
}

# ─── Reload Service After Renewal ─────────────────────────────────────────────
reload_service() {
    local service="$1"
    # Try to notify service via reload endpoint (non-fatal if unavailable)
    local reload_url
    case "$service" in
        gateway)       reload_url="http://localhost:8000/admin/reload-cert" ;;
        service-a)     reload_url="http://localhost:8001/admin/reload-cert" ;;
        service-b)     reload_url="http://localhost:8002/admin/reload-cert" ;;
        service-c)     reload_url="http://localhost:8003/admin/reload-cert" ;;
        *)             return 0 ;;
    esac

    if curl -sf --max-time 2 -X POST "$reload_url" &>/dev/null; then
        log_info "  Notified ${service} to reload certificate"
    else
        log_warn "  Could not notify ${service} to reload (service may not be running)"
    fi
}

# ─── Check and Renew Each Service ─────────────────────────────────────────────
check_and_renew() {
    log_step "Checking Certificate Expiry"
    printf "\n${BOLD}%-20s %-12s %-35s %-10s${NC}\n" \
        "Service" "Time Left" "Expires" "Action"
    printf "%-20s %-12s %-35s %-10s\n" \
        "-------" "---------" "-------" "------"

    for entry in "${SERVICES[@]}"; do
        local service="${entry%%:*}"
        local alt_names="${entry##*:}"
        local cert_file="${CERTS_DIR}/${service}/cert.pem"

        if [[ ! -f "$cert_file" ]]; then
            printf "%-20s %-12s %-35s %-10s\n" \
                "$service" "MISSING" "N/A" "$(echo -e ${RED}ISSUE${NC})"
            log_warn "  ${service}: No cert found — issuing new one"
            if renew_cert "$service" "$alt_names"; then
                RENEWED=$((RENEWED + 1))
            else
                FAILED=$((FAILED + 1))
            fi
            continue
        fi

        local seconds_left
        seconds_left=$(seconds_until_expiry "$cert_file")
        local expiry
        expiry=$(openssl x509 -noout -enddate -in "$cert_file" 2>/dev/null \
            | cut -d= -f2 || echo "unknown")

        if [[ "$seconds_left" -lt 0 ]]; then
            local time_str="EXPIRED"
            printf "%-20s %-12s %-35s %-10s\n" \
                "$service" "$time_str" "$expiry" "$(echo -e ${RED}RENEW${NC})"
            if renew_cert "$service" "$alt_names"; then
                RENEWED=$((RENEWED + 1))
            else
                FAILED=$((FAILED + 1))
            fi
        elif [[ "$seconds_left" -lt "$RENEW_THRESHOLD" ]]; then
            local hours_left=$(( seconds_left / 3600 ))
            local time_str="${hours_left}h left"
            printf "%-20s %-12s %-35s %-10s\n" \
                "$service" "$time_str" "$expiry" "$(echo -e ${YELLOW}RENEW${NC})"
            if renew_cert "$service" "$alt_names"; then
                RENEWED=$((RENEWED + 1))
            else
                FAILED=$((FAILED + 1))
            fi
        else
            local hours_left=$(( seconds_left / 3600 ))
            local time_str="${hours_left}h left"
            printf "%-20s %-12s %-35s %-10s\n" \
                "$service" "$time_str" "$expiry" "$(echo -e ${GREEN}OK${NC})"
            SKIPPED=$((SKIPPED + 1))
        fi
    done
}

# ─── Summary ──────────────────────────────────────────────────────────────────
print_summary() {
    echo ""
    echo -e "${BOLD}Summary:${NC}"
    echo -e "  ${GREEN}Renewed: ${RENEWED}${NC}  ${CYAN}Up-to-date: ${SKIPPED}${NC}  ${RED}Failed: ${FAILED}${NC}"

    if [[ $FAILED -gt 0 ]]; then
        log_error "Some renewals failed. Check Vault connectivity."
        exit 1
    else
        echo -e "\n${GREEN}${BOLD}✓ Renewal check complete${NC}"
    fi
}

# ─── Main ──────────────────────────────────────────────────────────────────────
main() {
    load_token
    check_and_renew
    print_summary
}

main "$@"

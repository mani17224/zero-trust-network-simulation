#!/usr/bin/env bash
# check_tunnel.sh — Ping all WireGuard peers and report VPN tunnel status
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

log_info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[✓]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[!]${NC}    $*"; }
log_error()   { echo -e "${RED}[✗]${NC}    $*"; }

PEERS=(
    "10.0.0.1:Gateway"
    "10.0.0.2:ServiceNode"
    "10.0.0.3:Client"
)

PING_COUNT=3
PING_TIMEOUT=2
PASS=0
FAIL=0

echo -e "${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║   Zero Trust — WireGuard Tunnel Check    ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ─── Interface Status ──────────────────────────────────────────────────────────
echo -e "${BOLD}Interface Status:${NC}"
if ip link show wg0 &>/dev/null; then
    STATUS=$(ip link show wg0 | grep -oP '(?<=state )\w+')
    log_success "wg0 interface exists (state: ${STATUS})"
    echo ""
    echo -e "${BOLD}WireGuard Details:${NC}"
    wg show wg0 2>/dev/null || log_warn "Could not read wg show (may need root)"
else
    log_error "wg0 interface NOT found. Run setup_wireguard.sh --activate first."
    exit 1
fi

echo ""
echo -e "${BOLD}Peer Connectivity:${NC}"
printf "%-20s %-15s %-10s %-15s\n" "Node" "IP" "Status" "Latency"
printf "%-20s %-15s %-10s %-15s\n" "----" "--" "------" "-------"

# ─── Ping Each Peer ────────────────────────────────────────────────────────────
for peer in "${PEERS[@]}"; do
    IP="${peer%%:*}"
    NAME="${peer##*:}"

    # Skip self
    if ip addr show wg0 2>/dev/null | grep -q "$IP"; then
        printf "%-20s %-15s %-10s %-15s\n" "$NAME" "$IP" "$(echo -e ${BLUE}SELF${NC})" "-"
        continue
    fi

    START_NS=$(date +%s%N)
    if ping -c "$PING_COUNT" -W "$PING_TIMEOUT" -q "$IP" &>/dev/null; then
        END_NS=$(date +%s%N)
        LATENCY_MS=$(( (END_NS - START_NS) / 1000000 / PING_COUNT ))
        printf "%-20s %-15s %-10s %-15s\n" \
            "$NAME" "$IP" \
            "$(echo -e ${GREEN}REACHABLE${NC})" \
            "${LATENCY_MS}ms"
        PASS=$((PASS + 1))
    else
        printf "%-20s %-15s %-10s %-15s\n" \
            "$NAME" "$IP" \
            "$(echo -e ${RED}UNREACHABLE${NC})" \
            "timeout"
        FAIL=$((FAIL + 1))
    fi
done

# ─── Handshake Status ─────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Last Handshakes:${NC}"
if command -v wg &>/dev/null; then
    wg show wg0 latest-handshakes 2>/dev/null | while read -r peer ts; do
        if [[ "$ts" == "0" ]]; then
            echo -e "  Peer ${CYAN}${peer:0:20}...${NC} → ${RED}Never connected${NC}"
        else
            AGE=$(( $(date +%s) - ts ))
            if [[ $AGE -lt 300 ]]; then
                echo -e "  Peer ${CYAN}${peer:0:20}...${NC} → ${GREEN}${AGE}s ago (active)${NC}"
            else
                echo -e "  Peer ${CYAN}${peer:0:20}...${NC} → ${YELLOW}${AGE}s ago (stale)${NC}"
            fi
        fi
    done
fi

# ─── Transfer Stats ────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Transfer Statistics:${NC}"
wg show wg0 transfer 2>/dev/null | while read -r peer rx tx; do
    RX_MB=$(echo "scale=2; $rx / 1048576" | bc 2>/dev/null || echo "?")
    TX_MB=$(echo "scale=2; $tx / 1048576" | bc 2>/dev/null || echo "?")
    echo -e "  Peer ${CYAN}${peer:0:20}...${NC} RX: ${GREEN}${RX_MB} MB${NC} TX: ${YELLOW}${TX_MB} MB${NC}"
done

# ─── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Summary:${NC}"
echo -e "  ${GREEN}${PASS} peer(s) reachable${NC}  ${RED}${FAIL} peer(s) unreachable${NC}"

if [[ $FAIL -eq 0 ]]; then
    echo -e "\n${GREEN}${BOLD}✓ All tunnels operational${NC}"
    exit 0
else
    echo -e "\n${RED}${BOLD}✗ Some tunnels have issues. Check endpoint configs and firewall rules.${NC}"
    exit 1
fi

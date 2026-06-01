# WireGuard VPN — Zero Trust Network Simulation

## Network Layout

```
┌─────────────────────────────────────────────────────────┐
│                   WireGuard VPN Subnet                   │
│                     10.0.0.0/24                          │
│                                                          │
│  ┌─────────────┐      ┌─────────────┐    ┌───────────┐  │
│  │   Gateway   │◄────►│ Service Node│    │  Client   │  │
│  │  10.0.0.1   │      │  10.0.0.2   │    │ 10.0.0.3  │  │
│  │  Port 51820 │      │  Port 51820 │    │           │  │
│  └──────┬──────┘      └─────────────┘    └─────┬─────┘  │
│         └────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

| Node | VPN IP | Role |
|------|--------|------|
| Gateway | 10.0.0.1 | Hub, API gateway, routes all traffic |
| Service Node | 10.0.0.2 | Runs microservices (A, B, C) |
| Client | 10.0.0.3 | Initiates requests via VPN only |

## Quick Start

```bash
# 1. Generate keys and configs for all nodes
./setup_wireguard.sh

# 2. Activate on current node (e.g. gateway)
./setup_wireguard.sh --activate gateway

# 3. Verify all tunnels
./check_tunnel.sh

# 4. Tear down (keep keys)
./teardown.sh

# 5. Full teardown including keys
./teardown.sh --force --purge-keys
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_HOST` | 10.0.0.1 | Gateway public IP/hostname |
| `SERVICE_NODE_HOST` | 10.0.0.2 | Service node public IP/hostname |
| `CLIENT_NODE_HOST` | 10.0.0.3 | Client public IP/hostname |

## Security Properties

- **Split tunneling**: Only 10.0.0.0/24 routes through VPN
- **iptables isolation**: Service ports (8001-8003) blocked on eth0 — VPN only
- **IP forwarding**: Enabled only on gateway node
- **Key permissions**: Private keys chmod 600, stored in `./keys/`
- **Idempotent**: All scripts safe to run multiple times

## File Structure

```
wireguard/
├── setup_wireguard.sh      # Key generation + config
├── check_tunnel.sh         # Connectivity verification
├── teardown.sh             # Clean removal
├── gateway/
│   └── wg0.conf            # Gateway WireGuard config
├── service-node/
│   └── wg0.conf            # Service node config
├── client/
│   └── wg0.conf            # Client config
└── keys/                   # Generated keys (gitignored)
    ├── gateway_private.key
    ├── gateway_public.key
    ├── service-node_private.key
    ├── service-node_public.key
    ├── client_private.key
    └── client_public.key
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `wg0` not found | Run `setup_wireguard.sh --activate <node>` |
| Ping fails | Check `Endpoint` IPs in conf files match actual hosts |
| Handshake never completes | Verify UDP 51820 is open in cloud firewall |
| Key mismatch | Delete `./keys/` and re-run `setup_wireguard.sh` |

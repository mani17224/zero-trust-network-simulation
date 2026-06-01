# PKI Certificate Authority — Zero Trust Network Simulation

## PKI Hierarchy

```
Root CA (10 years)              — Vault pki/
  └── Intermediate CA (1 year)  — Vault pki_int/
        ├── gateway.zerotrust.local     (24h)
        ├── service-a.zerotrust.local   (24h)
        ├── service-b.zerotrust.local   (24h)
        ├── service-c.zerotrust.local   (24h)
        └── monitoring.zerotrust.local  (24h)
```

## Quick Start

```bash
# 1. Start Vault (via Docker Compose or local)
docker compose up vault -d

# 2. Initialize Vault + create CA hierarchy
./setup_vault.sh

# 3. Issue certificates for all services
./issue_certs.sh

# 4. Verify mTLS handshakes between services
./verify_mtls.sh

# 5. Renew certs approaching expiry (run via cron)
./renew_certs.sh
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VAULT_ADDR` | `http://127.0.0.1:8200` | Vault server address |
| `VAULT_TOKEN` | (from file) | Vault root token |
| `VAULT_TOKEN_FILE` | `./vault_root_token` | File containing root token |
| `VAULT_UNSEAL_FILE` | `./vault_unseal_keys` | File containing unseal key |
| `DOMAIN` | `zerotrust.local` | Base domain for all certs |
| `RENEW_THRESHOLD` | `86400` | Seconds before expiry to trigger renewal |

## Certificate Files (per service)

```
certs/<service>/
├── cert.pem         # Service certificate (PEM)
├── key.pem          # Private key (PEM, chmod 600)
├── ca_chain.pem     # CA certificate chain
├── fullchain.pem    # cert.pem + ca_chain.pem (for nginx)
├── issuing_ca.pem   # Intermediate CA cert
└── root_ca.pem      # Root CA cert
```

## Cron Job for Auto-Renewal

```cron
# Renew certificates every hour if < 24h remaining
0 * * * * /path/to/zero-trust-simulation/certs/renew_certs.sh >> /var/log/cert-renewal.log 2>&1
```

## Security Properties

| Property | Value |
|----------|-------|
| Root CA key bits | RSA 4096 |
| Intermediate CA key bits | RSA 2048 |
| Service cert key bits | RSA 2048 |
| Root CA TTL | 10 years |
| Intermediate CA TTL | 1 year |
| Service cert TTL | 24 hours |
| Certificate usage | `server_flag=true`, `client_flag=true` |

## mTLS Enforcement

All services require a valid client certificate signed by the intermediate CA:

```bash
# Example mTLS request using curl
curl \
  --cert certs/gateway/cert.pem \
  --key  certs/gateway/key.pem \
  --cacert certs/gateway/ca_chain.pem \
  https://service-a.zerotrust.local:8001/health
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Vault is sealed` | Run `./setup_vault.sh` to unseal |
| `PKI role not found` | Re-run `./setup_vault.sh` to create role |
| `Certificate verify failed` | Check `ca_chain.pem` includes full chain |
| `Permission denied on key.pem` | Run `chmod 600 certs/<service>/key.pem` |
| Cert expired | Run `./renew_certs.sh` immediately |

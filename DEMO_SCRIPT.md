# Demo Script — Zero Trust Network Simulation
## College Presentation Guide

**Total demo time:** ~15 minutes  
**Audience:** Computer Science / Security students and faculty  
**Setup:** Docker Compose stack running, browser open to http://localhost:3000

---

## Pre-Demo Checklist

```bash
# Ensure all containers are healthy
docker compose ps

# Verify gateway is responding
curl http://localhost:8000/health

# Open browser tabs:
# Tab 1: http://localhost:3000        (Dashboard)
# Tab 2: http://localhost:3000/logs   (Audit Logs)
# Tab 3: http://localhost:3000/certificates (Certs)
# Terminal: ready for curl commands
```

---

## Scenario 1: Authorized Request → Allowed (3 min)

**Talking points:**
> "In a Zero Trust system, even internal services must prove their identity on every request. Watch what happens when the gateway — a trusted, registered service — tries to read records."

**Demo steps:**

```bash
# 1. Show the request going through (terminal)
curl -s -H "X-Client-Cert-CN: gateway.zerotrust.local" \
     http://localhost:8000/records | python3 -m json.tool

# Expected: 200 OK with paginated records
```

**Show in dashboard:**
1. Switch to **Dashboard** tab → point to "Allowed" counter incrementing
2. Switch to **Audit Logs** tab → highlight the new `allow` row at the top (green)
3. Point out: **subject=gateway**, **resource=/records**, **method=GET**, **decision=allow**
4. Point out the **latency_ms** column — OPA evaluates in < 5ms

**Key point to make:**
> "Notice three layers of verification: the WireGuard VPN encrypted the connection at the network level, the mTLS certificate proved the caller's identity, and OPA's Rego policy confirmed the gateway has the `reader` role needed for GET requests."

---

## Scenario 2: Unauthorized Service → 403 Denied (3 min)

**Talking points:**
> "What happens when a service tries to do something beyond its permissions? Service-A only has the `reader` role — it cannot create or delete records."

**Demo steps:**

```bash
# 2a. service-a (reader only) tries to POST /records
curl -s -X POST \
     -H "X-Client-Cert-CN: service-a.zerotrust.local" \
     -H "Content-Type: application/json" \
     -d '{"title":"Unauthorized Write","content":"hack attempt"}' \
     http://localhost:8000/records | python3 -m json.tool

# Expected: 403 Forbidden
# {
#   "error": "forbidden",
#   "message": "access denied: subject lacks required role for this resource",
#   "subject": "service-a",
#   "resource": "/records",
#   "method": "POST"
# }
```

```bash
# 2b. Even gateway (writer+reader, not admin) cannot access service-c
curl -s -H "X-Client-Cert-CN: gateway.zerotrust.local" \
     http://localhost:8000/users | python3 -m json.tool

# Expected: 403
# "message": "access denied: service-c requires admin role"
```

**Show in dashboard:**
1. **Audit Logs** → filter by Decision: **Deny** → highlight red rows
2. **Dashboard** → "Denied" counter is non-zero, chart shows deny spike
3. Show the **reason** column — OPA provides a human-readable explanation

**Key point to make:**
> "OPA denied this at the policy level before the request ever reached Service-B. The microservice never saw the request. This is the 'never trust, always verify' principle — even internal services are treated as potentially compromised."

---

## Scenario 3: Expired Certificate → Connection Rejected (3 min)

**Talking points:**
> "In Zero Trust, certificates have very short lifetimes — 24 hours in our case. An expired cert means the service's identity can no longer be trusted."

**Demo steps:**

```bash
# Show cert expiry status
cd certs && bash renew_certs.sh
```

**Show in dashboard:**
1. Switch to **Certificate Manager** tab
2. Point to any cert with **red "Expired"** badge (service-b in demo data)
3. Show the **days remaining** column — certs with < 7 days are yellow
4. Click **Renew** button on an expiring cert → show it refreshes to green

```bash
# Simulate expired cert attempt (shows what would happen)
# In real mTLS, the TLS handshake itself fails before HTTP
curl -s --cacert certs/gateway/ca_chain.pem \
     https://localhost:8000/health 2>&1 | head -5
# Would show: SSL: CERTIFICATE_VERIFY_FAILED
```

**Key point to make:**
> "Short-lived certificates reduce the window of opportunity for an attacker who compromises a certificate. Our `renew_certs.sh` script can run as a cron job to auto-renew before expiry — zero human intervention required."

---

## Scenario 4: Live OPA Policy Change → Instant Effect (4 min)

**Talking points:**
> "The real power of OPA is that you can update policies without restarting any service. Watch this."

**Demo steps:**

```bash
# 4a. First, confirm gateway CAN currently read records
curl -s -H "X-Client-Cert-CN: gateway.zerotrust.local" \
     http://localhost:8000/records -o /dev/null -w "%{http_code}\n"
# Expected: 200
```

```bash
# 4b. Update the OPA data to remove gateway's reader role
# (Temporarily patch data.json for demo)
docker exec opa sh -c "cat /policies/data.json" | \
  python3 -c "
import json, sys
d = json.load(sys.stdin)
d['roles']['gateway'] = []   # Remove all roles from gateway
print(json.dumps(d, indent=2))
" > /tmp/patched_data.json

# Reload OPA with new policy (via OPA's bundle API)
# In production you'd commit to git and CI/CD would push
```

```bash
# 4c. Now the same gateway request is denied
curl -s -H "X-Client-Cert-CN: gateway.zerotrust.local" \
     http://localhost:8000/records | python3 -m json.tool
# Expected: 403 - instantly, no restart needed
```

**Show in dashboard:**
1. **Policy Manager** tab → toggle "Service-B: Reader GET" off
2. **Audit Logs** tab → see the next gateway request get denied
3. Toggle it back on → requests are allowed again

**Key point to make:**
> "We changed authorization policy in real-time without touching any service code, restarting any container, or deploying anything. OPA decouples the authorization decision from the application logic — this is the Open Policy Agent's killer feature."

---

## Q&A Talking Points

**"Why 24-hour certificates instead of longer ones?"**
> Short TTLs limit the blast radius of a compromised private key. If an attacker gets our gateway's key, they have at most 24 hours before that key is useless. Combined with Vault's CRL, we can revoke it even sooner.

**"What's the performance impact of calling OPA on every request?"**
> We measured P95 OPA latency at under 5ms. With our 10-second cache, frequently-used decisions don't even hit OPA — they're served from memory. The Grafana dashboard shows OPA latency histogram in real-time.

**"How is this different from a VPN?"**
> WireGuard gives us encrypted network connectivity — that's the VPN layer. But VPN alone says nothing about *what* you're allowed to do once connected. OPA + mTLS adds identity-aware authorization on top of the encrypted tunnel.

**"Can this scale to hundreds of services?"**
> Yes. OPA can handle thousands of decisions per second. The role assignments in `data.json` can be replaced with a Vault secret or a database query. The gateway pattern means you only deploy OPA integration once, not in every service.

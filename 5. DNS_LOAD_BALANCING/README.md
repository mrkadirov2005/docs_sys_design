# DNS & Load Balancing

> Scope: how domain names become IP addresses and how traffic is distributed
> across servers. Covers the full DNS resolution pipeline, record types, caching,
> security, and the load-balancing techniques that build on top of DNS.
>
> Source: extracted and reorganised from `md/DOCUMENTATIONS ...md` → `SYSTEM_DESIGN vs BACKEND` →
> `PREVIOUS, OSI LAYERS, API DESIGN, Networking Essentials` → `DNS & Load Balancing`.

---

# 1. DNS (Domain Name System)

## 1.1 Definition

DNS is a **distributed system** that translates human-readable domain names (like
`example.com`) into IP addresses (like `93.184.216.34`) so that computers can find
and communicate with each other over the network.

Without DNS, every website visit would require typing a numeric IP address. DNS is
often called the **phonebook of the internet**.

## 1.2 DNS Hierarchy

DNS is organised in a strict hierarchy. A query travels down the tree until an
authoritative answer is found.

### Root DNS Servers

- Represented as `.` (a single dot).
- There are 13 logical root server clusters (A through M), but hundreds of physical
  instances distributed globally.
- Distributed using **anycast** — the same IP address is announced from many locations,
  and the network routes each query to the nearest one.
- Root servers do not know the final answer; they point you to the correct **TLD server**.

### TLD Servers (Top-Level Domain)

- **gTLD** (generic): `.com`, `.org`, `.net`, `.io`
- **ccTLD** (country-code): `.uz`, `.uk`, `.de`, `.jp`
- TLD servers know which **authoritative name server** is responsible for each domain
  registered under that TLD.

### Authoritative DNS Servers

- Contain the **actual DNS records** for a domain.
- Return the final answer: the IP address (or other record data) for the queried name.
- Common record types held here:

| Record | Purpose | Example |
| --- | --- | --- |
| `A` | Maps domain to IPv4 address | `example.com → 93.184.216.34` |
| `AAAA` | Maps domain to IPv6 address | `example.com → 2606:2800:220:1:...` |
| `MX` | Mail exchange server | `example.com → mail.example.com` |
| `CNAME` | Alias — points one name to another | `www.example.com → example.com` |
| `TXT` | Arbitrary text (SPF, DKIM, verification) | `"v=spf1 include:_spf.google.com ~all"` |

## 1.3 Key Terms

| Term | Meaning | Example |
| --- | --- | --- |
| **DNS** | Domain Name System | The entire resolution infrastructure |
| **TLD** | Top-Level Domain | `.com`, `.org`, `.uz` |
| **SLD** | Second-Level Domain | `example` in `example.com` |
| **RD** | Root Domain (the trailing dot) | `.` |

A fully qualified domain name (FQDN) reads right to left:
`www.example.com.` → `.` (root) → `com` (TLD) → `example` (SLD) → `www` (subdomain).

## 1.4 ISP vs DNS Resolver

These two are often confused because your ISP usually provides both, but they are
fundamentally different services.

| Concept | ISP | DNS Resolver |
| --- | --- | --- |
| What it is | Infrastructure provider — the physical connection to the internet | Directory service — translates domain names to IP addresses |
| Analogy | The road system | The address book / GPS |
| Can you swap it? | Switching ISP means changing contracts | Switching DNS is one settings change |
| Examples | Comcast, BT, Beeline | Google DNS (`8.8.8.8`), Cloudflare (`1.1.1.1`) |

## 1.5 DNS Resolver Deep Behaviour

A **Recursive DNS Resolver** performs the full DNS lookup on behalf of the client.
The client sends a single query; the resolver handles everything: recursion, caching,
retries, and optimisation.

- The client (browser, OS stub resolver) sends one recursive query to the resolver.
- The resolver walks the hierarchy: Root → TLD → Authoritative.
- Results are cached according to the record's **TTL**.
- If the cache already has the answer, no hierarchy walk is needed — the resolver
  returns immediately.

Well-known public resolvers:

| Provider | Primary | Secondary |
| --- | --- | --- |
| Google Public DNS | `8.8.8.8` | `8.8.4.4` |
| Cloudflare | `1.1.1.1` | `1.0.0.1` |
| Quad9 | `9.9.9.9` | `149.112.112.112` |

## 1.6 DNS Transport

DNS uses **UDP on port 53** by default. UDP is preferred because DNS queries are small
and the overhead of a TCP handshake is unnecessary for most lookups.

TCP (also port 53) is used when:

- The response exceeds 512 bytes (the original UDP limit) or the EDNS0 buffer size.
- **Zone transfers** (AXFR/IXFR) between primary and secondary name servers.
- **DNSSEC** responses, which tend to be large due to cryptographic signatures.

Modern encrypted DNS transports:

- **DNS over HTTPS (DoH)** — port 443, looks like normal HTTPS traffic.
- **DNS over TLS (DoT)** — port 853, dedicated encrypted channel.

## 1.7 DNS Packet Structure

Every DNS message (query and response) follows the same packet format:

| Section | Contents |
| --- | --- |
| **Header** | Transaction ID, Flags (QR, Opcode, AA, TC, RD, RA, RCODE), Question Count, Answer Count, Authority Count, Additional Count |
| **Question** | The domain name being queried, query Type (A, AAAA, MX...), query Class (usually IN for Internet) |
| **Answer** | Resource Records: the IP address (or other data), TTL, record type |
| **Authority** | NS records for the authoritative name servers for the zone |
| **Additional** | Glue records — IP addresses of name servers listed in the Authority section, so an extra lookup is avoided |

```
+---------------------+
|       Header        |  ID, Flags, Counts
+---------------------+
|      Question       |  What are you asking?
+---------------------+
|       Answer        |  Here is the IP
+---------------------+
|     Authority       |  Who is authoritative?
+---------------------+
|     Additional      |  Glue records
+---------------------+
```

## 1.8 Zone Files & Zones

### What is a Zone?

A **zone** is a portion of the DNS namespace that is managed by a specific authoritative
DNS server. A domain can be split into multiple zones — for example, `example.com`
could delegate `us.example.com` to a separate zone with its own name server.

### Zone vs Domain

- A **domain** is a name in the hierarchy (`example.com`).
- A **zone** is the administrative boundary — the set of records one server is
  authoritative for.
- A domain can span multiple zones (via delegation), but a zone always belongs to
  exactly one authoritative server (or its replicas).

### What is a Zone File?

A **zone file** is a plain-text file stored on the authoritative server. It contains
the actual DNS records for that zone.

```
$TTL 3600
@   IN  SOA   ns1.example.com. admin.example.com. (
            2024010101 ; Serial
            3600       ; Refresh
            900        ; Retry
            604800     ; Expire
            86400 )    ; Minimum TTL

@   IN  NS    ns1.example.com.
@   IN  NS    ns2.example.com.
@   IN  A     93.184.216.34
www IN  CNAME example.com.
@   IN  MX 10 mail.example.com.
mail IN A     93.184.216.35
```

### Key records in a zone file

- `$TTL` — default Time To Live for all records in the file.
- **SOA** (Start of Authority) — identifies the primary name server, contact email,
  serial number, and timing parameters.
- **NS** — name server records for the zone.
- **A / AAAA** — address records.
- **CNAME** — canonical name aliases.
- **MX** — mail exchange records with priority.

### Forward vs Reverse Lookup Zones

- **Forward lookup zone**: domain name → IP address (the normal case).
- **Reverse lookup zone**: IP address → domain name (uses `in-addr.arpa` for IPv4,
  `ip6.arpa` for IPv6).

## 1.9 DNS Caching

DNS responses are cached at multiple levels to reduce latency and load on authoritative
servers.

### Cache layers (checked in order)

1. **Browser cache** — Chrome, Firefox, etc. maintain their own DNS cache.
2. **OS cache** — the operating system's stub resolver (e.g. `systemd-resolved`,
   macOS `mDNSResponder`).
3. **Resolver cache** — the recursive DNS resolver (ISP or public DNS like `8.8.8.8`).
4. **CDN / Edge cache** — CDN providers may cache DNS responses at their edge nodes.

### How caching works

```
User types URL
    ↓
Browser cache hit? → yes → use cached IP
    ↓ no
OS cache hit?      → yes → use cached IP
    ↓ no
Resolver cache hit? → yes → use cached IP
    ↓ no
Full resolution: Root → TLD → Authoritative
    ↓
Cache the result at every level (with TTL)
```

### TTL (Time To Live)

TTL defines how long (in seconds) a DNS record may be cached before it must be
re-queried. Set by the domain owner on the authoritative server.

- **Positive caching**: caching a successful response (the normal case).
- **Negative caching**: caching the fact that a name does *not* exist (NXDOMAIN).
  Governed by the SOA record's minimum TTL.

**Cache hit**: the record is found in cache and still within its TTL — no network
query needed.
**Cache miss**: the record is not cached or the TTL has expired — a full or partial
resolution is triggered.

## 1.10 DNS Cache Poisoning

An attacker injects **fake DNS data** into a resolver's cache, causing it to return a
malicious IP address for a legitimate domain. Users are then silently redirected to
attacker-controlled servers.

### How it works

1. Attacker observes or predicts the query ID and source port of an outgoing DNS query.
2. Attacker sends a forged response before the real authoritative server replies.
3. The forged record is cached and served to all subsequent clients until the TTL expires.

### Defences

- **DNSSEC** — cryptographically signs DNS records so forged responses are detected
  and rejected.
- **Randomised query IDs** — makes it much harder for an attacker to guess the
  transaction ID.
- **Source port randomisation** — instead of using a predictable source port, each
  query uses a random one.
- **DNS over HTTPS / TLS** — encrypts the channel, preventing interception and
  injection.

## 1.11 Flushing DNS Cache

Sometimes you need to clear the local DNS cache manually:

- A domain's IP address has changed and you are still reaching the old server.
- Troubleshooting DNS resolution issues.
- Development and testing against staging/production environments.

```bash
# macOS
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder

# Windows
ipconfig /flushdns

# Linux (systemd-resolved)
sudo systemd-resolve --flush-caches
```

## 1.12 DNS Caching Strategy

Choosing the right TTL is a trade-off:

| | High TTL (e.g. 86400 — 24h) | Low TTL (e.g. 60 — 1min) |
| --- | --- | --- |
| **Speed** | Faster — most lookups served from cache | Slower — more frequent authoritative queries |
| **Load** | Less load on authoritative servers | More queries hit the authoritative server |
| **Freshness** | Risk of stale records if IP changes | Near-real-time propagation of changes |
| **Use case** | Stable services with fixed IPs | Failover, blue-green deployments, CDN steering |

> A common migration pattern: lower the TTL to 60s *before* a planned DNS change,
> wait for the old high TTL to expire, make the change, then raise the TTL back once
> the new record is confirmed.

## 1.13 Resolution Flow

The full journey from URL to IP address:

1. User enters `www.example.com` in the browser.
2. **Browser cache** — checked first. If a valid cached entry exists, done.
3. **OS cache** — the stub resolver checks the system-level cache and `/etc/hosts`.
4. **Recursive DNS Resolver** — the configured resolver (e.g. `8.8.8.8`) is queried.
5. Resolver contacts a **Root server** → gets a referral to the `.com` TLD server.
6. Resolver contacts the **TLD server** → gets a referral to `example.com`'s
   authoritative server.
7. Resolver contacts the **Authoritative server** → gets the A record: `93.184.216.34`.
8. Resolver caches the result and returns the IP to the client.
9. Browser opens a TCP connection to `93.184.216.34`.

```
Browser → OS Stub → Recursive Resolver → Root → TLD → Authoritative
                           ← IP cached & returned at each hop
```

## 1.14 Recursive vs Iterative Queries

| Aspect | Recursive Query | Iterative Query |
| --- | --- | --- |
| Who does the work? | The resolver does ALL the work and returns the final IP | Each server returns the next server to ask; the querier does the walking |
| Who uses it? | Client (browser / OS) → Recursive Resolver | Recursive Resolver → Root / TLD / Authoritative servers |
| Response type | Final answer or error | Referral: "I don't know, but ask this server" |

- The **browser / OS** always sends a **recursive query** to the configured resolver —
  "give me the answer, don't send me elsewhere."
- The **resolver** uses **iterative queries** internally when walking the hierarchy
  (Root → TLD → Authoritative).
- When the resolver already has the answer cached, it returns a **non-recursive
  response** immediately — no hierarchy walk needed.

## 1.15 PTR Records

A **PTR (Pointer) record** performs a **reverse DNS lookup** — it maps an IP address
back to a domain name. This is the opposite of an A record.

- IPv4 reverse lookups use the `in-addr.arpa` domain. The IP octets are reversed:
  `93.184.216.34` becomes `34.216.184.93.in-addr.arpa`.
- IPv6 reverse lookups use the `ip6.arpa` domain, with each hex nibble reversed.

### Use cases

- **Email spam filtering** — mail servers check whether the sending IP has a valid
  PTR record matching the mail domain. No PTR often means rejection.
- **Security auditing and logging** — turning IP addresses in logs into readable
  hostnames.
- **Network troubleshooting** — `traceroute` and similar tools use reverse DNS to
  show hostnames alongside IP addresses.

```bash
# Reverse lookup with dig
dig -x 93.184.216.34

# Reverse lookup with nslookup
nslookup 93.184.216.34
```

## 1.16 DNS Propagation

When DNS records are changed (new IP, new MX, etc.), the update does **not take effect
globally at once**. Caches at every level — browser, OS, resolver, CDN — hold the old
record until its TTL expires. This delay is called **DNS propagation**.

- Propagation can take anywhere from minutes to 48 hours, depending on TTL values
  across the caching chain.
- Lowering TTL before a planned change reduces propagation time.
- There is no way to force every cache on the internet to flush simultaneously.

## 1.17 Anycast

**Anycast** is a network addressing method where the **same IP address** is announced
from multiple physical locations. The network's routing protocol (BGP) automatically
sends each client to the **nearest instance**.

- DNS root servers use anycast — all 13 logical root servers share the same set of
  IPs, but hundreds of physical nodes answer worldwide.
- Benefits: **lower latency** (shortest-path routing), **DDoS resilience** (attack
  traffic is absorbed across all nodes), and **automatic failover** (if one node goes
  down, traffic reroutes to the next nearest).
- CDNs and public DNS resolvers (Cloudflare `1.1.1.1`) rely heavily on anycast.

## 1.18 Q&A

**Do developers choose between recursive and iterative queries?**
No. The query type is determined automatically by the software. The client (browser/OS)
always sends a recursive query. The resolver uses iterative queries internally.
Developers do not normally configure this.

**Can I force a specific query type?**
For diagnostic purposes, `dig` and `nslookup` allow control. `dig +norecurse` sends a
non-recursive (iterative-style) query. But in production applications, you use the
system resolver and it handles everything.

```bash
# dig with recursion (default)
dig example.com

# dig without recursion (iterative-style, for diagnostics)
dig +norecurse example.com

# nslookup
nslookup example.com 8.8.8.8
```

**What happens if all root servers go down?**
In practice this has never happened. Anycast distribution, geographic redundancy, and
aggressive caching at every level make a total root server outage effectively
impossible. Even if reachability were lost temporarily, cached records would continue
to function until their TTL expired.

---

# 2. Load Balancing

Load balancing distributes incoming traffic across multiple backend servers to improve
availability, reliability, and performance. This section covers the concepts most
tightly connected to DNS.

## 2.1 VIPs (Virtual IPs)

A **Virtual IP (VIP)** is a single IP address that maps to multiple backend servers.
Clients connect to the VIP; the load balancer decides which backend server actually
handles each request.

- The VIP is what DNS points to — an A record for `api.example.com` resolves to the
  VIP, not to individual server IPs.
- Backends can be added, removed, or replaced without changing the DNS record.
- Health checks ensure that only healthy backends receive traffic.

## 2.2 Proxy Servers

| Type | Direction | Purpose | Examples |
| --- | --- | --- | --- |
| **Forward proxy** | Client-side | Sits between the client and the internet. Anonymises requests, filters content, caches responses. | Squid, corporate proxies |
| **Reverse proxy** | Server-side | Sits in front of backend servers. Distributes load, terminates TLS, caches content, provides a single entry point. | Nginx, HAProxy, Envoy, AWS ALB |

> A reverse proxy **is** the most common form of load balancer in web infrastructure.
> DNS points clients to the reverse proxy's VIP; the proxy fans traffic out to backend
> servers.

## 2.3 DNS-based Load Balancing

DNS itself can distribute traffic without a separate load balancer, though with less
control.

### Round-robin DNS

Multiple A records are returned for the same domain. Clients (or resolvers) rotate
through the list, distributing requests across servers.

```
example.com.  300  IN  A  10.0.0.1
example.com.  300  IN  A  10.0.0.2
example.com.  300  IN  A  10.0.0.3
```

- Simple, no extra infrastructure.
- No health checking — DNS will continue returning a dead server's IP until the record
  is manually removed.
- No session awareness — consecutive requests from the same client may go to different
  servers.

### GeoDNS

The authoritative DNS server returns different IP addresses based on the **geographic
location** of the client (determined by the source IP of the query). Users in Europe
get European servers; users in Asia get Asian servers.

### Anycast routing

As described in section 1.17, the same IP is announced from multiple data centres. BGP
routing sends each client to the nearest one. This is load balancing at the network
layer, entirely transparent to DNS.

## 2.4 Where Load Balancing Connects to DNS

The two systems work together in layers:

1. **DNS resolves the domain** to one or more IP addresses (VIPs or direct server IPs).
2. **The load balancer at that IP** (if present) distributes each connection to a
   healthy backend.

```
Client → DNS resolution → VIP (e.g. 203.0.113.10)
                                ↓
                         Load Balancer
                        /      |      \
                  Server A  Server B  Server C
```

In large-scale systems, these are combined:

- **GeoDNS** picks the closest data centre (DNS layer).
- **Anycast** routes to the nearest edge node within that data centre's address space
  (network layer).
- **Reverse proxy / L7 load balancer** (Nginx, Envoy) distributes requests to backend
  instances (application layer).

---

# 3. Quick Revision Sheet

| Question | Answer |
| --- | --- |
| What does DNS do? | Translates domain names to IP addresses |
| DNS hierarchy order | Root (`.`) → TLD (`.com`) → Authoritative → Record |
| Default transport | UDP port 53; TCP for large responses, zone transfers, DNSSEC |
| Recursive vs Iterative | Client sends recursive to resolver; resolver uses iterative to walk the hierarchy |
| What is a zone file? | Plain-text file with SOA, NS, A, CNAME, MX records for a zone |
| TTL | How long a cached DNS record is valid (seconds) |
| Cache layers (order) | Browser → OS → Resolver → CDN/Edge |
| Cache poisoning defence | DNSSEC, randomised query IDs, source port randomisation |
| PTR record | Reverse lookup: IP → domain (`in-addr.arpa`) |
| Anycast | Same IP, many locations; BGP routes to nearest |
| VIP | Single IP mapping to multiple backend servers |
| Forward vs Reverse proxy | Forward = client-side; Reverse = server-side (Nginx, HAProxy) |
| Round-robin DNS | Multiple A records; no health checks, no session affinity |
| GeoDNS | Returns IPs based on client location |
| DNS propagation | Delay for changes to reach all caches; driven by TTL |

**One sentence each**

- **DNS** is the distributed phonebook that turns names into numbers so the internet
  works without memorising IP addresses.
- **Load balancing** spreads traffic across servers so no single machine bears the full
  load, using DNS, VIPs, and reverse proxies as complementary mechanisms.

---

**Previous:** [OSI Layers 5, 6 & 7 — Session, Presentation & Application](../OSI_LAYERS_5-6-7_SESSION_PRESENTATION_APPLICATION/README.md)

**Next:** [HTTP Evolution — HTTP/1.1, HTTP/2 & HTTP/3](../HTTP_EVOLUTION_HTTP1.1_HTTP2_HTTP3/README.md)

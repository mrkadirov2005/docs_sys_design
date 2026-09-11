# HTTP Evolution — HTTP/1.1, HTTP/2 & HTTP/3

> Scope: how the web talks. The full lifecycle of an HTTP request, every method, header,
> status code, caching layer, and the protocol evolution from HTTP/0.9 through HTTP/3
> and QUIC.
>
> Source: extracted and reorganised from `md/DOCUMENTATIONS ...md` → `SYSTEM_DESIGN vs BACKEND`
> → `HTTP Evolution`.

---

## 0. What this document covers

| Topic | One-line summary |
| --- | --- |
| HTTP fundamentals | Stateless request/response protocol over TCP (HTTPS adds TLS) |
| Methods | GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS, CONNECT, TRACE |
| Headers & body | Metadata envelope + payload |
| Status codes | 2xx success, 3xx redirect, 4xx client error, 5xx server error |
| State & idempotency | How a stateless protocol remembers things, and which methods are safe to retry |
| Version evolution | HTTP/0.9 → 1.0 → 1.1 → 2 → 3 (QUIC/UDP) |
| Caching | Browser cache, CDN cache, server cache, ETags, Cache-Control |

---

# 1. HTTP Fundamentals

## 1.1 Definition

**HTTP (HyperText Transfer Protocol)** is a stateless, application-layer protocol for
communication between a client and a server. It runs on top of TCP; when the connection
is secured, HTTPS wraps TCP in a TLS handshake before any HTTP bytes are exchanged.

- **Stateless** — the server does not remember previous requests. Each request is
  independent.
- **Text-based** (HTTP/1.x) or **binary-framed** (HTTP/2+).
- **Request/response** model — the client always initiates; the server always replies
  (server push in HTTP/2 is the exception).

## 1.2 Request lifecycle

1. User enters a URL in the browser.
2. **DNS resolution** — the domain name is translated into an IP address.
3. **TCP connection** — a three-way handshake (`SYN`, `SYN-ACK`, `ACK`) opens the
   connection.
4. **TLS handshake** (HTTPS only) — negotiates cipher suite, exchanges certificates,
   derives session keys.
5. Client sends an **HTTP request** (method, path, headers, optional body).
6. Server processes the request and sends an **HTTP response** (status code, headers,
   body).
7. Connection is **reused** (HTTP/1.1 Keep-Alive) or **closed**.

---

# 2. HTTP Methods

## 2.1 GET

Retrieve a resource without modification. Safe and idempotent.

```
GET /users/42 HTTP/1.1
Host: api.example.com
```

## 2.2 POST

Send data to create or update a resource. **Not idempotent** — sending the same POST
twice may create two records.

```
POST /users HTTP/1.1
Content-Type: application/json

{"name": "Alice", "email": "alice@example.com"}
```

## 2.3 PUT

Create or **fully replace** a resource at a specific URL. Idempotent — sending the same
PUT ten times yields the same result as sending it once.

```
PUT /users/42 HTTP/1.1
Content-Type: application/json

{"name": "Alice", "email": "alice@new.com"}
```

## 2.4 PATCH

Apply **partial modifications** to an existing resource. Not necessarily idempotent — a
patch like `{"views": "+1"}` changes the result each time.

```
PATCH /users/42 HTTP/1.1
Content-Type: application/json

{"email": "alice@new.com"}
```

## 2.5 DELETE

Remove a specified resource. Idempotent — deleting a resource that is already gone
returns the same outcome.

```
DELETE /users/42 HTTP/1.1
```

## 2.6 HEAD

Identical to GET but returns **only the headers**, no body. Used to check if a resource
exists, its size, or its last-modified date without downloading it.

```
HEAD /large-file.zip HTTP/1.1
```

## 2.7 OPTIONS

Request information about the communication options available for a resource. Commonly
seen in CORS preflight requests.

```
OPTIONS /api/data HTTP/1.1
Origin: https://app.example.com
```

## 2.8 CONNECT

Establish a **bidirectional tunnel** through a proxy. The proxy becomes a transparent
relay for raw TCP bytes.

```
CONNECT api.example.com:443 HTTP/1.1
Host: api.example.com
```

**Use cases:**

- **HTTPS via proxy** — the browser asks the proxy to tunnel TLS traffic to the
  destination.
- **Proxy tunnelling** — any TCP-based protocol (SSH, database) wrapped through an HTTP
  proxy.
- **Bypassing network restrictions** — tunnel traffic past restrictive firewalls.
- **Debugging and testing** — inspect traffic through an intercepting proxy.

## 2.9 TRACE

Diagnostic tool that asks the server to echo back the exact request it received.

> **Security note:** TRACE should be **disabled in production**. It enables Cross-Site
> Tracing (XST) attacks, where an attacker tricks a browser into issuing a TRACE request
> to steal cookies or authorization headers reflected in the response.

### Methods at a glance

| Method | Purpose | Body? | Idempotent? | Safe? |
| --- | --- | --- | --- | --- |
| GET | Read | No | Yes | Yes |
| POST | Create / process | Yes | No | No |
| PUT | Replace | Yes | Yes | No |
| PATCH | Partial update | Yes | No* | No |
| DELETE | Remove | Optional | Yes | No |
| HEAD | Read headers only | No | Yes | Yes |
| OPTIONS | Describe options | No | Yes | Yes |
| CONNECT | Tunnel | No | No | No |
| TRACE | Echo / debug | No | Yes | Yes |

\* PATCH *can* be idempotent if the patch document is a full replacement, but the spec
does not require it.

---

# 3. HTTP Headers

## 3.1 Definition

Headers are **metadata** attached to every HTTP request and response — like the label on
an envelope. They tell each side who is talking, what format the data is in, how long it
can be cached, and how to authenticate.

```
GET /api/users HTTP/1.1
Host: api.example.com
Accept: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

## 3.2 Header categories

### Request headers

Sent by the browser or client. Describe **who is asking and what they want**.

| Header | Purpose | Example |
| --- | --- | --- |
| `Host` | Target hostname (required in HTTP/1.1) | `Host: api.example.com` |
| `Accept` | Preferred response format | `Accept: application/json` |
| `User-Agent` | Client software identifier | `User-Agent: Mozilla/5.0 ...` |
| `Authorization` | Credentials for authentication | `Authorization: Bearer <token>` |
| `Cookie` | Previously stored cookies | `Cookie: session_id=abc123` |

### Response headers

Sent by the server. Describe **what is being returned and how to handle it**.

| Header | Purpose | Example |
| --- | --- | --- |
| `Content-Type` | Body media type | `Content-Type: application/json` |
| `Content-Length` | Body size in bytes | `Content-Length: 1024` |
| `Set-Cookie` | Store a cookie on the client | `Set-Cookie: id=abc; HttpOnly` |
| `Cache-Control` | Caching directives | `Cache-Control: max-age=3600` |
| `ETag` | Resource fingerprint for validation | `ETag: "33a64df5"` |

### General headers

Appear on **both** request and response. Not specific to the body.

- `Cache-Control` — caching directives for both directions.
- `Connection` — whether to keep the connection alive or close it.
- `Date` — timestamp of the message.

### Entity / representation headers

Describe the **body content itself**.

- `Content-Type` — media type of the body (`application/json`, `text/html`).
- `Content-Length` — size in bytes.
- `Content-Encoding` — compression applied (`gzip`, `br`).

## 3.3 Authorization

How a client proves its identity to the server.

| Scheme | How it works | When to use |
| --- | --- | --- |
| **Basic Auth** | Base64-encoded `username:password` in every request | Internal tools, always over HTTPS |
| **Bearer / JWT** | Client sends a signed token; server verifies the signature | Most modern APIs |
| **API Key** | Static key in header or query param | Machine-to-machine calls |

```
# Basic
Authorization: Basic dXNlcjpwYXNz

# Bearer / JWT
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# API Key (header)
X-API-Key: sk-abc123
```

## 3.4 Content-Type

Tells the server (request) or the client (response) **what type of data** the body
contains.

| Value | Use |
| --- | --- |
| `application/json` | JSON API payloads |
| `application/x-www-form-urlencoded` | Classic HTML form submissions |
| `multipart/form-data` | File uploads |
| `text/html` | Web pages |
| `text/plain` | Plain text |

---

# 4. HTTP Body

## 4.1 Definition

The body is the part of an HTTP message that carries the **actual data** being sent. Not
every request or response has one — a GET request typically has no body, and a `204 No
Content` response has no body by definition.

## 4.2 Request body

Sent by the client in methods that carry data: **POST**, **PUT**, **PATCH**.

```
POST /api/orders HTTP/1.1
Content-Type: application/json

{
  "product_id": 101,
  "quantity": 2
}
```

## 4.3 Response body

Sent by the server. Contains the resource data, an HTML page, a JSON payload, an error
message, or nothing at all.

```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "id": 42,
  "name": "Alice",
  "email": "alice@example.com"
}
```

## 4.4 Common content types

- **JSON** — `application/json`. The default for modern APIs.
- **Form data** — `application/x-www-form-urlencoded` or `multipart/form-data`.
- **Files** — any MIME type (`image/png`, `application/pdf`, etc.).
- **Plain text** — `text/plain`.
- **HTML** — `text/html`.

---

# 5. Status Codes

Every HTTP response carries a three-digit status code that tells the client what
happened.

| Range | Category | Meaning |
| --- | --- | --- |
| **1xx** | Informational | Request received, processing continues |
| **2xx** | Success | Request accepted and processed |
| **3xx** | Redirection | Further action needed (follow a new URL) |
| **4xx** | Client error | Bad request, not found, not authorised |
| **5xx** | Server error | Server failed to fulfil a valid request |

### Common codes worth memorising

| Code | Name | When |
| --- | --- | --- |
| 200 | OK | Standard success |
| 201 | Created | Resource created (POST, PUT) |
| 204 | No Content | Success, no body (DELETE) |
| 301 | Moved Permanently | URL changed forever, update bookmarks |
| 302 | Found | Temporary redirect |
| 304 | Not Modified | Cache is still valid |
| 400 | Bad Request | Malformed syntax or invalid parameters |
| 401 | Unauthorised | Authentication required or failed |
| 403 | Forbidden | Authenticated but not authorised |
| 404 | Not Found | Resource does not exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Generic server failure |
| 502 | Bad Gateway | Upstream server returned invalid response |
| 503 | Service Unavailable | Server overloaded or in maintenance |
| 504 | Gateway Timeout | Upstream server did not respond in time |

---

# 6. Handling State

HTTP is stateless — the server does not remember anything between requests. Every
mechanism for "remembering" a user is built *on top of* HTTP, not inside it.

| Mechanism | Where it lives | How it works |
| --- | --- | --- |
| **Cookies** | Browser ↔ server (header) | Server sends `Set-Cookie`; browser attaches `Cookie` header on every subsequent request to that domain. |
| **Sessions** | Server-side store | Server creates a session object, gives the client a session ID (usually in a cookie). State lives on the server. |
| **Tokens (JWT)** | Client-side (header / storage) | Server issues a signed token containing claims. Client sends it in `Authorization: Bearer`. Server verifies the signature — no server-side lookup needed. |

---

# 7. Idempotency

## 7.1 Definition

A request is **idempotent** if making it multiple times produces the **same final state**
as making it once. This is about the state on the server, not about the response body — a
DELETE that returns `200` the first time and `404` the second time is still idempotent
because the server state after both calls is the same: the resource is gone.

## 7.2 By method

| Method | Idempotent? | Why |
| --- | --- | --- |
| GET | Yes | Reading does not change state |
| PUT | Yes | Full replacement — same input, same result |
| DELETE | Yes | Deleting twice = resource still gone |
| HEAD | Yes | Same as GET, no body |
| OPTIONS | Yes | Describes capabilities, no side effects |
| POST | **No** | Creates new resources — two POSTs may create two records |
| PATCH | **No** | Depends on the patch semantics (increment operations are not idempotent) |
| CONNECT | **No** | Opens a new tunnel each time |

> **Why it matters:** idempotent methods are safe to retry on network failure. If a PUT
> times out and you resend it, you get the same result. If a POST times out and you
> resend it, you might create a duplicate. This is why payment APIs use idempotency keys.

---

# 8. HTTP Version Evolution

This is the core of the topic. Each version solved the previous version's biggest pain
point — and introduced the next one.

## 8.0 HTTP/0.9

The original 1991 protocol. One-line requests, HTML-only responses, no headers, no
status codes. A historical footnote — not used today.

```
GET /page.html
```

## 8.1 HTTP/1.0

Introduced headers, status codes, and content types. But every request required a **new
TCP connection**.

- One request per TCP connection.
- Connection closes after each response.
- No persistent connections by default.

**Problems:**

- **Slow** — TCP handshake on every single request.
- **Latency** — a page with 20 images means 20 separate TCP connections.
- **No pipelining** — completely sequential.

```
# Request 1: open TCP → GET index.html → close TCP
# Request 2: open TCP → GET style.css  → close TCP
# Request 3: open TCP → GET logo.png   → close TCP
# ... every resource = full round-trip overhead
```

## 8.2 HTTP/1.1

The workhorse of the web for two decades (1997–2015+). Key improvements:

- **Persistent connections (Keep-Alive)** — the TCP connection stays open for multiple
  requests.
- **Pipelining** — send multiple requests without waiting for the first response (rarely
  used in practice).
- **Chunked transfer encoding** — stream a response before the server knows the total
  size.
- **Host header** — enables virtual hosting (multiple domains on one IP).
- **Improved caching** — `Cache-Control`, `ETag`, conditional requests.

```
# One TCP connection, multiple requests:
GET /index.html HTTP/1.1    → 200 OK
GET /style.css  HTTP/1.1    → 200 OK
GET /logo.png   HTTP/1.1    → 200 OK
# Connection stays open (Keep-Alive)
```

**The problem: Head-of-Line (HOL) blocking**

Requests on a single connection must be processed **sequentially**. Even though the
browser can send multiple requests, it cannot receive a later response until the previous
one is fully delivered. If one response is slow, everything behind it waits.

> **Workaround:** browsers open 6–8 parallel TCP connections per domain. This helps but
> wastes resources and does not truly solve the problem.

## 8.3 HTTP/2

Published in 2015, based on Google's SPDY. A major upgrade.

- **Multiplexing** — multiple requests and responses **in parallel** over a **single TCP
  connection**. No more HOL blocking at the application layer.
- **Binary framing** — data is split into binary frames, not human-readable text. More
  compact, faster to parse.
- **Header compression (HPACK)** — headers are compressed and deduplicated.
- **Server push** — the server can proactively send resources the client will need.
  Rarely used in practice and deprecated in Chrome.
- **Stream prioritisation** — the client can hint which resources are more important.

```
# Single TCP connection, interleaved streams:
Stream 1: GET /index.html  ─┐
Stream 2: GET /style.css   ─┤  all multiplexed
Stream 3: GET /app.js      ─┤  on one connection
Stream 4: GET /logo.png    ─┘
```

**The remaining problem: TCP-level HOL blocking**

HTTP/2 solves HOL blocking at the HTTP layer, but **TCP itself still has HOL blocking**.
If a single TCP packet is lost, the entire connection stalls while TCP retransmits it —
even streams whose data was not in the lost packet.

## 8.4 HTTP/3

The current generation. HTTP/3 replaces TCP entirely with **QUIC**, a transport protocol
built on **UDP**.

- **Built on QUIC (UDP-based)** — no TCP at all. QUIC handles reliability, congestion
  control, and encryption itself.
- **Faster connection setup** — QUIC combines the transport handshake and TLS handshake
  into a single round-trip (1-RTT), or even zero round-trips on reconnection (0-RTT).
- **No TCP-level HOL blocking** — QUIC streams are independent. A lost packet only
  blocks the stream it belongs to, not the entire connection.
- **Connection migration** — connections survive IP changes (e.g., switching from Wi-Fi
  to mobile data) because QUIC identifies connections by ID, not by IP+port.
- **Better performance on bad networks** — the independent-stream design means lossy
  connections degrade gracefully.

```
# The modern web stack:
HTTP/3  →  QUIC  →  UDP
 (app)    (transport)  (network)

# vs the old stack:
HTTP/1.1 or HTTP/2  →  TLS  →  TCP
     (app)           (security) (transport)
```

### Version evolution summary

| Version | Transport | Key feature | Main problem it solved | Remaining problem |
| --- | --- | --- | --- | --- |
| HTTP/0.9 | TCP | Basic GET | — | No headers, no status codes |
| HTTP/1.0 | TCP | Headers, status codes | No metadata | New TCP connection per request |
| HTTP/1.1 | TCP | Keep-Alive, chunked encoding | Connection-per-request waste | HOL blocking (application layer) |
| HTTP/2 | TCP + TLS | Multiplexing, HPACK, binary | App-layer HOL blocking | HOL blocking (TCP layer) |
| HTTP/3 | QUIC (UDP) | Independent streams, 0-RTT | TCP-level HOL blocking | UDP blocking by some firewalls |

---

# 9. HTTP Caching

## 9.1 Definition

Caching is a mechanism that **stores HTTP responses** so they can be served faster on
future requests without hitting the origin server.

### Without caching vs with caching

| | Without caching | With caching |
| --- | --- | --- |
| Every request | Hits the server | Served from cache if valid |
| Latency | Network round-trip every time | Near-instant for cache hits |
| Server load | High | Reduced |
| Bandwidth | Full response every time | Zero bytes on 304 Not Modified |

## 9.2 Caching flow

1. **First request** — browser sends request; server responds with caching headers
   (`Cache-Control`, `ETag`, `Last-Modified`).
2. **Browser stores** the response in its cache.
3. **Next request for the same resource**:
   - If the cache entry is still **valid** (not expired) → **cache hit**, served
     instantly.
   - If the cache entry is **expired** → browser sends a **conditional request**
     (`If-None-Match` or `If-Modified-Since`) to revalidate.
   - Server returns **304 Not Modified** (use the cached version) or **200 OK** with
     fresh content.

## 9.3 ETag (Entity Tag)

A **unique fingerprint** (hash) of a resource. The server sends it with the response; the
browser stores it and sends it back on the next request.

```
# First response
HTTP/1.1 200 OK
ETag: "33a64df551425fcc55e4d42a148795d9f25f89d4"

# Next request (conditional)
GET /style.css HTTP/1.1
If-None-Match: "33a64df551425fcc55e4d42a148795d9f25f89d4"

# Server response (resource unchanged)
HTTP/1.1 304 Not Modified
```

If the resource *has* changed, the server returns `200 OK` with the new content and a
new ETag.

## 9.4 Heuristic caching

When the server sends **no** `Cache-Control` or `Expires` header, the browser falls back
to a heuristic: it uses the `Last-Modified` date and caches the resource for roughly
**10% of the time since it was last modified**.

> A file last modified 100 days ago would be heuristically cached for about 10 days.
> This is why setting explicit `Cache-Control` headers is important — heuristic caching
> is unpredictable.

## 9.5 Cache-Control headers

| Directive | Meaning |
| --- | --- |
| `max-age=3600` | Cache for 3600 seconds (1 hour). After that, revalidate. |
| `no-cache` | Always revalidate with the server before using the cached version. The response *is* stored; it is just never used without checking first. |
| `no-store` | Do not cache at all. Not in memory, not on disk. |
| `public` | Any cache (browser, CDN, proxy) may store this. |
| `private` | Only the end user's browser may cache this. CDNs and proxies must not. |
| `must-revalidate` | Once expired, the cache must not serve stale content — it must revalidate. |
| `immutable` | The resource will never change. Do not even revalidate. Used with hashed filenames (`app.a1b2c3.js`). |

```
# Typical for a hashed static asset:
Cache-Control: public, max-age=31536000, immutable

# Typical for an API response:
Cache-Control: private, no-cache

# Sensitive data (bank statements, health records):
Cache-Control: no-store
```

---

# 10. CDN Caching

## 10.1 Definition

A **CDN (Content Delivery Network)** is a network of servers distributed geographically
that stores copies of content **close to users**. Instead of every request travelling to
the origin server, most requests are served by a nearby **edge node**.

## 10.2 CDN caching flow

**First request (cache miss):**

```
User  →  CDN edge (miss)  →  Origin server
                               ↓
User  ←  CDN edge (stores) ←  Response
```

**Subsequent requests (cache hit):**

```
User  →  CDN edge (hit)  →  User
         (no origin hit)
```

## 10.3 Additional CDN benefits

- **DDoS protection** — absorbs attack traffic at the edge before it reaches the origin.
- **TLS termination** — handles HTTPS at the edge, reducing load on the origin.
- **Load distribution** — spreads traffic across many servers.
- **Geographic performance** — a user in Tokyo gets content from a Tokyo edge node, not
  from a server in Virginia.

---

# 11. Server Cache

## 11.1 What to cache

- **Database query results** — expensive queries that return the same data for many
  requests.
- **Computed / aggregated data** — dashboards, analytics, leaderboards.
- **Session data** — user sessions stored in Redis or Memcached.
- **External API responses** — third-party data that does not change frequently.
- **Rendered HTML fragments** — partial page renders, template fragments.

## 11.2 Validation strategies

| Strategy | How it works |
| --- | --- |
| **TTL (Time to Live)** | Cache entry expires after a fixed duration. Simple but allows stale reads. |
| **Event-based invalidation** | When data changes, an event (webhook, message) explicitly invalidates the cache entry. |
| **Cache-aside (lazy loading)** | App checks cache first; on miss, loads from DB and writes to cache. Most common pattern. |
| **Write-through** | Every write goes to cache and DB simultaneously. Cache is always fresh but writes are slower. |
| **Cache versioning** | Append a version key to cache entries. Bump the version to invalidate all entries at once. |

## 11.3 Cache invalidation

> "There are only two hard things in computer science: cache invalidation and naming
> things." — Phil Karlton

The hard problem is knowing **when exactly to invalidate**. There is always a trade-off:

- **Consistency (freshness)** — how quickly do users see updated data?
- **Performance (fewer DB hits)** — how long can we serve from cache before checking?

There is no universal answer. The right TTL depends on the use case: a stock price needs
sub-second freshness; a blog post can be cached for hours.

---

# 12. Quick revision sheet

| Version | Year | Transport | Connection model | Key innovation | Weakness |
| --- | --- | --- | --- | --- | --- |
| HTTP/0.9 | 1991 | TCP | One request, close | Simplicity | No headers, no status codes |
| HTTP/1.0 | 1996 | TCP | One request per connection | Headers, status codes, content types | New TCP handshake per request |
| HTTP/1.1 | 1997 | TCP | Persistent (Keep-Alive) | Connection reuse, chunked encoding, caching | HOL blocking (app layer) |
| HTTP/2 | 2015 | TCP + TLS | Multiplexed streams | Binary framing, HPACK, server push | HOL blocking (TCP layer) |
| HTTP/3 | 2022 | QUIC (UDP) | Independent streams | 0-RTT, no TCP HOL, connection migration | UDP firewall blocking, newer ecosystem |

**One sentence each:**

- **HTTP/1.0** — one connection, one request, throw it away.
- **HTTP/1.1** — keep the connection alive but still queue responses one at a time.
- **HTTP/2** — multiplex many streams over one TCP connection, but a single lost packet
  stalls them all.
- **HTTP/3** — replace TCP with QUIC so each stream is independent and a lost packet
  only affects its own stream.

---

**Previous:** [OSI Layers 5, 6 & 7 — Session, Presentation & Application](../OSI_LAYERS_5-6-7_SESSION_PRESENTATION_APPLICATION/README.md)

**Next:** [DNS & Load Balancing](../DNS_LOAD_BALANCING/README.md)

# REST, RESTful APIs & Best Practices

> Scope: what REST actually is, how a RESTful API is designed resource by resource, and the
> production practices that separate a toy API from one other teams can depend on: status
> codes, errors, pagination, idempotency, versioning, caching, security, rate limiting and
> failure handling.
>
> Source: extracted and reorganised from `0. md/DOCUMENTATIONS ...md` (and its HTML twin) →
> `SYSTEM_DESIGN vs BACKEND` → `API DESIGN`, `REST vs Restful API diff`, `REST: Simple and Flexible`,
> `Idempotency (HTTP Concept)`, `Handling Failures and Fault Mode`, `Rate Limiting and Throttling`,
> `JWT`, `CORS`, `CSRF token`. Gaps were filled from the HTTP RFCs, IETF drafts and OWASP. All
> diagrams in `images/` were drawn for this document.

---

## 0. What this document covers

| Topic | One-line summary |
| --- | --- |
| REST vs RESTful | REST is the architectural style; a RESTful API is a real API that follows it |
| Constraints | Six rules from Fielding's dissertation that define REST |
| Maturity | Richardson levels 0–3, and why most APIs stop at level 2 |
| Choosing a style | REST by default, GraphQL for flexible fetching, gRPC for internal speed |
| Resource design | Nouns, plural collections, shallow nesting, actions modelled as state |
| Methods & status codes | Which verb, which code, and the common mistakes |
| Errors | One machine-readable error shape: Problem Details (RFC 9457) |
| Pagination | Offset vs cursor, and why cursor wins at scale |
| Idempotency | Safe retries, including the `Idempotency-Key` header for POST |
| Versioning | URI vs header versioning, additive change, Deprecation and Sunset headers |
| Caching | `Cache-Control`, `ETag`, conditional requests, optimistic locking |
| Security | Auth, object-level authorization, CORS, CSRF, OWASP API Top 10 |
| Rate limiting | Algorithms, `429`, `Retry-After`, distributed limits |
| Reliability | Timeouts, retries with backoff and jitter, circuit breakers |
| Worked example | A complete orders API plus an Express implementation |

REST lives at the application layer. For the protocol underneath it, see
[HTTP Evolution](../4.%20HTTP_EVOLUTION_HTTP1.1_HTTP2_HTTP3/README.md) and
[OSI Layers 5, 6 & 7](../3.%20OSI_LAYERS_5-6-7_SESSION_PRESENTATION_APPLICATION/README.md).

---

# 1. What REST is

## 1.1 Definition

**REST (Representational State Transfer)** is an architectural style for designing networked
applications. Resources are identified by URLs and manipulated through a small, uniform set of
operations, which on the web are the standard HTTP methods.

Roy Fielding defined it in his 2000 PhD dissertation, describing the principles that had made the
web itself scale. REST is therefore not a protocol, a library or a specification. It is a set of
constraints.

The name explains the mechanism. A client never touches a resource directly. It receives a
**representation** of the resource's **state**, typically JSON, and **transfers** a new
representation back to change it.

## 1.2 REST vs RESTful API

- **REST** is an architectural style: a set of rules and constraints for designing APIs and web
  services.
- **RESTful API** is an actual API built following REST principles.
- In short: **REST = concept and rules. RESTful API = implementation of those rules in a real
  system.**

| Feature | REST | RESTful |
| --- | --- | --- |
| Type | Concept / architecture | Implementation |
| Nature | Theoretical rules | Real, running API |
| Usage | Design guideline | Working system |
| Example | "Use GET for fetching" | `GET /users` endpoint |

A RESTful API follows the core constraints: stateless communication, proper HTTP methods,
resource-based URLs and a uniform interface.

### Sample RESTful APIs

GitHub API:

```http
GET https://api.github.com/users
GET https://api.github.com/users/octocat
```

E-commerce API:

```http
GET    /products
POST   /products
PUT    /products/10
DELETE /products/10
```

## 1.3 Why REST is the default

- It rides on HTTP, so every language, proxy, CDN, browser and debugging tool already understands it.
- Resources map naturally onto database entities and CRUD operations.
- Statelessness makes horizontal scaling straightforward: any server can answer any request.
- GET responses are cacheable by browsers and CDNs for free.

Its known costs:

- JSON is verbose and slow to serialise compared with binary formats such as Protobuf.
- Fixed endpoints cause **over-fetching** (too much data) and **under-fetching** (several round
  trips to assemble one screen).
- It is not the most performant option for very high-throughput internal traffic.

Most applications are never bottlenecked by JSON serialisation, which is why REST is the right
starting point, especially in system design interviews. Reach for GraphQL, gRPC, SSE or WebSockets
only when there is a specific need REST cannot meet.

---

# 2. The six REST constraints

![The six REST architectural constraints](images/rest-constraints.svg)

| # | Constraint | What it means | What you gain |
| --- | --- | --- | --- |
| 1 | Client–server | UI concerns are separated from data storage | Client and server evolve independently |
| 2 | Stateless | Each request contains everything needed to process it; no session held on the server | Any instance can serve any request; easy horizontal scaling |
| 3 | Cacheable | Responses label themselves as cacheable or not | Fewer requests, lower latency, less server load |
| 4 | Uniform interface | Resources identified by URI, manipulated via representations, self-descriptive messages, hypermedia links | Generic clients, proxies and tools work with every API |
| 5 | Layered system | A client cannot tell whether it talks to the origin or an intermediary | Load balancers, CDNs, gateways slot in transparently |
| 6 | Code on demand (optional) | Server may send executable code to the client | Clients can be extended at runtime |

### Stateless does not mean the application has no state

HTTP is stateless, but applications obviously remember who you are. The state simply lives with the
client or in a shared store rather than in server memory. It is carried by:

- **Tokens** such as a JWT in the `Authorization` header.
- **Cookies**, sent automatically by the browser.
- **Sessions** held in a shared store like Redis, keyed by a session ID the client sends.

The rule is that a request must never depend on which server instance handled the previous one.

---

# 3. Richardson Maturity Model

![Richardson Maturity Model levels 0 to 3](images/richardson-maturity.svg)

Leonard Richardson's model grades how fully an HTTP API uses the web's features.

| Level | Name | Characteristics | Example |
| --- | --- | --- | --- |
| 0 | Swamp of POX | One endpoint, one method, operation named in the body | `POST /api` with `{"action":"getUser"}` |
| 1 | Resources | Separate URIs per resource, but still one method | `POST /users/42` to read a user |
| 2 | HTTP verbs | Correct methods and status codes | `GET /users/42` returns `200` |
| 3 | Hypermedia controls | Responses include links describing the next valid actions | `_links.cancel` on an order |

### HATEOAS

**Hypermedia As The Engine Of Application State** is level 3. The client discovers what it may do
next from links in the response, rather than hard-coding URL patterns.

```json
{
  "id": "ord_7",
  "status": "pending",
  "total": { "amount": 4999, "currency": "USD" },
  "_links": {
    "self":    { "href": "/orders/ord_7" },
    "pay":     { "href": "/orders/ord_7/payment", "method": "POST" },
    "cancel":  { "href": "/orders/ord_7", "method": "PATCH" }
  }
}
```

Once the order ships, the server simply stops including `cancel`. In practice few public APIs go
fully to level 3. Level 2 done well, with good documentation, is the realistic target.

---

# 4. Choosing an API style

![Decision tree: GraphQL, REST or RPC](images/api-style-decision.svg)

The three main paradigms, as captured in the notes:

1. **REST** uses standard HTTP methods on resources identified by URLs. It maps naturally to CRUD
   and database operations, which makes it the go-to protocol for most web and mobile services.
   This should be your default choice.
2. **GraphQL** exposes a single endpoint and a query language, so each client asks for exactly the
   fields it needs. A mobile app needing a user's name and a dashboard needing full analytics can
   share one API without extra endpoints. Signals to consider it: "flexible data fetching",
   "over-fetching", "under-fetching", many different clients.
3. **RPC**, such as gRPC, uses binary serialisation over HTTP/2 and models **actions** rather than
   resources. A call like `checkPermission(userId, resource)` between an auth service and a user
   service is more natural as RPC than as a resource. Signals: microservices, internal APIs,
   performance-critical service-to-service calls.

## 4.1 Comparison

| Feature | REST | GraphQL | gRPC |
| --- | --- | --- | --- |
| Endpoints | Many, one per resource | One, usually `/graphql` | Methods on a service |
| Data shape | Fixed by server | Chosen by client | Fixed by `.proto` contract |
| Format | JSON (text) | JSON (text) | Protobuf (binary) |
| Transport | HTTP/1.1, 2 or 3 | Usually HTTP POST | HTTP/2 |
| HTTP caching | Excellent for GET | Hard, single POST endpoint | None built in |
| Error model | HTTP status codes | `data` plus `errors` array, often with 200 | gRPC status codes |
| Partial success | No | Yes | No |
| Timeouts | Client-side | Per resolver | Deadlines, propagated |
| Streaming | No (use SSE or WebSocket) | Subscriptions | Native bidirectional |
| Browser support | Native | Native | Needs gRPC-Web proxy |
| Best for | Public and CRUD APIs | Many clients with varied needs | Internal, low-latency services |

A common real-world architecture uses all three: REST or GraphQL at the edge for clients, gRPC
between internal services.

---

# 5. Resource and URI design

## 5.1 Think in resources, not operations

The central design task in REST is modelling **resources** and the operations allowed on them.
Resources are usually the core entities of the system, which often map to database tables.

Many engineers instinctively design endpoints like `updateUser` or `startGame`. Those are
operations, not resources, so they are not RESTful. Rewrite them as a method on a resource:

| RPC-style (avoid) | RESTful |
| --- | --- |
| `POST /getUser?id=42` | `GET /users/42` |
| `POST /createUser` | `POST /users` |
| `POST /updateUser` | `PUT /users/42` or `PATCH /users/42` |
| `POST /deleteUser?id=42` | `DELETE /users/42` |
| `POST /startGame` | `PATCH /games/9` with `{"status":"started"}` |
| `GET /getUserPosts?user=42` | `GET /users/42/posts` |

## 5.2 URI rules

- **Use nouns, not verbs.** The HTTP method is the verb.
- **Use plural collection names.** `/users` and `/users/42`, never mixing `/user/42`.
- **Use lowercase kebab-case for multi-word paths.** `/order-items`, not `/orderItems`.
- **Nest only to express ownership, and keep it shallow.** `/users/42/posts` is fine.
  `/users/42/posts/9/comments/3/likes` is not; expose `/comments/3/likes` instead.
- **Keep file extensions out of URIs.** Use `Accept: application/json`, not `/users.json`.
- **Use query parameters for filtering, sorting, searching and pagination**, never for identity.
- **Never put secrets or personal data in URLs.** URLs are logged by proxies, servers and browsers.
- **Avoid trailing slashes**, or redirect them consistently.

```http
GET /users?role=admin&status=active          # filter
GET /users?sort=-created_at,name             # sort: minus = descending
GET /users?q=alice                           # search
GET /users?fields=id,name,email              # sparse fieldset
GET /users?limit=20&cursor=eyJpZCI6NDJ9      # paginate
```

## 5.3 When an action really is an action

Some operations do not map cleanly onto CRUD, for example sending an email or recalculating a
report. Three accepted approaches, in order of preference:

1. **Model the action as a state change.** Cancelling an order becomes
   `PATCH /orders/7` with `{"status":"cancelled"}`.
2. **Model the action as a sub-resource that gets created.**
   `POST /orders/7/refunds` creates a refund resource you can later `GET`.
3. **Use a controller resource as a last resort.** `POST /reports/12/recalculate`. This is common
   in well-known APIs such as Stripe and GitHub, and is acceptable when used sparingly.

---

# 6. HTTP methods

| Method | Purpose | Safe | Idempotent | Request body | Typical success |
| --- | --- | --- | --- | --- | --- |
| GET | Read a resource or collection | Yes | Yes | No | 200 |
| HEAD | Same as GET, headers only | Yes | Yes | No | 200 |
| OPTIONS | Discover allowed methods, CORS preflight | Yes | Yes | No | 204 |
| POST | Create in a collection, or trigger processing | No | **No** | Yes | 201 or 202 |
| PUT | Replace a resource entirely, or create at a known URI | No | Yes | Yes | 200 or 204, 201 if created |
| PATCH | Partially update a resource | No | **Not guaranteed** | Yes | 200 or 204 |
| DELETE | Remove a resource | No | Yes | Rarely | 204 |

**Safe** means the method does not change server state. **Idempotent** means sending the same
request once or many times leaves the server in the same final state.

## 6.1 Idempotency, precisely

From the notes: an operation is idempotent if making the same request multiple times results in the
same **final state** on the server.

- **GET** only retrieves data, so state never changes.
- **PUT** replaces a resource. Sending the same body three times gives the same result.
- **DELETE** removes a resource. Deleting again leaves it still deleted.

Non-idempotent:

- **POST** creates resources or triggers actions such as sending an email or charging a card.
  Repeating it can create duplicate orders or payments.
- **PATCH** depends on current state. A patch meaning "increment counter by 1" changes state every
  time. A patch that sets a field to a fixed value happens to be idempotent, but the method makes no
  promise.
- **CONNECT** opens a tunnel through a proxy and is not idempotent.

**Idempotent does not mean identical responses.** The first `DELETE /users/42` returns `204`; the
second may return `404`. The server state is the same after both, which is what counts.

## 6.2 PUT vs PATCH

`PUT` sends the **complete** representation. Omitted fields are cleared or reset to defaults.

```http
PUT /users/42
Content-Type: application/json

{ "name": "John Doe", "email": "john.doe@example.com", "role": "admin" }
```

`PATCH` sends only the **changes**. Two standard formats exist.

JSON Merge Patch, RFC 7396, is simple and covers most needs. A `null` value deletes the field.

```http
PATCH /users/42
Content-Type: application/merge-patch+json

{ "email": "new@example.com", "nickname": null }
```

JSON Patch, RFC 6902, is a list of operations. It can express array edits and conditional `test`
operations that merge patch cannot.

```http
PATCH /users/42
Content-Type: application/json-patch+json

[
  { "op": "test",    "path": "/version", "value": 3 },
  { "op": "replace", "path": "/email",   "value": "new@example.com" },
  { "op": "add",     "path": "/tags/-",  "value": "vip" }
]
```

In practice most APIs accept a plain JSON object on `PATCH` with merge-patch semantics.

---

# 7. Status codes

Status codes are the API's first and cheapest error channel. Clients, retries, monitoring and
caches all key off them, so pick precisely.

## 7.1 The codes worth knowing

| Code | Name | Use it when |
| --- | --- | --- |
| 200 | OK | Successful GET, PUT or PATCH that returns a body |
| 201 | Created | POST created a resource. Include a `Location` header with its URL |
| 202 | Accepted | Request queued for asynchronous processing |
| 204 | No Content | Success with nothing to return, typically DELETE |
| 301 | Moved Permanently | Resource moved for good; clients should update links |
| 302 | Found | Temporary redirect |
| 304 | Not Modified | Conditional GET matched; client's cached copy is still valid |
| 400 | Bad Request | Malformed syntax: invalid JSON, wrong type, missing required parameter |
| 401 | Unauthorized | Not authenticated: no credentials, or invalid or expired token |
| 403 | Forbidden | Authenticated, but not allowed to do this |
| 404 | Not Found | Resource does not exist, or you choose not to reveal that it does |
| 405 | Method Not Allowed | Method not supported on this resource. Send an `Allow` header |
| 409 | Conflict | State conflict: duplicate unique field, or an invalid state transition |
| 412 | Precondition Failed | `If-Match` ETag did not match, so the resource changed meanwhile |
| 415 | Unsupported Media Type | Request `Content-Type` not accepted |
| 422 | Unprocessable Content | Well-formed JSON that fails business validation |
| 429 | Too Many Requests | Rate limit exceeded. Send `Retry-After` |
| 500 | Internal Server Error | Unexpected bug on the server |
| 502 | Bad Gateway | A proxy or gateway got an invalid response from upstream |
| 503 | Service Unavailable | Overloaded or in maintenance. Send `Retry-After` |
| 504 | Gateway Timeout | Upstream did not respond in time |

## 7.2 Distinctions that come up constantly

- **401 vs 403.** 401 means "I don't know who you are". 403 means "I know who you are, and the
  answer is no". Despite its name, 401 is about authentication.
- **400 vs 422.** 400 for a request the server cannot parse. 422 for a request it parsed but whose
  content is invalid, such as an end date before a start date. Using 400 for both is acceptable if
  applied consistently.
- **403 vs 404.** Returning 404 for a resource that exists but belongs to someone else avoids
  leaking its existence. GitHub does this for private repositories.
- **409 vs 412.** 409 is a general state conflict. 412 is specifically a failed precondition header.
- **4xx vs 5xx decides retries.** 4xx means the client must change something, so retrying the same
  request is pointless, with 408 and 429 as the exceptions. 5xx means the server failed and a retry
  may succeed.

## 7.3 Anti-patterns

- **200 with an error body**, such as `200 {"success": false}`. Monitoring counts it as success,
  caches may store it and client libraries will not raise.
- **500 for bad input.** It pages the on-call engineer for a client mistake and hides real bugs.
- **Always 400.** Clients cannot distinguish "fix your JSON" from "you're not allowed".
- **201 without `Location`.** The client then has to guess the new resource's URL.

---

# 8. Request and response design

## 8.1 Conventions that save arguments later

| Concern | Recommendation | Why |
| --- | --- | --- |
| Format | JSON, `Content-Type: application/json` | Universal tooling |
| Field naming | Pick `camelCase` or `snake_case` and never mix | Consistency beats either choice |
| Dates and times | ISO 8601 in UTC: `2026-09-13T14:05:00Z` | Unambiguous, sortable, time-zone safe |
| IDs | Strings, even if numeric internally | Lets you move to UUIDs or prefixed IDs without breaking clients |
| Money | Integer minor units plus currency: `{"amount":4999,"currency":"USD"}` | Floating point cannot represent cents exactly |
| Enums | Lowercase strings: `"pending"`, not `2` | Self-documenting, safe to extend |
| Booleans | `true` or `false`, named positively: `isActive` | Avoids double negatives |
| Empty collections | `[]`, never `null` | Clients can iterate without a null check |
| Absent vs null | Document the difference and keep it consistent | Matters for PATCH semantics |

## 8.2 Envelope or no envelope

A bare resource is simplest for single items:

```json
{ "id": "usr_42", "name": "Alice", "email": "alice@example.com" }
```

Collections benefit from a wrapper, because pagination metadata needs somewhere to live:

```json
{
  "data": [ { "id": "usr_42", "name": "Alice" } ],
  "pagination": { "nextCursor": "eyJpZCI6NDJ9", "hasMore": true }
}
```

Do **not** duplicate HTTP in the body with fields like `"status": 200` or `"success": true`. The
status line already says that.

## 8.3 Never trust the request body

HTTPS encrypts traffic in transit, but it does not prove the request was produced by your own
client. Anyone can craft a request with `curl`.

A classic mistake is reading the user's ID from the request body and using it in a database query.
An attacker simply changes the ID and reads another user's data. Derive identity from the verified
token on the server, and validate every ID the client sends against what that identity is allowed
to access.

```js
// ❌ trusts the client
app.get("/orders", (req, res) => db.orders.find({ userId: req.body.userId }));

// ✅ identity comes from the verified token
app.get("/orders", auth, (req, res) => db.orders.find({ userId: req.user.id }));
```

## 8.4 Content negotiation

HTTP headers are a good model of extensible interface design. The client states what it can handle
and the server picks the best match, which gives backward compatibility and graceful degradation.

```http
GET /reports/9
Accept: application/json
Accept-Encoding: gzip, br
Accept-Language: en-GB

HTTP/1.1 200 OK
Content-Type: application/json
Content-Encoding: br
Vary: Accept-Encoding
```

---

# 9. Error handling

## 9.1 Use one error format: Problem Details, RFC 9457

RFC 9457 (July 2023, replacing RFC 7807) standardises a JSON error body with media type
`application/problem+json`. Using it means clients write one error parser for your whole API.

```http
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/validation-error",
  "title": "Your request parameters didn't validate.",
  "status": 422,
  "detail": "2 fields failed validation.",
  "instance": "/orders",
  "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
  "errors": [
    { "pointer": "/items/0/quantity", "detail": "must be at least 1" },
    { "pointer": "/shippingAddress/postcode", "detail": "is required" }
  ]
}
```

| Member | Meaning |
| --- | --- |
| `type` | URI identifying the problem type; ideally a page documenting it |
| `title` | Short, human-readable summary that does not change between occurrences |
| `status` | The HTTP status code, repeated for convenience |
| `detail` | Explanation specific to this occurrence |
| `instance` | URI identifying this specific occurrence |
| extensions | Any extra members, such as `errors` or `traceId` |

## 9.2 Error handling rules

- **Return every validation error at once**, not one per round trip.
- **Give each error a stable machine-readable code or `type`.** Clients branch on it; the human
  message can then change freely.
- **Never leak internals.** No stack traces, SQL, file paths or library versions in production.
- **Include a correlation or trace ID** so a support ticket can be matched to server logs.
- **Log the full detail server-side** and return only what the client needs.
- **Treat unexpected errors as 500 with a generic body**, and alert on them.

---

# 10. Pagination, filtering and sorting

Any collection that can grow must be paginated from day one. Adding pagination later is a breaking
change, because clients that expected every item will silently receive only the first page.

![Offset vs cursor pagination](images/pagination-offset-vs-cursor.svg)

## 10.1 Offset pagination

```http
GET /posts?limit=20&offset=40
```

```sql
SELECT * FROM posts ORDER BY created_at DESC LIMIT 20 OFFSET 40;
```

- ✅ Simple, and supports jumping to an arbitrary page number.
- ❌ **Gets slower on deep pages.** The database still reads and discards every skipped row.
- ❌ **Unstable under writes.** An insert or delete between requests shifts rows, so items are
  duplicated or skipped.

## 10.2 Cursor (keyset) pagination

```http
GET /posts?limit=20&cursor=eyJjcmVhdGVkX2F0IjoiMjAyNi0wOS0xM1QxMDowMDowMFoiLCJpZCI6OTg3fQ
```

The cursor is an opaque, usually base64-encoded, pointer to the last item seen. The server decodes
it into a `WHERE` clause that uses an index:

```sql
SELECT * FROM posts
WHERE (created_at, id) < ('2026-09-13T10:00:00Z', 987)
ORDER BY created_at DESC, id DESC
LIMIT 21;              -- fetch one extra row to compute hasMore
```

- ✅ **Constant speed** at any depth, because it is an index seek.
- ✅ **Stable under concurrent inserts and deletes.**
- ❌ No "jump to page 50". Only next, and optionally previous.
- ⚠️ The sort key must be unique. Add `id` as a tie-breaker, as above.
- ⚠️ Keep the cursor opaque so you can change its internals later.

## 10.3 Which to use

| Situation | Choice |
| --- | --- |
| Infinite scroll, feeds, activity logs | Cursor |
| Large or fast-changing tables | Cursor |
| Public APIs meant to scale | Cursor |
| Small admin tables that need numbered pages | Offset is fine |

The notes' short answer is right: offset-based and cursor-based both exist, and cursor-based is
better for most systems.

## 10.4 Response shape and Link header

```http
HTTP/1.1 200 OK
Link: <https://api.example.com/posts?limit=20&cursor=abc>; rel="next"

{
  "data": [ ... ],
  "pagination": { "nextCursor": "abc", "hasMore": true, "limit": 20 }
}
```

Rules:

- **Enforce a maximum `limit`**, such as 100, and apply a sensible default when it is omitted.
- **Avoid returning a total count by default.** `COUNT(*)` on a large table is expensive; offer it
  as an opt-in when truly needed.
- **Whitelist sortable and filterable fields.** Arbitrary sort fields invite unindexed scans and
  injection bugs.

---

# 11. Idempotency and safe retries

Networks fail in the worst possible place: after the server did the work, but before the client got
the response. The client cannot tell a failed request from a lost response, so it retries. For GET,
PUT and DELETE that is harmless. For POST it means a second order or a second charge.

## 11.1 The Idempotency-Key header

![Idempotency-Key retry flow](images/idempotency-key-flow.svg)

The client generates a unique key, typically a UUID, per logical operation and sends it on the
request. On a retry it sends the **same** key. Stripe popularised the pattern, and the IETF HTTPAPI
working group is standardising it as the `Idempotency-Key` header, currently an Internet-Draft.

```http
POST /payments
Idempotency-Key: 8e03978e-40d5-43e8-bc93-6894a57f9324
Content-Type: application/json

{ "amount": 4999, "currency": "USD", "source": "card_123" }
```

## 11.2 Server-side algorithm

1. **Look up the key**, scoped to the authenticated client.
2. **Not found:** atomically insert it as `in_progress`, for example with a unique constraint or
   Redis `SET key value NX`, then process the request.
3. **After processing:** store the status code and response body against the key, and give it a
   retention period such as 24 hours.
4. **Found and completed:** replay the stored response without re-executing the operation.
5. **Found but still in progress:** return `409 Conflict`, so two concurrent retries cannot both run.
6. **Found with a different request body:** return `422`, because the key is being reused for a
   different operation.

Doing the business write and recording the key in the **same database transaction** removes the
window where one succeeds and the other does not.

## 11.3 Retry policy

| Response | Retry? |
| --- | --- |
| Network error or timeout | Yes, if the operation is idempotent or has an idempotency key |
| 408, 429 | Yes, after `Retry-After` if present |
| 500, 502, 503, 504 | Yes, with backoff |
| Other 4xx | No. The request itself is wrong |

Use **exponential backoff with jitter** and a cap on attempts. Without jitter, thousands of clients
that failed together retry together, which causes the **retry storm** the notes list as a REST
failure mode.

```js
async function withRetry(fn, { attempts = 5, baseMs = 200, maxMs = 10_000 } = {}) {
  for (let i = 0; ; i++) {
    try {
      return await fn();
    } catch (err) {
      if (i === attempts - 1 || !err.retryable) throw err;
      const ceiling = Math.min(maxMs, baseMs * 2 ** i);
      const delay = Math.random() * ceiling;          // "full jitter"
      await new Promise((r) => setTimeout(r, delay));
    }
  }
}
```

---

# 12. Versioning and API evolution

## 12.1 The best version is the one you never ship

Most change can be made **backward compatible**, so no new version is required.

| Non-breaking (safe) | Breaking (needs a new version) |
| --- | --- |
| Adding a new endpoint | Removing or renaming an endpoint or field |
| Adding an optional request field | Making an optional field required |
| Adding a response field | Changing a field's type or format |
| Adding a new enum value (if clients were told to expect unknown values) | Changing the meaning of an existing value |
| Relaxing validation | Tightening validation |
| Adding an optional query parameter | Changing default sort, page size or behaviour |

Clients should follow the **tolerant reader** principle: ignore unknown fields rather than failing
on them. Document that expectation explicitly.

## 12.2 Versioning strategies

| Strategy | Example | Pros | Cons |
| --- | --- | --- | --- |
| URI path | `/v1/users` | Obvious, easy to route, cache and test in a browser | Version is not really part of the resource's identity |
| Custom header | `Api-Version: 2026-09-01` | Clean URLs; allows date-based versions | Invisible in links; easy to forget |
| Media type | `Accept: application/vnd.example.v2+json` | Most "pure" REST | Awkward tooling and testing |
| Query parameter | `/users?version=2` | Easy to add | Messes with caching; easy to omit |

**URI path versioning is the pragmatic default** and is what most public APIs use. Stripe's
date-based header versioning, pinned per account, is the best-known alternative and suits APIs
that change often.

Only major, breaking versions belong in the URL: `v1`, `v2`. Never `v1.2.3`.

## 12.3 Deprecating responsibly

Announce removal in the protocol, not only in a blog post:

```http
HTTP/1.1 200 OK
Deprecation: @1788220800
Sunset: Wed, 30 Jun 2027 23:59:59 GMT
Link: <https://api.example.com/docs/migrate-v2>; rel="deprecation"
```

- **`Deprecation`**, RFC 9745 (March 2025), says the resource is or will be deprecated. Its value
  is a Unix timestamp prefixed with `@`.
- **`Sunset`**, RFC 8594, gives the date after which the resource may stop responding.
- Track who still calls deprecated endpoints, and contact them before the sunset date.

---

# 13. Caching and conditional requests

## 13.1 Cache-Control

```http
Cache-Control: public, max-age=300          # shared caches such as CDNs may store for 5 minutes
Cache-Control: private, max-age=60          # only the user's browser may store it
Cache-Control: no-cache                     # store, but revalidate before every use
Cache-Control: no-store                     # never store: tokens, personal data, payment details
```

Any response that varies by header must say so, or a CDN may serve one user's response to another:

```http
Vary: Authorization, Accept-Encoding
```

## 13.2 ETags and conditional GET

An `ETag` is a fingerprint of a representation's content. The client sends it back and the server
answers `304` with an empty body if nothing changed, saving bandwidth.

```http
GET /products/10
→ 200 OK
  ETag: "v7-a1b2c3"

GET /products/10
If-None-Match: "v7-a1b2c3"
→ 304 Not Modified          (no body)
```

The notes explain why ETags beat `Last-Modified`. They detect changes within the same second, they
ignore "touched but unchanged" files, and they do not depend on synchronised clocks across a
server cluster.

## 13.3 Optimistic concurrency: preventing lost updates

Two users load product 10. Both edit it. The second save silently overwrites the first. The fix is
a **conditional write** using `If-Match`.

```http
PUT /products/10
If-Match: "v7-a1b2c3"
Content-Type: application/json

{ "name": "Desk lamp", "price": { "amount": 2999, "currency": "USD" } }
```

- ETag still matches → the update is applied, `200` with the new ETag.
- ETag changed because someone else saved first → `412 Precondition Failed`. The client refetches,
  merges and retries.
- Header missing, when the API requires it → `428 Precondition Required`.

---

# 14. Security

## 14.1 Baseline

- **HTTPS everywhere, no exceptions.** Redirecting HTTP to HTTPS is not enough for API clients;
  reject plain HTTP and send `Strict-Transport-Security` for browsers.
- **Authenticate every non-public endpoint**, and deny by default.
- **Authorize every object, not just every endpoint.**
- **Validate all input** against a schema: types, lengths, ranges, formats, allowed values.
- **Encode output** and set `Content-Type` correctly, so JSON is never rendered as HTML.
- **Keep secrets out of URLs and logs.** Tokens belong in headers.
- **Limit payload sizes** for request bodies and uploads.

## 14.2 Authentication options

| Mechanism | Best for | Notes |
| --- | --- | --- |
| API keys | Server-to-server, identifying a calling application | Identifies an app, not a user. Send in a header, rotate, scope |
| OAuth 2.0 | Delegated access: letting an app act on a user's behalf | Use Authorization Code with PKCE for browser and mobile clients |
| OpenID Connect | Login and user identity | Identity layer on top of OAuth 2.0; issues an ID token |
| JWT bearer tokens | Stateless auth between services | Short expiry; verify signature, `exp`, `iss`, `aud` |
| Session cookies | First-party browser apps | Mark `HttpOnly`, `Secure`, `SameSite`; needs CSRF protection |
| mTLS | High-trust service-to-service | Both sides present certificates |

From the notes on JWT:

- A JWT has three base64url-encoded parts: header, payload and signature.
- The payload holds claims such as `sub`, `exp`, `iat` and a role.
- **It is encoded, not encrypted.** Anyone can read it, so never put secrets or sensitive personal
  data in it.
- The signature guarantees integrity, not confidentiality.
- Because it is stateless, a JWT cannot easily be revoked before expiry. Keep access tokens short
  lived, such as 5 to 15 minutes, and use refresh tokens.

## 14.3 CORS and CSRF

**CORS** is a browser mechanism, not a server security control. It decides whether JavaScript from
one origin (protocol + domain + port) may read a response from another origin. `curl` and servers
ignore it entirely.

```http
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Methods: GET, POST, PATCH, DELETE
Access-Control-Allow-Headers: Authorization, Content-Type, Idempotency-Key
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 600
```

Never combine `Access-Control-Allow-Origin: *` with credentials, and never reflect the request's
`Origin` header back without checking it against an allowlist.

**CSRF** is an attack in which another website makes the victim's browser send an authenticated
request, because browsers attach cookies automatically.

- An API authenticated only with `Authorization: Bearer` headers is **not** vulnerable to CSRF,
  because browsers never attach that header automatically.
- An API authenticated with **cookies** must defend itself: `SameSite=Lax` or `Strict` cookies, CSRF
  tokens, and checking the `Origin` header on state-changing requests.

## 14.4 OWASP API Security Top 10 (2023)

| # | Risk | In one line |
| --- | --- | --- |
| API1 | Broken Object Level Authorization (BOLA) | `GET /orders/124` returns someone else's order |
| API2 | Broken Authentication | Weak tokens, no expiry, credential stuffing allowed |
| API3 | Broken Object Property Level Authorization | Exposing or letting clients set fields they shouldn't, such as `isAdmin` |
| API4 | Unrestricted Resource Consumption | No rate limits, unbounded page sizes or uploads |
| API5 | Broken Function Level Authorization | A normal user can call admin endpoints |
| API6 | Unrestricted Access to Sensitive Business Flows | Bots mass-buying stock or abusing sign-ups |
| API7 | Server-Side Request Forgery (SSRF) | API fetches an attacker-supplied URL on an internal network |
| API8 | Security Misconfiguration | Verbose errors, permissive CORS, default credentials |
| API9 | Improper Inventory Management | Forgotten old versions and debug endpoints still live |
| API10 | Unsafe Consumption of APIs | Blindly trusting data returned by third-party APIs |

**BOLA is number one** and is exactly the "user ID in the request body" mistake from section 8.3.
Every handler that loads an object by ID must check that the caller may access that specific object.

**Mass assignment**, part of API3, is its sibling. Never pass the request body straight into an ORM
update; copy only an explicit allowlist of fields.

```js
// ❌ client can send {"role":"admin"}
await db.users.update(req.params.id, req.body);

// ✅ allowlist
const { name, email } = req.body;
await db.users.update(req.params.id, { name, email });
```

---

# 15. Rate limiting and throttling

## 15.1 What and why

**Rate limiting** controls how many requests a client may make in a time window, for example 100
requests per minute. Its goals are to prevent abuse, protect capacity and ensure fair usage.

Without it:

- A DDoS or misbehaving script can take the system down.
- One user can consume all shared resources.
- The API becomes unstable for everyone.
- Infrastructure and third-party costs grow without bound.

It is used by essentially every public API, including Google Cloud, Stripe, GitHub and the major
LLM APIs.

**Throttling** is the softer sibling. Instead of rejecting outright, it delays or degrades requests
when traffic is high.

## 15.2 Where it happens

1. **Client** throttling, such as debouncing a search box. A courtesy only, since it can be bypassed.
2. **API gateway**, the main line of defence.
3. **Backend middleware**, for per-endpoint or business-specific limits.
4. **A shared store such as Redis**, which tracks counters across all instances.

```text
Client → API Gateway → Rate Limiter → Service → DB
```

Limits can be keyed by IP address, user ID, API key, device, or a combination. IP-only limits
punish users behind shared NAT and are easy to evade with many IPs, so prefer authenticated
identity where possible.

## 15.3 Algorithms

![Token bucket rate limiter](images/token-bucket.svg)

| Algorithm | How it works | Burst handling | Memory | Typical use |
| --- | --- | --- | --- | --- |
| Fixed window counter | Count requests per clock window, reset at the boundary | ❌ Up to 2× limit across a boundary | Very low | Basic APIs |
| Sliding window log | Store a timestamp per request; count those inside the window | ✅ Exact | High | Low-volume, strict limits |
| Sliding window counter | Weighted blend of current and previous window counts | ⚠️ Close approximation | Low | Large-scale APIs |
| Token bucket | Tokens refill at a steady rate; each request spends one | ✅ Allows bursts up to capacity | Low | Most real systems |
| Leaky bucket | Requests queue and drain at a constant rate | ⚠️ Smooths bursts into a steady flow | Queue size | Protecting fragile downstreams |

**Fixed window boundary problem:** with a limit of 100 per minute, a client can send 100 requests at
0:59 and another 100 at 1:00, which is 200 requests in two seconds.

## 15.4 Communicating limits to clients

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 30
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/rate-limited",
  "title": "Too many requests",
  "status": 429,
  "detail": "Limit of 100 requests per minute exceeded. Retry in 30 seconds."
}
```

- **`429` + `Retry-After`** are standard and should always be sent.
- Many APIs also send `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset`. These
  are a convention, not a standard.
- The IETF is standardising `RateLimit` and `RateLimit-Policy` headers. As of the May 2026 draft
  this is still an Internet-Draft, so the syntax may change before it becomes an RFC.

## 15.5 Implementation

The notes' Express example keeps an array of timestamps per IP and drops those older than the
window. That is a **sliding window log**, not a token bucket as the notes labelled it. It is
correct, but in-memory state only works on a single server.

```js
const express = require("express");
const app = express();

const hits = new Map();          // ip -> array of timestamps
const LIMIT = 5;                 // max requests
const WINDOW_MS = 60 * 1000;     // per minute

app.use((req, res, next) => {
  const now = Date.now();
  const recent = (hits.get(req.ip) ?? []).filter((t) => now - t < WINDOW_MS);

  if (recent.length >= LIMIT) {
    const retryAfter = Math.ceil((recent[0] + WINDOW_MS - now) / 1000);
    res.set("Retry-After", String(retryAfter));
    return res.status(429).json({ title: "Too many requests", status: 429 });
  }

  recent.push(now);
  hits.set(req.ip, recent);
  next();
});
```

Production systems keep the state in **Redis** so every instance shares one counter. A simple fixed
window uses an atomic increment with expiry:

```text
key    = ratelimit:{userId}:{currentMinute}
INCR key            -> returns the new count
EXPIRE key 60       -> only when the count is 1
count > limit       -> reject with 429
```

A token bucket or sliding window should run as a **Lua script** in Redis so the read, compute and
write happen atomically; otherwise concurrent requests race past the limit.

## 15.6 Common problems and best practices

Problems listed in the notes:

- Shared state across distributed instances.
- Clock synchronisation between servers.
- IP spoofing and rotating IPs.
- Burst traffic at window boundaries.
- Race conditions on counters.

Best practices:

- Use Redis, or the gateway's built-in limiter, for distributed limits.
- Prefer the token bucket algorithm for user-facing APIs.
- Apply limits per user, per IP and per API key, often in layers.
- Set stricter limits on expensive or sensitive endpoints, such as login, password reset and search.
- Always return `429` with `Retry-After`.
- Decide in advance whether to **fail open** (allow traffic) or **fail closed** (reject) if the
  limiter's store is down.

---

# 16. Reliability and failure handling

## 16.1 REST failure modes

From the notes, REST is stateless, HTTP-based and has a simple error model. Its common failure
modes are:

1. Timeouts from slow APIs.
2. 5xx errors from server failures.
3. 4xx errors from client mistakes.
4. Partial failure across microservices.
5. Retry storms.

| Failure type | Description |
| --- | --- |
| Timeout | Request takes too long |
| Network failure | Packet loss or disconnect |
| Server crash | Service goes down |
| Partial failure | Some services fail while others work |
| Data inconsistency | Replicas disagree |
| Overload | Too many requests |

## 16.2 Defences

### 1. Accurate status codes
So clients and infrastructure can tell a retryable failure from a permanent one (section 7).

### 2. Timeouts on every outbound call
A call without a timeout can hang a thread or connection forever and cascade into an outage.

The notes show `fetch(url, { timeout: 3000 })`. **`fetch` has no `timeout` option**, so that line
silently does nothing. Use an abort signal instead:

```js
const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
```

Set a total deadline for the whole request, and give each downstream call a share of it.

### 3. Retries with exponential backoff and jitter
Retry only idempotent operations or those with an idempotency key, and only on retryable responses
(section 11.3).

### 4. Circuit breaker
After repeated failures, stop calling the failing dependency for a cooling-off period and fail fast
instead. After the timeout, let a trial request through to test recovery.

```text
CLOSED ──(failure threshold reached)──▶ OPEN ──(cool-off expires)──▶ HALF-OPEN
   ▲                                                                   │
   └──────────────(trial request succeeds)─────────────────────────────┘
                   (trial request fails → back to OPEN)
```

Netflix's **Hystrix**, cited in the notes, has been in maintenance mode since 2018. Current choices
are **Resilience4j** for Java, **Polly** for .NET, **opossum** for Node.js, or a service mesh such
as Istio or Envoy.

### 5. Load balancing and health checks
Route away from unhealthy or overloaded instances.

### 6. Graceful degradation
Serve cached or partial data, or hide a non-critical feature, rather than failing the whole request.

### 7. Load shedding
Return `503` with `Retry-After` early when overloaded, instead of accepting work you cannot finish.

## 16.3 Long-running operations

Never hold an HTTP connection open for a job that takes minutes. Accept it, return immediately and
let the client poll a status resource.

```http
POST /reports
→ 202 Accepted
  Location: /reports/jobs/job_91

GET /reports/jobs/job_91
→ 200 OK
  { "id": "job_91", "status": "running", "progress": 0.4 }

GET /reports/jobs/job_91
→ 303 See Other
  Location: /reports/rpt_55
```

For push instead of polling, offer a **webhook** callback, or stream progress over **SSE**.

---

# 17. Documentation, tooling and observability

## 17.1 Documentation

- **Describe the API with OpenAPI 3.1.** One spec generates interactive docs (Swagger UI, Redoc),
  client SDKs, mock servers and contract tests.
- **Prefer contract-first design.** Write and review the spec before the code, so consumers can
  give feedback while change is still cheap.
- **Document every endpoint** with its purpose, auth requirements, parameters, request and response
  examples, every possible error, and its rate limit.
- **Publish a changelog** and a deprecation policy.

## 17.2 Observability

- **Propagate a trace ID** on every request using the W3C `traceparent` header, and return it in
  error responses.
- **Emit structured JSON logs** containing method, route template, status, duration, client ID and
  trace ID, and never the token or the request body's secrets.
- **Track the RED metrics per endpoint:** Rate, Errors and Duration, using p50, p95 and p99 latency
  rather than averages.
- **Alert on symptoms users feel**, such as error rate and latency, rather than on CPU alone.

---

# 18. Worked example: an orders API

## 18.1 Endpoints

| Method | Path | Purpose | Success | Notable errors |
| --- | --- | --- | --- | --- |
| GET | `/v1/orders` | List the caller's orders, cursor-paginated | 200 | 400 bad cursor |
| POST | `/v1/orders` | Create an order; requires `Idempotency-Key` | 201 + `Location` | 409, 422 |
| GET | `/v1/orders/{id}` | Fetch one order, with `ETag` | 200, 304 | 404 |
| PATCH | `/v1/orders/{id}` | Update notes or cancel; requires `If-Match` | 200 | 404, 409, 412, 422, 428 |
| DELETE | `/v1/orders/{id}` | Delete a draft order | 204 | 404, 409 |
| GET | `/v1/orders/{id}/items` | List line items | 200 | 404 |
| POST | `/v1/orders/{id}/refunds` | Create a refund; requires `Idempotency-Key` | 201 or 202 | 404, 409, 422 |

## 18.2 A full exchange

```http
POST /v1/orders HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json
Idempotency-Key: 5b1f0c1e-9a4d-4f7a-8f0e-2c7d6f1a9b33

{
  "items": [ { "productId": "prd_10", "quantity": 2 } ],
  "shippingAddress": { "line1": "1 Main St", "city": "Austin", "postcode": "78701", "country": "US" }
}
```

```http
HTTP/1.1 201 Created
Location: /v1/orders/ord_7
ETag: "1"
Content-Type: application/json

{
  "id": "ord_7",
  "status": "pending",
  "items": [ { "productId": "prd_10", "quantity": 2, "unitPrice": { "amount": 2499, "currency": "USD" } } ],
  "total": { "amount": 4998, "currency": "USD" },
  "createdAt": "2026-09-13T14:05:00Z",
  "updatedAt": "2026-09-13T14:05:00Z"
}
```

Cancelling it, with optimistic locking:

```http
PATCH /v1/orders/ord_7 HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
If-Match: "1"
Content-Type: application/merge-patch+json

{ "status": "cancelled" }
```

```http
HTTP/1.1 200 OK
ETag: "2"

{ "id": "ord_7", "status": "cancelled", "updatedAt": "2026-09-13T14:09:12Z", ... }
```

## 18.3 Express implementation

A compact, runnable illustration of the practices above. Storage is in memory to keep the focus on
HTTP behaviour; a real service would use a database and Redis.

```js
const express = require("express");
const crypto = require("node:crypto");

const app = express();
app.use(express.json({ limit: "100kb" }));

// ---- in-memory stores -------------------------------------------------
const orders = new Map();              // id -> order
const idempotency = new Map();         // `${userId}:${key}` -> { hash, status, body }
let seq = 0;

// ---- helpers ------------------------------------------------------------
const problem = (res, status, title, extra = {}) =>
  res.status(status).type("application/problem+json").json({
    type: `https://api.example.com/problems/${title.toLowerCase().replace(/\s+/g, "-")}`,
    title, status, ...extra,
  });

const etagOf = (order) => `"${order.version}"`;

// Opaque cursor wrapping the sort key of the last item seen (keyset pagination).
const encodeCursor = (order) => Buffer.from(JSON.stringify({ seq: order.seq })).toString("base64url");
const decodeCursor = (c) => {
  const { seq } = JSON.parse(Buffer.from(c, "base64url").toString("utf8"));
  if (!Number.isInteger(seq)) throw new Error("bad cursor");
  return seq;
};

// Stand-in for real token verification: identity comes from the token, never the body.
function auth(req, res, next) {
  const token = req.get("Authorization")?.replace(/^Bearer /, "");
  if (!token) return problem(res, 401, "Unauthorized");
  req.user = { id: token };            // pretend the token is the verified user id
  next();
}

// Loads the order AND checks it belongs to the caller (prevents BOLA).
function loadOwnOrder(req, res, next) {
  const order = orders.get(req.params.id);
  if (!order || order.userId !== req.user.id) return problem(res, 404, "Not Found");
  req.order = order;
  next();
}

// ---- routes -------------------------------------------------------------
app.get("/v1/orders", auth, (req, res) => {
  const limit = Math.min(Number(req.query.limit) || 20, 100);
  let beforeSeq = Infinity;
  if (req.query.cursor) {
    try { beforeSeq = decodeCursor(req.query.cursor); }
    catch { return problem(res, 400, "Bad Request", { detail: "Invalid cursor." }); }
  }

  // Equivalent of: WHERE user_id = ? AND seq < ? ORDER BY seq DESC LIMIT limit + 1
  const page = [...orders.values()]
    .filter((o) => o.userId === req.user.id && o.seq < beforeSeq)
    .sort((a, b) => b.seq - a.seq)                           // newest first
    .slice(0, limit + 1);                                    // one extra => hasMore
  const hasMore = page.length > limit;
  const rows = page.slice(0, limit);

  res.json({
    data: rows.map(({ userId, seq, version, ...o }) => o),
    pagination: { hasMore, nextCursor: hasMore ? encodeCursor(rows.at(-1)) : null, limit },
  });
});

app.post("/v1/orders", auth, (req, res) => {
  const key = req.get("Idempotency-Key");
  if (!key) return problem(res, 400, "Bad Request", { detail: "Idempotency-Key header is required." });

  const storeKey = `${req.user.id}:${key}`;
  const hash = crypto.createHash("sha256").update(JSON.stringify(req.body)).digest("hex");
  const seen = idempotency.get(storeKey);
  if (seen) {
    if (seen.hash !== hash)
      return problem(res, 422, "Unprocessable Content", { detail: "Idempotency-Key reused with a different body." });
    if (seen.status === "in_progress") return problem(res, 409, "Conflict", { detail: "Request still in progress." });
    return res.status(seen.statusCode).set(seen.headers).json(seen.body);  // replay
  }
  idempotency.set(storeKey, { hash, status: "in_progress" });

  const items = Array.isArray(req.body.items) ? req.body.items : [];
  const errors = [];
  if (items.length === 0) errors.push({ pointer: "/items", detail: "must contain at least one item" });
  items.forEach((it, i) => {
    if (!Number.isInteger(it.quantity) || it.quantity < 1)
      errors.push({ pointer: `/items/${i}/quantity`, detail: "must be an integer of at least 1" });
  });
  if (errors.length) {
    idempotency.delete(storeKey);                            // let the client fix and retry
    return problem(res, 422, "Unprocessable Content", { errors });
  }

  const now = new Date().toISOString();
  const order = {
    id: `ord_${++seq}`, seq, version: 1, userId: req.user.id,   // userId from token, not body
    status: "pending",
    items: items.map(({ productId, quantity }) => ({ productId, quantity })),  // allowlist
    createdAt: now, updatedAt: now,
  };
  orders.set(order.id, order);

  const { userId, seq: _s, version, ...body } = order;
  const headers = { Location: `/v1/orders/${order.id}`, ETag: etagOf(order) };
  idempotency.set(storeKey, { hash, status: "done", statusCode: 201, headers, body });
  res.status(201).set(headers).json(body);
});

app.get("/v1/orders/:id", auth, loadOwnOrder, (req, res) => {
  const etag = etagOf(req.order);
  if (req.get("If-None-Match") === etag) return res.status(304).end();
  const { userId, seq, version, ...body } = req.order;
  res.set("ETag", etag).json(body);
});

const ALLOWED_TRANSITIONS = { pending: ["cancelled"], cancelled: [] };

app.patch("/v1/orders/:id", auth, loadOwnOrder, (req, res) => {
  const ifMatch = req.get("If-Match");
  if (!ifMatch) return problem(res, 428, "Precondition Required");
  if (ifMatch !== etagOf(req.order)) return problem(res, 412, "Precondition Failed");

  const { status, notes } = req.body;                        // allowlist of patchable fields
  if (status !== undefined) {
    if (!(ALLOWED_TRANSITIONS[req.order.status] ?? []).includes(status))
      return problem(res, 409, "Conflict", { detail: `Cannot move from ${req.order.status} to ${status}.` });
    req.order.status = status;
  }
  if (notes !== undefined) req.order.notes = notes;

  req.order.version += 1;
  req.order.updatedAt = new Date().toISOString();
  const { userId, seq, version, ...body } = req.order;
  res.set("ETag", etagOf(req.order)).json(body);
});

app.delete("/v1/orders/:id", auth, loadOwnOrder, (req, res) => {
  if (req.order.status !== "pending")
    return problem(res, 409, "Conflict", { detail: "Only pending orders can be deleted." });
  orders.delete(req.order.id);
  res.status(204).end();
});

// Unknown routes and unexpected errors still return Problem Details.
app.use((req, res) => problem(res, 404, "Not Found"));
app.use((err, req, res, next) => {
  if (err.type === "entity.parse.failed") return problem(res, 400, "Bad Request", { detail: "Malformed JSON." });
  console.error(err);                                        // full detail stays server-side
  problem(res, 500, "Internal Server Error");
});

if (require.main === module) app.listen(3000, () => console.log("listening on :3000"));
module.exports = app;
```

---

# 19. Best-practices checklist

## Design
- [ ] Resources are plural nouns; the HTTP method is the verb
- [ ] Nesting is at most one or two levels deep
- [ ] Field naming, date format and ID format are consistent across the whole API
- [ ] Every collection is paginated, with a maximum page size
- [ ] Filtering and sorting use whitelisted query parameters

## Semantics
- [ ] GET is safe; PUT and DELETE are idempotent
- [ ] POST endpoints with side effects accept an `Idempotency-Key`
- [ ] Status codes are precise: 201 + `Location`, 204, 401 vs 403, 409, 422, 429
- [ ] All errors use one format, ideally `application/problem+json`
- [ ] Long jobs return 202 with a status resource

## Evolution
- [ ] Only additive changes within a version
- [ ] Major version in the URI path, or a documented header scheme
- [ ] `Deprecation` and `Sunset` headers before anything is removed
- [ ] An OpenAPI spec is the source of truth and is published

## Security
- [ ] HTTPS only
- [ ] Every object access is checked against the caller's identity (BOLA)
- [ ] Request bodies are schema-validated; updates use a field allowlist
- [ ] Tokens are short-lived and never placed in URLs or logs
- [ ] CORS is an explicit allowlist; cookie auth has CSRF protection
- [ ] Errors never expose stack traces or internals

## Operations
- [ ] Rate limits per client, with `429` and `Retry-After`
- [ ] Timeouts on every outbound call
- [ ] Retries use exponential backoff with jitter and a cap
- [ ] Circuit breakers on critical dependencies
- [ ] `Cache-Control` and `ETag` on cacheable GETs; `If-Match` on concurrent writes
- [ ] Trace IDs, structured logs and per-endpoint latency and error metrics

---

# 20. Q&A

### Fundamentals

**What is REST?**
An architectural style, defined by Roy Fielding in 2000, for networked applications in which
resources identified by URLs are manipulated through a uniform interface, usually HTTP methods.

**What is the difference between REST and a RESTful API?**
REST is the set of rules. A RESTful API is a real API that implements those rules.

**Is REST a protocol?**
No. It is an architectural style. HTTP is the protocol it is almost always used with.

**What are the six REST constraints?**
Client–server, stateless, cacheable, uniform interface, layered system, and the optional code on
demand.

**What does stateless mean in REST?**
Each request carries all the information needed to process it. The server keeps no client session
between requests, so any instance can serve any request.

**If HTTP is stateless, how do APIs know who is logged in?**
The client sends state with each request: a token such as a JWT, a cookie, or a session ID that
points to a shared store such as Redis.

**What is HATEOAS?**
Hypermedia As The Engine Of Application State. Responses include links to the actions available
next, so clients discover the API rather than hard-coding URLs.

**What is the Richardson Maturity Model?**
A four-level scale: one endpoint (0), resources (1), HTTP verbs and status codes (2), hypermedia
controls (3).

### Design questions

**Why use nouns instead of verbs in URLs?**
The HTTP method already expresses the action. `GET /users/42` is clearer and more uniform than
`/getUser?id=42`.

**How do you model an action like "cancel order" in REST?**
As a state change, `PATCH /orders/7` with `{"status":"cancelled"}`, or by creating a sub-resource
such as `POST /orders/7/cancellations`.

**PUT vs PATCH?**
PUT replaces the entire resource and is idempotent. PATCH applies a partial change and is not
guaranteed to be idempotent.

**PUT vs POST for creation?**
POST when the server assigns the ID: `POST /users`. PUT when the client knows the URI:
`PUT /users/alice`.

**Which methods are idempotent?**
GET, HEAD, OPTIONS, PUT and DELETE. POST is not; PATCH is not guaranteed.

**Does idempotent mean the response is always the same?**
No. It means the server's final state is the same. A second DELETE may return 404 instead of 204.

**401 vs 403?**
401 means not authenticated. 403 means authenticated but not permitted.

**400 vs 422?**
400 for a malformed request the server cannot parse. 422 for well-formed data that fails
validation.

**Why is returning 200 with an error in the body a bad idea?**
Monitoring, caches, retries and client libraries all treat 200 as success, so the failure becomes
invisible.

**What should a successful POST return?**
201 Created, a `Location` header pointing at the new resource, and usually the resource itself.

### Pagination, caching, versioning

**Offset vs cursor pagination?**
Offset is simple and allows page jumps but slows down on deep pages and duplicates or skips rows
when data changes. Cursor pagination is fast at any depth and stable, but only supports next and
previous.

**Why should cursors be opaque?**
So clients cannot depend on their internals, leaving you free to change the encoding or sort keys.

**What is an ETag used for?**
Conditional GETs that return 304 when unchanged, and conditional writes with `If-Match` that return
412 when someone else changed the resource first.

**How do you prevent lost updates?**
Optimistic concurrency: the client sends `If-Match` with the ETag it read, and the server rejects the
write with 412 if the ETag has changed.

**How do you version a REST API?**
Most commonly with a major version in the path, such as `/v1`. Alternatives are a custom header, a
media type, or a query parameter. Avoid breaking changes within a version.

**What counts as a breaking change?**
Removing or renaming fields or endpoints, changing types, making optional fields required,
tightening validation, or changing default behaviour.

**How do you deprecate an endpoint?**
Announce it, send `Deprecation` and `Sunset` headers with a link to migration docs, monitor remaining
usage, contact those clients, then remove it after the sunset date.

### Reliability and security

**How do you make POST safe to retry?**
The client sends an `Idempotency-Key`. The server stores the key with the result and replays that
result for any retry with the same key.

**Which errors should a client retry?**
Network errors, timeouts, 408, 429 and 5xx, using exponential backoff with jitter. Never other 4xx.

**What is a retry storm?**
Many clients retrying at the same moment, multiplying load on an already failing service. Jitter,
retry caps and circuit breakers prevent it.

**What is a circuit breaker?**
A wrapper that stops calling a failing dependency after a threshold of failures, fails fast for a
cooling period, then lets a trial request through to test recovery.

**Why doesn't `fetch(url, { timeout: 3000 })` work?**
`fetch` has no timeout option, so it is silently ignored. Use `AbortSignal.timeout(3000)` as the
`signal`.

**What is rate limiting, and which algorithm is most used?**
Limiting how many requests a client may make per time window. Token bucket is the most common
because it allows short bursts while enforcing an average rate.

**What is the fixed window boundary problem?**
A client can send a full quota at the end of one window and another at the start of the next,
doubling the effective rate for a moment.

**What should an API return when rate limited?**
429 Too Many Requests with a `Retry-After` header.

**What is BOLA?**
Broken Object Level Authorization, the top OWASP API risk. The API checks that a user is logged in
but not that the specific object requested belongs to them.

**Is a JWT encrypted?**
No. A standard signed JWT is only base64url-encoded. Anyone can read the payload, but nobody can
alter it without invalidating the signature.

**Does a REST API need CSRF protection?**
Only if it authenticates with cookies. Bearer tokens in the `Authorization` header are not sent
automatically by browsers, so they are not exposed to CSRF.

**Is CORS a security feature for the server?**
No. It is enforced only by browsers, to protect users. Non-browser clients ignore it, so the server
still has to authenticate and authorize every request.

**When would you choose GraphQL or gRPC over REST?**
GraphQL when many clients need differently shaped data and over-fetching or under-fetching hurts.
gRPC for internal service-to-service calls where performance, strict contracts or streaming matter.

---

# 21. Quick revision sheet

| Topic | Remember |
| --- | --- |
| REST | Architectural style: resources + uniform interface + stateless |
| RESTful | An API that actually follows those constraints |
| URIs | Plural nouns, shallow nesting, query params for filter, sort, page |
| GET | Safe, idempotent, cacheable, no body |
| POST | Not idempotent; use `Idempotency-Key`; 201 + `Location` |
| PUT | Full replace; idempotent |
| PATCH | Partial update; not guaranteed idempotent |
| DELETE | Idempotent; 204 |
| 401 / 403 | Not authenticated / not allowed |
| 400 / 422 | Can't parse / parsed but invalid |
| 409 / 412 | State conflict / ETag precondition failed |
| 429 | Rate limited; send `Retry-After` |
| Errors | `application/problem+json`, RFC 9457 |
| Pagination | Cursor for scale, offset for small page-jump tables |
| Caching | `Cache-Control`, `ETag`, `If-None-Match` → 304 |
| Concurrency | `If-Match` → 412 on conflict |
| Versioning | Additive changes; `/v1`; `Deprecation` + `Sunset` headers |
| Security | HTTPS, auth every call, check every object, validate input, allowlist fields |
| Rate limiting | Token bucket, Redis, per user and key |
| Reliability | Timeouts, backoff + jitter, circuit breaker, 503 + `Retry-After` |

**One sentence each**

- REST is a set of constraints, and a RESTful API is one that honours them over HTTP.
- Good REST design is mostly about modelling resources well and using HTTP's existing semantics
  precisely instead of reinventing them.
- A production API is defined less by its happy path than by how it handles errors, retries,
  change, abuse and failure.

---

# 22. References

- Roy Fielding, [Architectural Styles and the Design of Network-based Software Architectures](https://ics.uci.edu/~fielding/pubs/dissertation/top.htm), chapter 5, 2000
- [RFC 9110 — HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html): methods, status codes, conditional requests
- [RFC 9111 — HTTP Caching](https://www.rfc-editor.org/rfc/rfc9111.html)
- [RFC 9457 — Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html)
- [RFC 7396 — JSON Merge Patch](https://www.rfc-editor.org/rfc/rfc7396.html) and [RFC 6902 — JSON Patch](https://www.rfc-editor.org/rfc/rfc6902.html)
- [RFC 8288 — Web Linking](https://www.rfc-editor.org/rfc/rfc8288.html)
- [RFC 9745 — The Deprecation HTTP Response Header Field](https://www.rfc-editor.org/rfc/rfc9745.html) and [RFC 8594 — The Sunset Header Field](https://www.rfc-editor.org/rfc/rfc8594.html)
- [IETF draft — The Idempotency-Key HTTP Header Field](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/)
- [IETF draft — RateLimit header fields for HTTP](https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/)
- [OWASP API Security Top 10 — 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)
- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)
- Martin Fowler, [Richardson Maturity Model](https://martinfowler.com/articles/richardsonMaturityModel.html)
- Hello Interview, [API Design](https://www.hellointerview.com/learn/system-design/core-concepts/api-design) and [Networking Essentials](https://www.hellointerview.com/learn/system-design/core-concepts/networking-essentials), referenced in the notes

---

**Previous:** [DNS & Load Balancing](../5.%20DNS_LOAD_BALANCING/README.md)

**Related:** [HTTP Evolution — HTTP/1.1, HTTP/2 & HTTP/3](../4.%20HTTP_EVOLUTION_HTTP1.1_HTTP2_HTTP3/README.md)

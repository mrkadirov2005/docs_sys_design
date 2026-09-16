# GraphQL Practical Challenges

This document covers the hard, real-world problems you face when running GraphQL in production. Every section maps to a question that shows up in system design interviews: the N+1 problem, query cost control, federation at scale, caching strategies, and more. Code examples use Node.js / Apollo Server unless noted otherwise.

---

## 1. The N+1 Query Problem

### What It Is

When a GraphQL query resolves a list of items and each item triggers a **separate** database query for a related field. The "1" is the initial list query; the "N" is one query per item in that list.

> Query 50 users, each user triggers a separate query for their posts = **1 + 50 = 51 queries**.

### Why It Happens in GraphQL

Resolvers execute **per-field**. A field resolver for `posts` on a `User` type runs independently for each user in the list. Each invocation has no knowledge of the others -- it only sees its own parent object.

### Schema That Triggers It

```graphql
type Query {
  users: [User!]!
}

type User {
  id: ID!
  name: String!
  posts: [Post!]!    # This field causes N+1
}

type Post {
  id: ID!
  title: String!
  body: String!
}
```

### The Naive Resolver

```js
const resolvers = {
  Query: {
    users: () => db.query('SELECT * FROM users'),  // 1 query
  },
  User: {
    // This runs ONCE PER USER in the list
    posts: (parent) => {
      // If 50 users returned above, this executes 50 times
      return db.query('SELECT * FROM posts WHERE author_id = ?', [parent.id]);
    },
  },
};
```

### SQL Queries Generated

```sql
-- 1 query for the list
SELECT * FROM users;

-- Then N queries, one per user:
SELECT * FROM posts WHERE author_id = 1;
SELECT * FROM posts WHERE author_id = 2;
SELECT * FROM posts WHERE author_id = 3;
...
SELECT * FROM posts WHERE author_id = 50;
-- Total: 51 queries
```

### The Optimized Approach (Preview)

Batch all 50 user IDs into a single query:

```sql
SELECT * FROM posts WHERE author_id IN (1, 2, 3, ..., 50);
-- Total: 2 queries (1 for users, 1 for all posts)
```

This is exactly what **DataLoader** does automatically.

---

## 2. DataLoader

### What DataLoader Is

A utility created by Facebook that **batches** and **caches** individual data loads within a single request. It collects all IDs requested during one tick of the event loop, then makes **one batched query** instead of N individual ones.

### How It Works

1. Resolver calls `loader.load(id)` for each item.
2. DataLoader defers execution to the next tick (`process.nextTick`).
3. All IDs collected in that tick are passed to the **batch function** as an array.
4. Batch function returns results in the **same order** as the input keys.
5. Each `load()` promise resolves with its corresponding result.
6. Same ID requested twice in one request? Served from per-request cache.

### Implementation

```js
const DataLoader = require('dataloader');

// The batch function: receives array of keys, returns array of results
// RULE: results must be same length and same order as keys
function createPostLoader() {
  return new DataLoader(async (userIds) => {
    // One query for ALL user IDs
    const posts = await db.query(
      'SELECT * FROM posts WHERE author_id IN (?)',
      [userIds]
    );

    // Group posts by author_id
    const postsByUser = {};
    for (const post of posts) {
      if (!postsByUser[post.author_id]) {
        postsByUser[post.author_id] = [];
      }
      postsByUser[post.author_id].push(post);
    }

    // Return in same order as input keys
    // If a user has no posts, return empty array (not undefined)
    return userIds.map(id => postsByUser[id] || []);
  });
}
```

### Using DataLoader in Resolvers

```js
// server.js -- create new loaders PER REQUEST
const server = new ApolloServer({
  typeDefs,
  resolvers,
  context: () => ({
    loaders: {
      posts: createPostLoader(),   // Fresh instance per request
      users: createUserLoader(),
    },
  }),
});

// resolvers.js -- use the loader instead of direct DB calls
const resolvers = {
  Query: {
    users: () => db.query('SELECT * FROM users'),
  },
  User: {
    posts: (parent, _args, context) => {
      // DataLoader batches these automatically
      return context.loaders.posts.load(parent.id);
    },
  },
};
```

### Before and After: SQL Queries

| Without DataLoader | With DataLoader |
|---|---|
| `SELECT * FROM users` | `SELECT * FROM users` |
| `SELECT * FROM posts WHERE author_id = 1` | `SELECT * FROM posts WHERE author_id IN (1, 2, ..., 50)` |
| `SELECT * FROM posts WHERE author_id = 2` | |
| `... (50 queries)` | |
| **51 queries total** | **2 queries total** |

### Key Rules

1. **Same order**: Batch function must return results in the exact same order as the input keys.
2. **Same length**: Must return exactly one result per key (use `null` or `[]` for missing).
3. **Per-request instantiation**: Create a new DataLoader per request, never share globally. Global sharing leaks data between users and serves stale cache.

### Caching Behavior

```js
const loader = new DataLoader(batchFn);

// Per-request cache (NOT cross-request)
await loader.load(1);  // DB hit
await loader.load(1);  // Cache hit, no DB query

// Manual cache control
loader.prime(42, { id: 42, name: 'Ada' });  // Pre-populate cache
loader.clear(42);                            // Remove from cache
loader.clearAll();                           // Flush entire cache
```

> **Important:** DataLoader's cache is per-request only. It does not replace Redis or Memcached for cross-request caching.

---

## 3. Query Complexity & Cost Analysis

### The Problem

Clients can send **arbitrarily deep or wide** queries that overload the server. A single GraphQL request can trigger thousands of database queries and consume unbounded memory.

### Malicious Query Example

```graphql
{
  users {           # 100 users
    posts {         # 50 posts each = 5,000
      comments {    # 20 comments each = 100,000
        author {    # 1 author each = 100,000
          posts {   # 50 posts each = 5,000,000
            comments {  # 20 each = 100,000,000
              author {
                # ...keeps going
              }
            }
          }
        }
      }
    }
  }
}
```

### Solution 1: Query Depth Limiting

Set a maximum nesting depth. Any query exceeding it is rejected before execution.

```js
const depthLimit = require('graphql-depth-limit');

const server = new ApolloServer({
  typeDefs,
  resolvers,
  validationRules: [depthLimit(10)],  // Max 10 levels deep
});
```

### Solution 2: Query Complexity Analysis

Assign a **cost** to each field. Multiply cost by list size. Set a maximum total complexity budget per query.

```graphql
type Query {
  users(first: Int = 10): [User!]!  @complexity(value: 1, multipliers: ["first"])
}

type User {
  id: ID!            @complexity(value: 0)
  name: String!      @complexity(value: 0)
  posts: [Post!]!    @complexity(value: 5, multipliers: ["first"])
}

type Post {
  id: ID!            @complexity(value: 0)
  title: String!     @complexity(value: 0)
  comments: [Comment!]! @complexity(value: 5, multipliers: ["first"])
}
```

#### Calculating Complexity

```graphql
# This query:
{
  users(first: 50) {       # cost = 1 * 50 = 50
    posts(first: 20) {     # cost = 5 * 50 * 20 = 5,000
      comments(first: 10) { # cost = 5 * 50 * 20 * 10 = 50,000
        body
      }
    }
  }
}
# Total complexity: 50 + 5,000 + 50,000 = 55,050
# If budget is 10,000 -> REJECTED
```

### Implementation with graphql-query-complexity

```js
const { createComplexityRule, simpleEstimator, fieldExtensionsEstimator }
  = require('graphql-query-complexity');

const server = new ApolloServer({
  typeDefs,
  resolvers,
  plugins: [{
    requestDidStart: () => ({
      didResolveOperation({ request, document }) {
        const complexity = getComplexity({
          schema,
          operationName: request.operationName,
          query: document,
          variables: request.variables,
          estimators: [
            fieldExtensionsEstimator(),
            simpleEstimator({ defaultComplexity: 1 }),
          ],
        });

        if (complexity > 10000) {
          throw new Error(
            `Query too complex: ${complexity}. Maximum allowed: 10000.`
          );
        }

        console.log('Query complexity:', complexity);
      },
    }),
  }],
});
```

### Rate Limiting by Complexity

Instead of limiting by request count (which treats a simple `{ me { name } }` the same as a massive nested query), limit by **total complexity consumed per time window**.

```js
// Pseudocode
const userBudget = await redis.get(`complexity:${userId}`);  // e.g., 100,000 per minute
const queryCost = calculateComplexity(query);

if (userBudget - queryCost < 0) {
  throw new Error('Complexity budget exceeded. Try again later.');
}

await redis.decrby(`complexity:${userId}`, queryCost);
```

### Persisted Queries / Allowlisting

Only allow **pre-approved queries** in production. The client sends a query hash instead of the full query string.

```json
// Client sends:
POST /graphql
{
  "extensions": {
    "persistedQuery": {
      "sha256Hash": "abc123def456..."
    }
  },
  "variables": { "id": "42" }
}
```

The server looks up the hash in a registry of approved queries. If not found, reject.

> **Automatic Persisted Queries (APQ)**: Client sends hash first. If server doesn't recognize it, client re-sends with full query. Server stores the mapping for next time. This is an optimization, not a security measure -- true allowlisting requires a build step that registers queries.

---

## 4. Schema Stitching & Federation

### The Problem

As a GraphQL API grows, a single monolithic schema becomes hard to maintain. Different teams own different domains (users, orders, inventory) but clients want one unified graph.

### Schema Stitching (Older Approach)

A gateway combines multiple GraphQL schemas into one by merging type definitions and delegating resolvers.

```js
const { stitchSchemas } = require('@graphql-tools/stitch');

const gatewaySchema = stitchSchemas({
  subschemas: [
    {
      schema: await introspectSchema(userServiceExecutor),
      executor: userServiceExecutor,
    },
    {
      schema: await introspectSchema(orderServiceExecutor),
      executor: orderServiceExecutor,
      merge: {
        User: {
          fieldName: 'userById',
          selectionSet: '{ id }',
          args: (original) => ({ id: original.id }),
        },
      },
    },
  ],
});
```

### Apollo Federation (Modern Approach)

Each service defines its own schema independently. A gateway (Apollo Router) composes them into a **supergraph** and builds query plans to fetch data from the right services.

#### User Service

```graphql
# user-service/schema.graphql
type User @key(fields: "id") {
  id: ID!
  name: String!
  email: String!
}
```

#### Order Service (extends User)

```graphql
# order-service/schema.graphql
type User @key(fields: "id") {
  id: ID! @external
  orders: [Order!]!
}

type Order @key(fields: "id") {
  id: ID!
  total: Float!
  status: String!
  user: User!
}
```

#### Review Service (extends both)

```graphql
# review-service/schema.graphql
type User @key(fields: "id") {
  id: ID! @external
  reviews: [Review!]!
}

type Review @key(fields: "id") {
  id: ID!
  body: String!
  rating: Int!
  author: User!
}
```

#### Composed Supergraph (What Clients See)

```graphql
type User {
  id: ID!
  name: String!      # from User Service
  email: String!     # from User Service
  orders: [Order!]!  # from Order Service
  reviews: [Review!]! # from Review Service
}
```

#### Reference Resolvers

```js
// order-service/resolvers.js
const resolvers = {
  User: {
    __resolveReference(user) {
      // 'user' contains only { id } from the @key
      return orderDb.getOrdersByUserId(user.id);
    },
  },
};
```

### Federation Directives

| Directive | Purpose | Example |
|---|---|---|
| `@key` | Declares entity's primary key for cross-service resolution | `type User @key(fields: "id")` |
| `@external` | Marks a field as owned by another service | `id: ID! @external` |
| `@requires` | Declares fields from other services needed to resolve this field | `totalWithTax: Float! @requires(fields: "total")` |
| `@provides` | Declares fields of an entity that this service can resolve (optimization) | `user: User! @provides(fields: "name")` |

### Federation vs Stitching

| Aspect | Schema Stitching | Apollo Federation |
|---|---|---|
| Ownership | Gateway owns the merged schema | Each service owns its own schema |
| Coupling | Gateway must know about all services' types | Services independently declare types |
| Type extension | Complex merge config at gateway | `@key` / `@external` at the service |
| Query planning | Manual delegation rules | Automatic query plan generation |
| Team independence | Low -- gateway changes for every service change | High -- services deploy independently |
| Tooling | graphql-tools | Apollo Router / Gateway |
| Status | Legacy, mostly replaced | Industry standard |

---

## 5. Caching in GraphQL

### Why Caching Is Hard

REST APIs use different URLs for different resources, so HTTP caching (CDN, browser cache) works naturally. GraphQL has a **single endpoint** (`POST /graphql`) with different query bodies -- traditional URL-based caching doesn't apply.

### Client-Side Caching (Normalized Cache)

Apollo Client and Relay use **normalized caching**: objects are stored by `__typename` + `id`, not by query shape.

```js
// Apollo Client automatically normalizes:
// Query 1: { user(id: 1) { id name } }  -> cache: User:1 = { name: "Alice" }
// Query 2: { post(id: 5) { author { id name } } }
//   -> hits cache for User:1 if author.id === 1

// After a mutation, cache updates automatically if the response
// includes the modified object with its id:
const [updateUser] = useMutation(UPDATE_USER, {
  // Apollo matches the returned id to the cached object
  // and updates all queries referencing it
});
```

### CDN / HTTP Caching

Make queries cacheable at the HTTP layer:

- **GET requests**: Put the query in the URL so CDNs can cache by URL.

  ```
  GET /graphql?query={user(id:1){name}}&variables={}
  ```

- **Automatic Persisted Queries (APQ)**: Client sends a hash; CDN caches by hash.

  ```
  GET /graphql?extensions={"persistedQuery":{"sha256Hash":"abc123"}}
  ```

- **Cache-Control headers**: Apollo Server can compute max-age from field-level `@cacheControl` directives.

  ```graphql
  type User @cacheControl(maxAge: 300) {
    id: ID!
    name: String! @cacheControl(maxAge: 600)
    email: String! @cacheControl(maxAge: 0)  # Never cache
  }
  ```

### Server-Side Caching

```js
// Response caching: cache the entire query result
const { responseCachePlugin } = require('@apollo/server-plugin-response-cache');

const server = new ApolloServer({
  plugins: [responseCachePlugin()],
});

// Resolver-level caching with Redis
const resolvers = {
  Query: {
    user: async (_, { id }, { redis }) => {
      const cached = await redis.get(`user:${id}`);
      if (cached) return JSON.parse(cached);

      const user = await db.query('SELECT * FROM users WHERE id = ?', [id]);
      await redis.set(`user:${id}`, JSON.stringify(user), 'EX', 300);
      return user;
    },
  },
};
```

### Cache Invalidation

Harder than REST because the same data appears in differently shaped responses.

| Strategy | How It Works | Trade-off |
|---|---|---|
| TTL-based | Cache entries expire after a fixed time | Simple but serves stale data until expiry |
| Event-based | Mutations publish events; listeners invalidate affected cache entries | Real-time but complex to wire up |
| Tag-based | Tag cache entries (e.g., `user:42`); purge all entries with a tag on mutation | Good balance; supported by some CDNs |

---

## 6. File Uploads

### The Problem

The GraphQL spec doesn't define how to handle file uploads. The standard JSON request body isn't designed for binary data.

### Approach 1: graphql-upload (Multipart)

```graphql
scalar Upload

type Mutation {
  uploadAvatar(file: Upload!): String!
}
```

```js
const resolvers = {
  Mutation: {
    uploadAvatar: async (_, { file }) => {
      const { createReadStream, filename, mimetype } = await file;
      const stream = createReadStream();
      const path = `uploads/${Date.now()}-${filename}`;
      await saveToStorage(stream, path);
      return path;
    },
  },
};
```

### Approach 2: Separate REST Endpoint

```
POST /api/upload -> returns { url: "https://cdn.example.com/abc.jpg" }
```

Then use the URL in a GraphQL mutation:

```graphql
mutation {
  updateProfile(avatarUrl: "https://cdn.example.com/abc.jpg") {
    id
    avatarUrl
  }
}
```

### Approach 3: Pre-Signed URLs (Best Practice)

```graphql
# Step 1: Get a pre-signed upload URL from GraphQL
mutation {
  createUploadUrl(filename: "photo.jpg", contentType: "image/jpeg") {
    uploadUrl     # Pre-signed S3 URL
    fileKey       # Key to reference after upload
  }
}

# Step 2: Client uploads directly to S3 using the pre-signed URL
# (No file goes through your GraphQL server)

# Step 3: Confirm upload in GraphQL
mutation {
  confirmUpload(fileKey: "photo.jpg") {
    url  # Final CDN URL
  }
}
```

> **Why pre-signed URLs win:** Your GraphQL server never handles binary data. Uploads go directly to object storage (S3, GCS). Scales independently. Supports large files without server memory pressure.

---

## 7. Error Handling

### GraphQL Errors Array

GraphQL responses can contain **both data and errors**. Unlike REST (which returns one status code), GraphQL can partially succeed.

```json
{
  "data": {
    "user": {
      "name": "Alice",
      "email": null
    }
  },
  "errors": [
    {
      "message": "Not authorized to view email",
      "path": ["user", "email"],
      "extensions": {
        "code": "FORBIDDEN"
      }
    }
  ]
}
```

### Throwing Errors in Resolvers

```js
const { GraphQLError } = require('graphql');

const resolvers = {
  Query: {
    user: (_, { id }, context) => {
      if (!context.user) {
        throw new GraphQLError('Authentication required', {
          extensions: { code: 'UNAUTHENTICATED' },
        });
      }

      const user = db.findUser(id);
      if (!user) {
        throw new GraphQLError('User not found', {
          extensions: { code: 'NOT_FOUND', id },
        });
      }

      return user;
    },
  },
};
```

### Union-Based Error Handling (Type-Safe)

Return errors as **typed union members** instead of relying on the errors array. This makes errors part of the schema -- clients handle them with pattern matching.

```graphql
type User {
  id: ID!
  name: String!
}

type NotFoundError {
  message: String!
  resourceId: ID!
}

type ForbiddenError {
  message: String!
  requiredRole: String!
}

union UserResult = User | NotFoundError | ForbiddenError

type Query {
  user(id: ID!): UserResult!
}
```

```graphql
# Client query
query {
  user(id: "42") {
    ... on User {
      id
      name
    }
    ... on NotFoundError {
      message
      resourceId
    }
    ... on ForbiddenError {
      message
      requiredRole
    }
  }
}
```

```js
// Resolver
const resolvers = {
  Query: {
    user: (_, { id }, context) => {
      if (!context.user) {
        return { __typename: 'ForbiddenError', message: 'Login required', requiredRole: 'USER' };
      }
      const user = db.findUser(id);
      if (!user) {
        return { __typename: 'NotFoundError', message: 'User not found', resourceId: id };
      }
      return { __typename: 'User', ...user };
    },
  },
};
```

| Approach | Pros | Cons |
|---|---|---|
| Errors array | Simple, built-in, no schema changes | Untyped, clients must parse strings |
| Union types | Type-safe, self-documenting, pattern matching | More schema boilerplate |

---

## 8. Authentication & Authorization

### Authentication via Context

Authentication typically happens in HTTP middleware. The authenticated user is placed into the GraphQL `context`, which every resolver receives.

```js
const server = new ApolloServer({
  typeDefs,
  resolvers,
  context: ({ req }) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    const user = token ? verifyJWT(token) : null;
    return { user };
  },
});
```

### Authorization: Resolver-Level Checks

```js
const resolvers = {
  Query: {
    adminDashboard: (_, __, context) => {
      if (!context.user) throw new GraphQLError('Not authenticated');
      if (context.user.role !== 'ADMIN') throw new GraphQLError('Not authorized');
      return getDashboardData();
    },
  },
};
```

### Authorization: Directive-Based

```graphql
directive @auth(requires: Role = ADMIN) on FIELD_DEFINITION

enum Role {
  ADMIN
  USER
  EDITOR
}

type Query {
  users: [User!]! @auth(requires: ADMIN)
  me: User! @auth(requires: USER)
  publicPosts: [Post!]!  # No directive = public
}
```

```js
function authDirective(schema) {
  return mapSchema(schema, {
    [MapperKind.FIELD]: (fieldConfig) => {
      const authDirective = getDirective(schema, fieldConfig, 'auth')?.[0];
      if (!authDirective) return fieldConfig;

      const requiredRole = authDirective.requires;
      const originalResolve = fieldConfig.resolve;

      fieldConfig.resolve = (source, args, context, info) => {
        if (!context.user) throw new GraphQLError('Not authenticated');
        if (!hasRole(context.user, requiredRole)) {
          throw new GraphQLError(`Requires role: ${requiredRole}`);
        }
        return originalResolve(source, args, context, info);
      };
      return fieldConfig;
    },
  });
}
```

### Authorization: graphql-shield

```js
const { shield, rule, and, or } = require('graphql-shield');

const isAuthenticated = rule()((_, __, context) => !!context.user);
const isAdmin = rule()((_, __, context) => context.user?.role === 'ADMIN');
const isOwner = rule()((_, { id }, context) => context.user?.id === id);

const permissions = shield({
  Query: {
    users: isAdmin,
    user: and(isAuthenticated, or(isAdmin, isOwner)),
    publicPosts: true,
  },
  Mutation: {
    deleteUser: isAdmin,
    updateProfile: and(isAuthenticated, isOwner),
  },
});

const server = new ApolloServer({
  schema: applyMiddleware(schema, permissions),
});
```

### Field-Level Authorization

```js
const resolvers = {
  User: {
    email: (parent, _, context) => {
      if (context.user?.id === parent.id || context.user?.role === 'ADMIN') {
        return parent.email;
      }
      return null;
    },
    salary: (parent, _, context) => {
      if (context.user?.role !== 'HR' && context.user?.role !== 'ADMIN') {
        throw new GraphQLError('Not authorized to view salary');
      }
      return parent.salary;
    },
  },
};
```

---

## 9. Performance Monitoring

### Resolver-Level Tracing

```js
const server = new ApolloServer({
  typeDefs,
  resolvers,
  plugins: [
    ApolloServerPluginUsageReporting({
      sendVariableValues: { all: true },
      sendHeaders: { all: true },
    }),
  ],
});

// Custom tracing plugin
const tracingPlugin = {
  requestDidStart() {
    const start = Date.now();
    return {
      willResolveField({ info }) {
        const fieldStart = Date.now();
        return () => {
          const duration = Date.now() - fieldStart;
          if (duration > 100) {
            console.warn(
              `Slow resolver: ${info.parentType.name}.${info.fieldName} took ${duration}ms`
            );
          }
        };
      },
      willSendResponse() {
        console.log(`Request took ${Date.now() - start}ms`);
      },
    };
  },
};
```

### Query Logging

```js
const loggingPlugin = {
  requestDidStart({ request }) {
    const operationName = request.operationName || 'anonymous';
    console.log(`Operation: ${operationName}`);

    return {
      didResolveOperation({ operation }) {
        console.log(`Type: ${operation.operation}`);
      },
      willSendResponse({ response }) {
        if (response.body.singleResult?.errors?.length) {
          console.error('Errors:', response.body.singleResult.errors);
        }
      },
    };
  },
};
```

### Schema Analytics

Track which fields are actually used in production:

- **Field usage tracking**: Count how often each field is queried. Identify unused fields that are candidates for deprecation.
- **Operation registry**: Log all unique operations. Detect new or changed queries from clients.
- **Breaking change detection**: Before deploying a schema change, check if any active client queries use the fields being removed.

```graphql
type User {
  id: ID!
  name: String!
  fullName: String!
  username: String! @deprecated(reason: "Use 'name' instead. Removal: 2025-01-01")
}
```

---

## 10. Quick Revision Sheet

| Challenge | Root Cause | Solution | Key Tool / Technique |
|---|---|---|---|
| N+1 queries | Per-field resolver execution | Batch data loading | DataLoader |
| Query abuse | Clients send unbounded queries | Depth limiting + complexity analysis | graphql-query-complexity, persisted queries |
| Monolithic schema | Single schema grows too large | Distributed ownership with federation | Apollo Federation, `@key` directive |
| HTTP caching | Single endpoint, POST bodies | GET queries, APQ, normalized client cache | Apollo Client, `@cacheControl` |
| Server caching | Differently shaped responses for same data | Resolver-level caching, response cache | Redis, responseCachePlugin |
| File uploads | Spec doesn't cover binary data | Pre-signed URLs (upload directly to S3) | S3 pre-signed URLs |
| Error handling | Partial success + untyped errors | Union-based result types | `union UserResult = User \| Error` |
| Authorization | Field-level access control needed | Directives or middleware | graphql-shield, `@auth` directive |
| Performance | No built-in observability | Tracing + field usage analytics | Apollo Studio, custom plugins |

---

**Previous:** [GraphQL Architecture & Schema Design](../9.%20GRAPHQL_ARCHITECTURE_SCHEMA_DESIGN/README.md)

**Next:** [Short Polling, Long Polling & SSE](../11.%20SHORT_POLLING_LONG_POLLING_SSE/README.md)

# GraphQL Architecture & Schema Design

## What is GraphQL

GraphQL is a **query language for APIs** and a **runtime** for executing those queries against your data. Created internally by Facebook in 2012 to power their mobile apps, it was open-sourced in 2015 and is now governed by the GraphQL Foundation under the Linux Foundation.

The fundamental idea: the client describes the shape of the data it needs, and the server returns exactly that shape -- nothing more, nothing less.

### Single Endpoint Model

Unlike REST, which exposes many endpoints (`GET /users`, `GET /users/1/posts`, `GET /posts/42/comments`), GraphQL exposes a **single endpoint** (typically `POST /graphql`). The request body contains the query that describes what data to fetch.

```graphql
# REST: 3 requests
GET /users/1
GET /users/1/posts
GET /posts/42/comments

# GraphQL: 1 request
POST /graphql
{
  user(id: 1) {
    name
    posts {
      title
      comments { body author { name } }
    }
  }
}
```

### GraphQL vs REST -- High-Level

| Aspect | REST | GraphQL |
|--------|------|---------|
| Endpoints | Multiple (one per resource) | Single endpoint |
| Data fetching | Server decides response shape | Client specifies exact fields |
| Over-fetching | Common (returns full resource) | Eliminated (only requested fields) |
| Under-fetching | Common (requires multiple calls) | Eliminated (nested queries) |
| Type system | Optional (OpenAPI/Swagger) | Built-in, required schema |
| Versioning | URL versioning (/v1, /v2) | No versioning needed (evolve schema) |
| Caching | HTTP caching works out of the box | Requires custom caching strategy |
| Learning curve | Low | Medium-High |

---

## Core Concepts

### Schema

The schema is the **contract between client and server**. It defines every type, field, query, mutation, and subscription available in the API. Written in the Schema Definition Language (SDL), the schema serves as both documentation and validation layer.

```graphql
# Every GraphQL API has a root schema
schema {
  query: Query
  mutation: Mutation
  subscription: Subscription
}
```

The schema is the single source of truth. Clients can only request fields that exist in the schema, and the server validates every incoming query against it before execution.

### Type System

GraphQL has a rich, strongly-typed system. Every field has a defined type.

#### Scalar Types (built-in primitives)

| Type | Description | Example |
|------|-------------|---------|
| `Int` | Signed 32-bit integer | `42` |
| `Float` | Signed double-precision floating-point | `3.14` |
| `String` | UTF-8 character sequence | `"hello"` |
| `Boolean` | true or false | `true` |
| `ID` | Unique identifier (serialized as String) | `"abc123"` |

#### Object Types

```graphql
type User {
  id: ID!              # Non-null ID
  name: String!        # Non-null String
  email: String
  age: Int
  posts: [Post!]!      # Non-null list of non-null Posts
}
```

#### Enum Types

```graphql
enum Role {
  ADMIN
  EDITOR
  VIEWER
}

type User {
  id: ID!
  role: Role!
}
```

#### Interface Types

```graphql
interface Node {
  id: ID!
}

type User implements Node {
  id: ID!
  name: String!
}

type Post implements Node {
  id: ID!
  title: String!
}
```

#### Union Types

```graphql
union SearchResult = User | Post | Comment

type Query {
  search(term: String!): [SearchResult!]!
}
```

#### Input Types

```graphql
# Input types are used for mutation arguments
input CreateUserInput {
  name: String!
  email: String!
  role: Role = VIEWER   # Default value
}
```

#### Type Modifiers

| Syntax | Meaning | Null allowed? | Empty list? |
|--------|---------|---------------|-------------|
| `String` | Nullable string | Yes | N/A |
| `String!` | Non-null string | No | N/A |
| `[String]` | Nullable list of nullable strings | Yes (list and items) | Yes |
| `[String!]` | Nullable list of non-null strings | List can be null, items cannot | Yes |
| `[String!]!` | Non-null list of non-null strings | No | Yes |

### Schema Definition Language (SDL)

SDL is how you define the complete schema. Here is a realistic example showing types with relationships:

```graphql
type User {
  id: ID!
  username: String!
  email: String!
  profile: Profile
  posts(first: Int = 10, after: String): PostConnection!
  createdAt: DateTime!
}

type Profile {
  bio: String
  avatarUrl: String
  website: String
}

type Post {
  id: ID!
  title: String!
  body: String!
  author: User!
  comments: [Comment!]!
  tags: [String!]!
  publishedAt: DateTime
  status: PostStatus!
}

type Comment {
  id: ID!
  body: String!
  author: User!
  post: Post!
  createdAt: DateTime!
}

enum PostStatus {
  DRAFT
  PUBLISHED
  ARCHIVED
}

# Custom scalar for dates
scalar DateTime
```

---

## Queries

### Basic Query Syntax

A query selects fields on objects. The response mirrors the query shape exactly.

```graphql
# Query
query {
  user(id: "1") {
    name
    email
  }
}

# Response
{
  "data": {
    "user": {
      "name": "Alice",
      "email": "alice@example.com"
    }
  }
}
```

### Nested Queries

Follow relationships by nesting field selections. This is what eliminates under-fetching.

```graphql
query {
  user(id: "1") {
    name
    posts {
      title
      comments {
        body
        author {
          name
        }
      }
    }
  }
}
```

One request fetches the user, their posts, comments on those posts, and the comment authors. In REST, this would require 4+ round trips.

### Arguments & Variables

Fields can accept arguments. Variables let you parameterize queries for reuse.

```graphql
# With inline arguments
query {
  user(id: "1") { name }
  posts(limit: 5, status: PUBLISHED) { title }
}

# With variables (preferred for production)
query GetUser($userId: ID!, $postLimit: Int = 10) {
  user(id: $userId) {
    name
    posts(first: $postLimit) {
      title
    }
  }
}
```

```json
// Variables JSON (sent alongside the query)
{
  "userId": "1",
  "postLimit": 5
}
```

### Aliases

Aliases let you query the same field multiple times with different arguments.

```graphql
query {
  admin: user(id: "1") {
    name
    role
  }
  viewer: user(id: "42") {
    name
    role
  }
}

# Response
{
  "data": {
    "admin": { "name": "Alice", "role": "ADMIN" },
    "viewer": { "name": "Bob", "role": "VIEWER" }
  }
}
```

### Fragments

Fragments are reusable sets of fields. They reduce duplication and make queries maintainable.

```graphql
fragment UserFields on User {
  id
  name
  email
  role
}

query {
  admin: user(id: "1") {
    ...UserFields
    posts { title }
  }
  viewer: user(id: "42") {
    ...UserFields
  }
}

# Inline fragments (for union/interface types)
query {
  search(term: "graphql") {
    ... on User { name email }
    ... on Post { title body }
    ... on Comment { body author { name } }
  }
}
```

### Directives

Directives modify query execution. The two built-in directives:

```graphql
query GetUser($userId: ID!, $withPosts: Boolean!, $skipEmail: Boolean!) {
  user(id: $userId) {
    name
    email @skip(if: $skipEmail)
    posts @include(if: $withPosts) {
      title
    }
  }
}
```

| Directive | Behavior |
|-----------|----------|
| `@include(if: Boolean!)` | Include field only if argument is `true` |
| `@skip(if: Boolean!)` | Skip field if argument is `true` |
| `@deprecated(reason: String)` | Mark a field as deprecated in the schema |

---

## Mutations

Mutations are how clients **modify server-side data**. They are explicitly separated from queries to signal side effects.

### Create / Update / Delete Patterns

```graphql
# Schema
type Mutation {
  createPost(input: CreatePostInput!): Post!
  updatePost(id: ID!, input: UpdatePostInput!): Post!
  deletePost(id: ID!): DeletePostPayload!
}

input CreatePostInput {
  title: String!
  body: String!
  tags: [String!]
  status: PostStatus = DRAFT
}

input UpdatePostInput {
  title: String
  body: String
  tags: [String!]
  status: PostStatus
}

type DeletePostPayload {
  success: Boolean!
  deletedId: ID
}
```

```graphql
# Create
mutation {
  createPost(input: {
    title: "GraphQL Basics"
    body: "GraphQL is a query language..."
    tags: ["graphql", "api"]
  }) {
    id
    title
    status
    author { name }
  }
}

# Update
mutation {
  updatePost(id: "42", input: {
    status: PUBLISHED
  }) {
    id
    title
    status
    publishedAt
  }
}

# Delete
mutation {
  deletePost(id: "42") {
    success
    deletedId
  }
}
```

### Input Types for Mutations

> **Best practice:** Always use dedicated `input` types for mutation arguments rather than listing fields inline. This keeps mutations clean, reusable, and easier to evolve. Suffix them with `Input` (e.g., `CreateUserInput`).

Return the mutated object so the client cache can update automatically:

```graphql
mutation CreateUser($input: CreateUserInput!) {
  createUser(input: $input) {
    id        # Needed for cache identification
    name      # Return what the client cares about
    email
    createdAt
  }
}
```

---

## Subscriptions

Subscriptions provide **real-time data** over a persistent connection, typically a WebSocket. The client subscribes to an event, and the server pushes data when it occurs.

```graphql
# Schema
type Subscription {
  postPublished: Post!
  commentAdded(postId: ID!): Comment!
  userStatusChanged(userId: ID!): UserStatus!
}

# Client subscription
subscription {
  commentAdded(postId: "42") {
    id
    body
    author { name }
    createdAt
  }
}
```

#### When to use subscriptions vs polling

| Use subscriptions when | Use polling when |
|------------------------|------------------|
| Data changes frequently and unpredictably | Data changes at known intervals |
| Low latency is critical (chat, live feeds) | Near-real-time is acceptable |
| Small number of concurrent listeners | Many clients need same data |
| Server can handle persistent connections | Simpler infrastructure preferred |

---

## Resolvers

Resolvers are **functions that populate data for each field** in the schema. The schema defines the shape; resolvers provide the data.

### Resolver Chain

Every resolver receives four arguments:

```javascript
fieldName(parent, args, context, info) {
  // parent  - Result from the parent resolver
  // args    - Arguments passed to this field
  // context - Shared object (auth, DB, loaders) across all resolvers
  // info    - AST and schema metadata about the query
}
```

```javascript
// Example: Node.js resolvers
const resolvers = {
  Query: {
    // Root resolver - no meaningful parent
    user: (parent, { id }, context) => {
      return context.db.users.findById(id);
    },
    posts: (parent, { limit, status }, context) => {
      return context.db.posts.find({ status }).limit(limit);
    },
  },

  // Field-level resolvers
  User: {
    // parent is the User object from the Query.user resolver
    posts: (user, { first = 10 }, context) => {
      return context.db.posts.find({ authorId: user.id }).limit(first);
    },
    fullName: (user) => {
      return `${user.firstName} ${user.lastName}`;
    },
  },

  Post: {
    author: (post, args, context) => {
      return context.db.users.findById(post.authorId);
    },
    comments: (post, args, context) => {
      return context.db.comments.find({ postId: post.id });
    },
  },

  Mutation: {
    createPost: (parent, { input }, context) => {
      if (!context.currentUser) throw new AuthenticationError('Login required');
      return context.db.posts.create({
        ...input,
        authorId: context.currentUser.id,
      });
    },
  },
};
```

### Execution Order & the Resolver Tree

Given this query:

```graphql
query {
  user(id: "1") {       # 1. Query.user resolver
    name                 # 2. User.name (default resolver)
    posts {              # 3. User.posts resolver
      title              # 4. Post.title (default) - runs for EACH post
      author {           # 5. Post.author resolver - runs for EACH post
        name             # 6. User.name (default)
      }
    }
  }
}
```

Resolvers execute **breadth-first by level, depth-first by field**. Sibling fields at the same level resolve in parallel; a child waits for its parent to resolve first.

#### Default (Trivial) Resolvers

If you don't define a resolver for a field, GraphQL uses a default resolver that returns `parent[fieldName]`. You only need custom resolvers when the field name doesn't match the property, or when you need to fetch data from another source.

#### Context Object

The context is created once per request and shared across all resolvers:

```javascript
// Server setup
const server = new ApolloServer({
  typeDefs,
  resolvers,
  context: ({ req }) => ({
    currentUser: getUserFromToken(req.headers.authorization),
    db: database,
    loaders: createDataLoaders(),  // For N+1 prevention
  }),
});
```

---

## Schema Design Best Practices

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Fields | camelCase | `firstName`, `createdAt` |
| Types | PascalCase | `User`, `BlogPost` |
| Enums | PascalCase type, SCREAMING_SNAKE values | `PostStatus.PUBLISHED` |
| Input types | PascalCase + "Input" suffix | `CreateUserInput` |
| Mutations | verb + noun | `createUser`, `deletePost` |
| Queries | noun (singular or plural) | `user`, `posts` |

### Nullable vs Non-Nullable Fields

> **Rule of thumb:** Start nullable, then add `!` only when you're certain the field will always have a value. A non-null field that fails to resolve causes the error to propagate up to the nearest nullable parent, potentially nullifying an entire object.

| Use `!` (non-null) when | Keep nullable when |
|--------------------------|---------------------|
| Field is a database primary key (`id: ID!`) | Field might not exist yet (`publishedAt`) |
| Field is always present by schema logic | Field comes from an external service that can fail |
| Field is an enum with a guaranteed value | Field is optional user data (`bio`, `website`) |

### Pagination Patterns

#### Offset-Based (simple but fragile)

```graphql
type Query {
  posts(offset: Int = 0, limit: Int = 20): [Post!]!
}

# Usage
query { posts(offset: 40, limit: 20) { title } }
```

Problem: if items are inserted or deleted between page requests, you can skip or duplicate items.

#### Cursor-Based / Relay-Style Connections (robust)

```graphql
type Query {
  posts(first: Int, after: String, last: Int, before: String): PostConnection!
}

type PostConnection {
  edges: [PostEdge!]!
  pageInfo: PageInfo!
  totalCount: Int
}

type PostEdge {
  node: Post!
  cursor: String!    # Opaque cursor (typically base64-encoded ID)
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}
```

```graphql
# First page
query {
  posts(first: 10) {
    edges {
      node { id title }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}

# Next page
query {
  posts(first: 10, after: "Y3Vyc29yOjEw") {
    edges {
      node { id title }
      cursor
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

### Error Handling

#### Approach 1: Top-Level Errors Array (default)

```json
{
  "data": { "user": null },
  "errors": [
    {
      "message": "User not found",
      "locations": [{ "line": 2, "column": 3 }],
      "path": ["user"],
      "extensions": { "code": "NOT_FOUND" }
    }
  ]
}
```

#### Approach 2: Union Types for Errors (recommended for expected errors)

```graphql
union CreateUserResult = User | ValidationError | DuplicateEmailError

type ValidationError {
  message: String!
  field: String!
}

type DuplicateEmailError {
  message: String!
  existingEmail: String!
}

type Mutation {
  createUser(input: CreateUserInput!): CreateUserResult!
}

# Client handles each case
mutation {
  createUser(input: { name: "Alice", email: "alice@test.com" }) {
    ... on User { id name }
    ... on ValidationError { message field }
    ... on DuplicateEmailError { message }
  }
}
```

### Schema Evolution

GraphQL schemas evolve without versioning. Deprecate old fields instead of breaking them:

```graphql
type User {
  id: ID!
  name: String! @deprecated(reason: "Use firstName and lastName instead")
  firstName: String!
  lastName: String!
}
```

Deprecated fields still work but are flagged in tooling (GraphiQL, Apollo Studio). Remove them only after all clients have migrated.

### Relay Specification

The Relay spec defines three patterns for a consistent, predictable schema:

1. **Node Interface** -- Every object has a globally unique `id` and can be re-fetched via `node(id: ID!)`
2. **Global Object Identification** -- IDs are opaque and globally unique (often base64-encoded `Type:localId`)
3. **Connections** -- Cursor-based pagination with `edges`, `node`, `pageInfo` (described above)

```graphql
interface Node {
  id: ID!
}

type Query {
  node(id: ID!): Node
  nodes(ids: [ID!]!): [Node]!
}

# Any type that implements Node can be fetched by ID
type User implements Node {
  id: ID!     # Globally unique, e.g., base64("User:123")
  name: String!
}
```

---

## GraphQL vs REST -- Detailed Comparison

| Criteria | REST | GraphQL |
|----------|------|---------|
| Data fetching | Fixed structure per endpoint | Client specifies exact fields |
| Endpoints | Many (one per resource + action) | Single endpoint |
| Over-fetching | Server returns full resource | Only requested fields returned |
| Under-fetching | Multiple round trips needed | Nested queries in single request |
| Type safety | Optional (JSON Schema, OpenAPI) | Built-in strong type system |
| Versioning | URL-based (/v1, /v2) | Schema evolution, no versions |
| Caching | HTTP caching (ETags, Cache-Control) | Needs client-side normalized cache |
| File uploads | Multipart/form-data natively | Requires multipart spec or separate endpoint |
| Error handling | HTTP status codes (404, 500) | Always 200, errors in response body |
| Tooling | Postman, curl, browser | GraphiQL, Apollo Studio, Playground |
| Real-time | Webhooks, SSE, polling | Built-in subscriptions (WebSocket) |
| Introspection | Requires separate docs (Swagger) | Built-in schema introspection |
| Learning curve | Low (HTTP fundamentals) | Medium-High (SDL, resolvers, client libs) |
| Best for | Simple CRUD, public APIs, microservices | Complex data graphs, mobile apps, BFFs |

### When to Use GraphQL

- Mobile apps where bandwidth and round trips matter
- Complex data requirements with deep relationships
- Rapid frontend iteration (no backend changes needed for new data shapes)
- Backend-for-Frontend (BFF) layer aggregating multiple services
- When multiple clients (web, mobile, TV) need different data shapes from the same API

### When to Stick with REST

- Simple CRUD APIs without complex relationships
- Public APIs consumed by third parties (REST is more universally understood)
- File-heavy APIs (uploads, downloads)
- When HTTP caching is critical to your architecture
- Microservice-to-microservice communication (gRPC is often better here)

---

## Introspection

Introspection allows clients to **query the schema itself** -- discover types, fields, arguments, and documentation at runtime.

```graphql
# Query all types in the schema
{
  __schema {
    types {
      name
      kind
      description
    }
  }
}

# Query a specific type
{
  __type(name: "User") {
    name
    fields {
      name
      type {
        name
        kind
        ofType { name }
      }
    }
  }
}

# Query available queries and mutations
{
  __schema {
    queryType { fields { name description } }
    mutationType { fields { name description } }
  }
}
```

### Why Introspection Matters

- **Tooling:** GraphiQL, Apollo Studio, and Playground all use introspection to provide autocomplete, documentation, and schema exploration
- **Code generation:** Tools like GraphQL Code Generator create TypeScript types from the schema via introspection
- **Validation:** Clients can validate queries against the live schema before sending them

### Security: Disable in Production

> Introspection reveals your entire API surface. Disable it in production to prevent attackers from mapping your schema. Keep it enabled in development and staging.

```javascript
// Apollo Server
const server = new ApolloServer({
  typeDefs,
  resolvers,
  introspection: process.env.NODE_ENV !== 'production',
});
```

---

## Quick Revision Sheet

| Concept | Key Point |
|---------|-----------|
| GraphQL | Query language for APIs. Client asks for exactly what it needs. |
| Schema | Contract between client and server. Written in SDL. Single source of truth. |
| Types | Scalar (Int, Float, String, Boolean, ID), Object, Enum, Input, Union, Interface. |
| `!` modifier | Non-null. Error propagates up to nearest nullable parent if field fails. |
| Query | Read data. Nested fields follow relationships. Single request, exact shape. |
| Mutation | Write data. Use `input` types. Return the mutated object. |
| Subscription | Real-time via WebSocket. Server pushes on events. |
| Resolver | Function per field: `(parent, args, context, info)`. Default returns `parent[field]`. |
| Fragment | Reusable field set. Inline fragments for unions/interfaces. |
| Directive | `@include`, `@skip` (client); `@deprecated` (schema). |
| Pagination | Cursor-based (Relay connections) is robust. Offset-based is simple but fragile. |
| Error handling | Top-level errors array (default) or union-type result types (for expected errors). |
| Introspection | Query the schema itself (`__schema`, `__type`). Disable in production. |
| N+1 Problem | Resolver per field can cause N+1 DB queries. Solve with DataLoader (batching). |
| Caching | No HTTP caching. Use normalized client cache (Apollo) or persisted queries. |
| vs REST | GraphQL: flexible, typed, single endpoint. REST: simple, cacheable, universal. |

---

**Previous:** [gRPC Practical Patterns & Streaming](../8.%20GRPC_PRACTICAL_PATTERNS_STREAMING/README.md)

**Next:** [GraphQL Practical Challenges](../10.%20GRAPHQL_PRACTICAL_CHALLENGES/README.md)

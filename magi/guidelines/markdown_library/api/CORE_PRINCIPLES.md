# Core Principles

These guidelines define strict, consistent, and maintainable patterns for REST API design, optimizing for:

- **Predictability**: Clients infer behavior from conventions; every endpoint follows the same structural patterns
- **Discoverability**: Resources link to related resources; the API teaches itself through consistent responses
- **Evolvability**: APIs change over time; design anticipates extension without breaking existing clients
- **Debuggability**: Every request and response carries sufficient context for troubleshooting without access to server logs
- **Performance by Default**: Payloads are minimal, caching is explicit, and expensive operations are clearly signaled

### Primary Rule: The API Is a Contract

An API is a public interface with external consumers who cannot update in lockstep with your releases. Every endpoint, field, and behavior becomes a commitment. Breaking changes break trust. Design as if every decision is permanent, because to your consumers, it effectively is. Deprecation and versioning exist to manage evolution, not to excuse poor initial design.

### Secondary Rule: Resources Over Actions

REST APIs model resources, not remote procedure calls. The URL identifies what you're operating on; the HTTP method identifies what you're doing. If your endpoint reads like a function call (`/api/createUser`, `/api/sendEmail`), the design is wrong. Resources are nouns; HTTP methods are verbs. Combine them correctly.

### API Style Selection

These guidelines assume RESTful HTTP APIs. Other styles have specific use cases:

- **GraphQL**: Client-driven query flexibility; appropriate when clients have highly variable data needs and the cost of multiple REST calls is prohibitive (see §15)
- **gRPC**: High-performance binary protocol; appropriate for internal service-to-service communication with strict latency requirements
- **WebSocket**: Bidirectional real-time communication; appropriate for live updates, chat, and streaming scenarios
- **Server-Sent Events**: Server-to-client streaming; appropriate for one-way real-time feeds

Choose REST when building public APIs, when HTTP semantics map naturally to your domain, and when broad client compatibility matters. REST remains the default for external-facing APIs due to tooling maturity, cacheability, and universal client support.

---
[Back to Overview](./OVERVIEW.md)

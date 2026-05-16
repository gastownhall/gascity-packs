# Shakedown — Integration Validation

### Definition

A Swift shakedown is the **first controlled, end-to-end execution of a Swift target under real operating conditions** — real `URLSession` against real backends, real Keychain, real push notification registration, real CoreData or SwiftData store. It is integration validation of the composed system, **distinct from XCTest unit tests, SwiftLint/SwiftFormat preflight, and Instruments performance profiling**.

It answers: **does the composed app or server work end-to-end before TestFlight, App Store, or Vapor/Hummingbird production deployment?**

| Phase | Question |
|:------|:---------|
| Preflight | Static prerequisites: `swift build` succeeds, SwiftLint passes, SwiftFormat verifies, `Info.plist` entitlements present, provisioning profile valid |
| **Shakedown** | **Integration validation under real conditions** — DI graph composes, Keychain reads/writes, URLSession reaches backend, async/await task cancellation honored, push registration completes |
| Testing | XCTest unit tests with mocks, XCUITest UI tests, Instruments profiling — **not shakedown** |

### Shakedown Forms

A Swift shakedown takes one of three forms:

1. **XCTest integration target** — a dedicated `ShakedownTests` target separate from `UnitTests` that instantiates the production DI graph, points it at the sandbox backend, and exercises the critical paths. Run via `xcodebuild -scheme Shakedown` before release.
2. **Server-side startup** — for server-side Swift (Vapor, Hummingbird, SwiftNIO), an async function invoked during `app.lifecycle.use` or before the event loop group accepts traffic. Exercises database connectivity (Fluent), Redis, external HTTP clients (`AsyncHTTPClient`), and each critical route with a known-good request. Throws on `failBlocking` to abort startup.
3. **First-launch beta** — TestFlight/beta build first-launch shakedown pass. Build configuration flag gates a shakedown runner that executes on first launch, runs known-good inputs through critical paths, records artifacts to the app's Application Support directory (**never system temp**), and surfaces the classification via a diagnostic view before the normal UI loads.

### Mandatory Triggers

Shakedown is required when any of these occur:

- First TestFlight or App Store submission of a new target.
- Major refactor crossing actor isolation boundaries, async/await signatures, or protocol requirements.
- Swift toolchain upgrade (Swift version bump, Xcode major version change).
- iOS/macOS deployment target bump or new SDK baseline.
- Swift concurrency migration (Swift 5 → Swift 6 strict concurrency checking).
- `URLSession` configuration change, backend endpoint migration, CDN swap.
- Keychain accessibility change, App Group swap, Sign in with Apple reconfiguration.
- CoreData or SwiftData model migration.
- Push notification entitlement or APNs environment change.
- Deep link scheme or Universal Link domain change.
- Repair after a crash loop affecting integration boundaries.

### Non-Triggers

- SwiftUI view tweaks with no data flow or dependency changes.
- Localization string updates.
- Asset catalog changes (image, color, symbol updates).
- Bug fixes confined to a single struct/enum with no async or actor boundaries crossed.
- Unit-test-only changes.

### Validation Categories

A Swift shakedown validates these integration surfaces explicitly:

1. **Dependency injection graph** — every protocol-backed dependency resolves to its production implementation; factory closures run without retain cycles; initializer injection chains complete.
2. **Keychain and UserDefaults propagation** — `kSecAttrService` keys read and write; `kSecAttrAccessible` flags honored; UserDefaults suite loads expected values; App Group defaults shared across extensions.
3. **async/await task cancellation paths** — `Task.isCancelled` checks fire where expected; structured concurrency children cancel when parents cancel; `withTaskCancellationHandler` runs its cleanup; no detached `Task`s orphan.
4. **URLSession reachability** — real requests to sandbox endpoints complete; TLS validates; `URLSessionConfiguration` applies (timeouts, cache policy, TLS pinning); response decoding via `JSONDecoder` into `Codable` types.
5. **Background task scheduling** — `BGTaskScheduler` submissions accept; `BGAppRefreshTask` and `BGProcessingTask` handlers register; expiration handlers fire.
6. **Push notification registration** — `UNUserNotificationCenter` requests authorization; `UIApplication.registerForRemoteNotifications` delivers an APNs token; the token reaches the backend registration endpoint.
7. **Deep link handler wiring** — SceneDelegate/AppDelegate URL handlers route to expected destination; Universal Links associated domains validate; `NSUserActivity` handoff routes correctly.
8. **Combine/AsyncSequence subscriptions** — publishers emit expected values; `AnyCancellable` storage prevents premature deinit; `for-await-in` loops complete without stranding.

### Execution Principles

- **Conservative inputs** — representative `Codable` payloads with known expected outputs; not property-based generators, not fuzz inputs.
- **Progressive stress** — start with a single async `Task` executing the happy path; add structured concurrency via `async let` and `TaskGroup` incrementally; stop on first failure.
- **Controlled environment** — sandbox APNs, sandbox backend endpoints, ephemeral UserDefaults suite, test-only Keychain access group, in-memory CoreData store only when the real store is under validation elsewhere.
- **Observable execution** — `os.Logger` subsystems enabled at `.debug` level, signposts for timing, full stdout capture.
- **Known-good inputs** — a fixed set of representative cases with expected outputs committed alongside the shakedown target.
- **No optimization during shakedown** — do not tune `URLSessionConfiguration`, do not adjust Swift concurrency cooperative thread pool, do not enable release optimization variants. Log it, move on.
- **No force unwraps** — shakedown code uses `guard let`, `if let`, or `throws`. Force unwrap is an **automatic shakedown code review failure**.
- No implicitly unwrapped optionals in shakedown data flow.

### Execution Order

1. Confirm preflight passes — `swift build`, SwiftLint, `SwiftFormat --lint`, entitlement check.
2. Initialize the controlled environment — sandbox URLs, test Keychain access group, ephemeral UserDefaults suite.
3. Compose the production DI graph pointed at the controlled environment.
4. Execute the simplest end-to-end happy path as a single `Task`.
5. Decode response bodies into `Codable` types and verify structural correctness.
6. Check for leaks — no orphaned `Task`s, `AnyCancellable` storage intact, no unexpected objects in the heap (use weak references to detect deallocation).
7. Increase complexity — add concurrent requests via `TaskGroup`, then push registration, then background task submission.
8. Record observations — `os.Logger` output, signpost timings, response bodies.
9. Classify results.

### Result Classification

| Outcome | Meaning |
|:--------|:--------|
| `pass` | Target composes and operates correctly end-to-end — proceed to XCTest, Instruments, or TestFlight |
| `fail-blocking` | Integration fault prevents correct operation — fix and re-run from step 1 |
| `fail-nonblocking` | Issue does not prevent operation but requires attention — log to tracker with reproduction context |
| `inconclusive` | Environment or input limitation prevented validation of a critical path — adjust and re-run the specific validation |

### Required Artifacts

Stored under the app's **Application Support directory** or a project-local scratch path — **never `NSTemporaryDirectory`, never `/tmp`**:

- Execution log — full `os.Logger` output with subsystem/category filters, signpost timings.
- Result summary — classification per validation category as machine-readable JSON via `Codable`.
- Issue list — every anomaly with classification and reproduction context.
- Environment snapshot — Swift version, Xcode version, iOS/macOS version, bundle version, entitlements list, resolved `Package.resolved` hash, config values with secrets redacted.

### Anti-Patterns

- Skipping shakedown after an actor isolation or async signature change.
- Treating shakedown as an XCTest suite with dozens of assertions.
- Running shakedown against `URLProtocol` stubs or Mockingbird doubles instead of real backends.
- Optimizing `URLSessionConfiguration`, decoder strategies, or CoreData batch sizes during shakedown.
- Running shakedown without capturing `os.Logger` output.
- Force unwrapping Optionals, using `try!`, or implicitly unwrapped optionals in shakedown code paths.
- Writing shakedown artifacts to `NSTemporaryDirectory()`, `/tmp`, or any system temp directory.

### Reference Server Startup Harness

```swift
import Foundation
import OSLog

/// Classification for a single shakedown validation area.
enum ShakedownOutcome: String, Codable, Sendable {
    case pass
    case failBlocking
    case failNonBlocking
    case inconclusive
}

/// One observation recorded by the shakedown runner.
struct ShakedownObservation: Codable, Sendable {
    let category: String
    let outcome: ShakedownOutcome
    let detail: String
    let durationMillis: Int
}

/// Runs the startup shakedown phase against real backends before the event loop accepts traffic.
actor ShakedownRunner {
    private let logger = Logger(subsystem: "com.example.app", category: "shakedown")
    private let session: URLSession
    private let sandboxEndpoint: URL
    private let artifactsDirectory: URL

    init(session: URLSession, sandboxEndpoint: URL, artifactsDirectory: URL) {
        self.session = session
        self.sandboxEndpoint = sandboxEndpoint
        self.artifactsDirectory = artifactsDirectory
    }

    /// Execute the full shakedown sequence. Throws on fail-blocking, records artifacts otherwise.
    func run() async throws {
        try FileManager.default.createDirectory(at: artifactsDirectory, withIntermediateDirectories: true)
        var observations: [ShakedownObservation] = []
        observations.append(await validateReachability())
        observations.append(await validateDecoding())
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        let summary = try encoder.encode(observations)
        let summaryURL = artifactsDirectory.appendingPathComponent("shakedown-summary.json")
        try summary.write(to: summaryURL, options: .atomic)
        logger.info("Shakedown summary written to \(summaryURL.path, privacy: .public)")
        if observations.contains(where: { $0.outcome == .failBlocking }) {
            throw ShakedownError.blocking
        }
    }

    private func validateReachability() async -> ShakedownObservation {
        let started = DispatchTime.now()
        do {
            let (_, response) = try await session.data(from: sandboxEndpoint)
            guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                return observation(category: "reachability", outcome: .failBlocking, detail: "non-2xx", started: started)
            }
            return observation(category: "reachability", outcome: .pass, detail: "sandbox reachable", started: started)
        } catch {
            return observation(category: "reachability", outcome: .failBlocking, detail: "\(error)", started: started)
        }
    }

    private func validateDecoding() async -> ShakedownObservation {
        let started = DispatchTime.now()
        struct Probe: Decodable { let id: String }
        do {
            let (data, _) = try await session.data(from: sandboxEndpoint.appendingPathComponent("probe"))
            let probe = try JSONDecoder().decode(Probe.self, from: data)
            guard !probe.id.isEmpty else {
                return observation(category: "data-flow", outcome: .failBlocking, detail: "empty id", started: started)
            }
            return observation(category: "data-flow", outcome: .pass, detail: "decoded probe \(probe.id)", started: started)
        } catch {
            return observation(category: "data-flow", outcome: .failBlocking, detail: "\(error)", started: started)
        }
    }

    private func observation(category: String, outcome: ShakedownOutcome, detail: String, started: DispatchTime) -> ShakedownObservation {
        let elapsed = Int((DispatchTime.now().uptimeNanoseconds - started.uptimeNanoseconds) / 1_000_000)
        return ShakedownObservation(category: category, outcome: outcome, detail: detail, durationMillis: elapsed)
    }
}

enum ShakedownError: Error {
    case blocking
}
```

---
[Back to Overview](./OVERVIEW.md)

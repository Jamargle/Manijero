---
name: clean-code-solid-architecture
description: Guide for writing, reviewing, and refactoring code following SOLID principles, Clean Code best practices, and Clean Architecture with MVVM or MVI in the presentation layer. Use this skill whenever the user asks to create, modify, review, or refactor any code - classes, functions, modules, features, use cases, repositories, ViewModels, screens, services, or project structure - even if they do not mention SOLID, clean code, or architecture explicitly. Also use it when deciding where code should live, how to split responsibilities, how to name things, how to structure dependencies, or how to make code testable.
---

# Clean Code, SOLID & Clean Architecture (MVVM)

This skill guides you to produce code that is easy to read, easy to change, and easy to test. Apply it to every piece of code you write or review in this codebase.

The goal is **maintainability with pragmatism**. Principles exist to reduce the cost of change, not to add ceremony. If applying a pattern makes a small problem more complicated, do not apply it. See "Pragmatism rules" below.

---

## Workflow

Follow these steps for any code task:

1. **Understand the request.** Identify the feature, its inputs, outputs, and business rules. If a requirement is ambiguous and affects the design, ask before coding.
2. **Locate the layer.** Decide which layer each piece of code belongs to (see "Architecture layers"). Never write code before knowing where it lives.
3. **Define contracts first.** Write the interfaces and data models that cross layer boundaries, then the implementations.
4. **Write the smallest correct design.** Start simple. Introduce abstractions only where a real boundary, a real variation, or a testing need exists.
5. **Implement with clean code rules** (naming, small functions, explicit error handling).
6. **Self-review** with the checklist at the end before delivering.
7. **Explain deviations.** If you break a rule on purpose, state why in a short comment or in your answer.

When modifying existing code, **follow the conventions already in the codebase** unless they contradict this skill in a harmful way. Prefer incremental refactoring over rewrites, and never mix a large refactor with a functional change unless asked.

---

## Architecture layers (Clean Architecture + MVVM)

Dependencies point **inward only**. Inner layers know nothing about outer layers.

```
Presentation (UI + ViewModel)  ──►  Domain  ◄──  Data (repositories impl, data sources)
                                      ▲
                                 (pure business logic,
                                  no framework imports)
```

| Layer | Contains | May depend on | Must NOT contain |
|---|---|---|---|
| **Domain** | Entities, value objects, use cases, repository **interfaces**, domain errors | Nothing (pure language + stdlib) | UI, DB, network, serialization annotations, framework types |
| **Data** | Repository **implementations**, remote/local data sources, DTOs, mappers | Domain | UI code, business rules, ViewModel references |
| **Presentation** | UI (screens/views), ViewModels, UI state, UI events, UI mappers | Domain | Direct data-source access, business rules, DTOs |
| **Composition root / DI** | Wiring of implementations to interfaces | All layers | Business logic |

### Domain layer
- Entities and value objects model the business concepts and enforce their own invariants.
- **Use cases** (interactors) hold one application-specific business operation each (`ApproveOrderUseCase`, `CalculateTotalCostUseCase`). Keep them small, single-purpose, and named after the action.
- **Repository interfaces** live here, expressed in domain terms. The domain decides what it needs; the data layer adapts to it (Dependency Inversion).
- Return domain errors or a result type for expected failures. Do not leak framework exceptions.
- Skip a use case when it would only forward a call to a repository with zero logic and the feature is trivial. A ViewModel may call the repository interface directly in that case, but be consistent within a feature.

### Data layer
- Implements domain repository interfaces.
- Owns DTOs (network/DB models) and **mappers** DTO ↔ domain. DTOs never leave this layer.
- Decides caching, offline strategy, and data-source orchestration. The domain does not know where data comes from.
- Translate low-level exceptions (timeouts, HTTP codes, SQL errors) into domain errors at this boundary.

### Presentation layer (MVVM)
- **View**: renders state and forwards user events. It contains no business logic and no data fetching. It should be as passive as possible.
- **ViewModel**: holds UI state, handles UI events, calls use cases, and maps domain results into UI state. It has no reference to the View or any UI/platform framework class.
- **UI State**: one immutable object per screen describing everything the View needs (loading, content, error, empty). The View renders it; it never computes it.
- **Events/Actions**: user intents modeled explicitly (`OnRefreshClicked`, `OnItemSelected`) and passed to the ViewModel through a single entry point or well-named methods.
- **One-off effects** (navigation, toasts) are exposed separately from persistent state so they are not replayed on re-render.
- State flows **down** (ViewModel → View), events flow **up** (View → ViewModel): unidirectional data flow.
- Format and map domain data for display (dates, currency, labels) in the presentation layer, not in domain or data.

### Illustrative example (pseudo-Kotlin, apply the same shape in any language)

```kotlin
// ---------- Domain ----------
data class Invoice(val id: InvoiceId, val amount: Money, val status: InvoiceStatus)

interface InvoiceRepository {
    suspend fun getInvoices(): Result<List<Invoice>, DomainError>
}

class GetPendingInvoicesUseCase(private val repository: InvoiceRepository) {
    suspend operator fun invoke(): Result<List<Invoice>, DomainError> =
        repository.getInvoices().map { list -> list.filter { it.status == InvoiceStatus.Pending } }
}

// ---------- Data ----------
class InvoiceRepositoryImpl(
    private val remote: InvoiceRemoteDataSource,
    private val mapper: InvoiceDtoMapper,
) : InvoiceRepository {
    override suspend fun getInvoices(): Result<List<Invoice>, DomainError> =
        remote.fetchInvoices()
            .map { dtos -> dtos.map(mapper::toDomain) }
            .mapError { it.toDomainError() }
}

// ---------- Presentation ----------
data class InvoicesUiState(
    val isLoading: Boolean = false,
    val items: List<InvoiceItemUi> = emptyList(),
    val errorMessage: String? = null,
)

class InvoicesViewModel(
    private val getPendingInvoices: GetPendingInvoicesUseCase,
    private val uiMapper: InvoiceUiMapper,
) : ViewModel() {
    private val _state = MutableStateFlow(InvoicesUiState(isLoading = true))
    val state: StateFlow<InvoicesUiState> = _state.asStateFlow()

    fun onRefresh() { /* launch, call use case, map result to _state */ }
}
```

---

## SOLID principles

For each principle: the rule, why it matters, and how to apply it.

### S - Single Responsibility Principle
**A module should have one reason to change.** Group code by the actor or concern that causes it to change, not by technical similarity.
- A class that validates, persists, formats, and sends notifications has four reasons to change. Split it.
- Smell: names containing "And", "Manager", "Helper", "Utils", "Processor" without a precise meaning; classes with many unrelated dependencies; files that grow past a few hundred lines.
- A ViewModel orchestrates UI state; it does not contain business rules (use cases/entities do) and does not do I/O (repositories do).

### O - Open/Closed Principle
**Extend behavior by adding code, not by editing stable code.**
- When you see `if/else` or `when` chains on a type that keeps growing, introduce polymorphism (strategy, sealed hierarchies with behavior, or a registry of handlers).
- Do this when variation is **real or already repeated** (two or more cases that will clearly keep growing), not preemptively for hypothetical futures.

### L - Liskov Substitution Principle
**Any implementation must be usable wherever its interface is expected, without surprises.**
- Implementations must honor the contract: same preconditions or weaker, same postconditions or stronger, same error semantics.
- Smell: an override that throws "not supported", returns null where the contract promises a value, or requires callers to check the concrete type (`is`, `instanceof`, casts).
- If a subtype cannot honor the contract, the hierarchy is wrong. Prefer composition or a narrower interface.

### I - Interface Segregation Principle
**Clients should not depend on methods they do not use.**
- Prefer several small, role-focused interfaces over one large one (`UserReader` / `UserWriter` rather than a giant `UserService`).
- Repository interfaces should expose what the domain needs, not everything the database can do.
- Smell: implementations with empty or throwing methods; fakes in tests that must stub many unrelated methods.

### D - Dependency Inversion Principle
**High-level policy must not depend on low-level details; both depend on abstractions.**
- Domain defines interfaces; Data implements them; DI wires them.
- Inject dependencies through constructors. Do not instantiate collaborators with `new`/constructors inside business classes, and do not use global singletons or service locators inside domain or presentation logic.
- Depend on interfaces for things that cross a boundary or are volatile: network, database, file system, clock, random, external SDKs, platform APIs. Pure helpers and simple value types do not need an interface.
- Wrap third-party libraries and paid/external services behind your own interface so they can be replaced without touching business logic.

---

## Clean Code rules

### Naming
- Names reveal intent. A reader should understand what something is or does without reading its body.
- Booleans read as questions (`isExpired`, `hasPermission`)
- Use domain vocabulary consistently. One concept, one word, everywhere.
- No abbreviations, no type-encoding prefixes, no vague names (`data`, `info`, `temp`, `handle`, `process`, `manager`).

### Functions
- Do one thing, at one level of abstraction.
- Avoid boolean flag parameters that switch behavior; split into two functions or use an enum/strategy.
- Prefer early returns (guard clauses) over deep nesting. Keep nesting to two or three levels at most.

### Comments and documentation
- Prefer code that explains itself. Fix unclear code instead of commenting it.
- Write comments for **why** (business reason, non-obvious constraint, trade-off), never for **what**.
- Document public contracts: what a public API promises, its errors, and its invariants.

### Data and state
- Prefer immutability: immutable data classes, read-only collections, `val`/`final`/`const` by default.
- Make illegal states unrepresentable: use enums, sealed types, and value types instead of loose strings, magic numbers, or nullable flags.
- Replace primitives that carry meaning with value types (`Money`, `Email`, `InvoiceId`) when it prevents bugs or duplicates validation.
- Avoid `null` as a signal for control flow. Use explicit types (`Result`, `Option`, sealed states, empty collections).
- No magic numbers or strings. Extract named constants or configuration.

### Error handling
- Fail fast on programmer errors (invalid arguments, broken invariants).
- Model **expected** failures (not found, no network, validation) as explicit return types, not exceptions used for flow control.
- Never swallow exceptions silently. Handle, translate, or propagate with context.
- Translate errors at layer boundaries. Present user-friendly messages in the presentation layer only.
- Validate input at the boundary where it enters the system, and keep the domain free of invalid data.

### Structure and duplication
- Keep related code together (cohesion) and unrelated code apart (low coupling). Organize by feature first, then by layer inside the feature, unless the codebase already uses a different convention.
- Law of Demeter: talk to direct collaborators, avoid long call chains (`a.b().c().d()`).
- Prefer composition over inheritance. Use inheritance only for a true "is-a" relationship with Liskov-compliant behavior.
- Keep public surface minimal: default to the most restrictive visibility.

### Concurrency and async (when applicable)
- Keep threading decisions at the edges (ViewModel or data source), and make dispatchers/schedulers injectable for testing.
- Do not block the main/UI thread. Do not expose mutable shared state across threads.
- Tie asynchronous work to a lifecycle/scope so it is cancelled when no longer needed.

---

## Testability

Code that follows the rules above is naturally testable. Verify it:
- Domain and use cases are tested with plain unit tests.
- Prefer fakes/stubs for repository interfaces over deep mock chains. They are more readable and less brittle.
- ViewModels are tested by feeding events and asserting emitted UI state.
- Inject time, randomness, and dispatchers so tests are deterministic.
- Test behavior and contracts, not implementation details. Name tests by scenario and expected outcome.
- When asked to implement a feature, include or propose tests for domain logic and ViewModel behavior unless told otherwise.

---

## Pragmatism rules (avoid over-engineering)

Principles serve the code, not the other way around.

- **YAGNI**: do not build abstractions for needs that do not exist. A single implementation behind an interface is justified only when it marks a layer boundary, isolates an external dependency, or enables testing.
- **Rule of three**: first duplicate is tolerable, the third occurrence calls for abstraction.
- **Match ceremony to size**: a trivial CRUD screen does not need the same structure as a complex business flow. Scale the number of classes to the complexity of the problem.
- **Prototype mode**: if the user explicitly asks for a quick proof of concept, keep the layer boundaries and interfaces (they are cheap and make later growth safe) but skip secondary polish. Say what was simplified.
- **Do not refactor unrelated code** while implementing a request. Mention opportunities instead with TODO comments for later.
- If two principles conflict, prefer the one that reduces the most likely future change cost, and state the trade-off briefly.

---

## Common anti-patterns to avoid

| Anti-pattern | Why it hurts | Do instead |
|---|---|---|
| God class / God ViewModel | Many reasons to change, impossible to test | Split by responsibility; move logic to use cases |
| Business logic in the View or ViewModel | Not reusable or testable without UI | Move to domain (entities/use cases) |
| DTOs or DB entities used in UI | UI breaks when API/DB changes | Map to domain, then to UI models at the boundaries |
| Domain importing framework/library types | Domain becomes coupled to infrastructure | Keep domain pure; adapt in the data layer |
| Repository returning raw network responses | Leaks infrastructure details | Return domain models and domain errors |
| Service locator / global singletons in logic | Hidden dependencies, hard to test | Constructor injection |
| Utils/Helper dumping grounds | Low cohesion | Place behavior on the type that owns the data, or create a named, focused class |
| Boolean flag parameters | Hidden branching, unclear call sites | Separate functions or enums |
| Exceptions for normal control flow | Hidden paths, performance and clarity costs | Explicit result types |
| Premature abstraction | Complexity without benefit | Wait for real variation (rule of three) |
| Mutable shared state | Race conditions, unpredictable behavior | Immutable state, single owner, unidirectional flow |

---

## Reviewing existing code

When asked to review or refactor:
1. Identify the **most impactful** violations first (wrong layer dependency, mixed responsibilities, untestable design) before cosmetic ones.
2. Reference the principle being violated and give a concrete, minimal fix, ideally with a short before/after snippet.
3. Propose refactors in small, safe steps that keep the code working after each step.
4. Distinguish clearly between **must fix** (breaks architecture or correctness), **should fix** (maintainability), and **nice to have** (style).
5. Preserve behavior. If a refactor could change behavior, say so.

---

## Pre-delivery checklist

Before presenting code, verify:

**Architecture**
- [ ] Each class lives in the correct layer, and dependencies point inward only.
- [ ] Domain has no framework, UI, network, or persistence imports.
- [ ] DTOs and DB models do not leak outside the data layer.
- [ ] Views contain no business logic; ViewModels expose immutable UI state and receive events.
- [ ] External services and volatile dependencies are behind interfaces and injected.

**SOLID**
- [ ] Each class/function has one clear reason to change.
- [ ] No growing `if/when` chains that should be polymorphism (when variation is real).
- [ ] Implementations honor their interface contracts without surprises.
- [ ] Interfaces are small and role-focused.
- [ ] Dependencies are injected, not constructed internally.

**Clean code**
- [ ] Names are intention-revealing and use consistent domain vocabulary.
- [ ] Functions are small, do one thing, and have few parameters.
- [ ] No magic values, dead code, or commented-out code.
- [ ] Errors are explicit, translated at boundaries, and never silently swallowed.
- [ ] Data is immutable by default, and illegal states are not representable.

**Pragmatism and tests**
- [ ] No abstraction exists without a boundary, real variation, or testing need.
- [ ] Domain logic and ViewModel behavior are testable (and tests are included or proposed).
- [ ] Any intentional rule-breaking is explained briefly.

# Recurring PR review nits

Source of truth for `prepare-for-review`. Each item is something that has shown
up repeatedly on Shine/Playon .NET PRs (human or AI reviewer).

Format for new items:

```markdown
## `id` — Title

- **Detect:** ...
- **Fix:** ...
- **Mode:** auto-fix | ask-before-redesign
```

`auto-fix`: change the code in pass 2.
`ask-before-redesign`: report under **Skipped** and wait; do not delete or redesign.

---

## `comments` — Unrequested comments

- **Detect:** New or edited comments that narrate implementation (`// call the service`,
  `// return result`), XML docs (`/// <summary>`), or comments on interfaces /
  abstract members that have no implementation.
- **Fix:** Delete them. Keep a comment if it contains an external link (http/https URL),
  the user asked for docs, the file already uses a consistent doc convention, or a
  short comment is required to explain non-obvious intent, a trade-off, or a
  constraint the code cannot convey. Do not strip the surrounding comment block just
  to drop narration when a link is in it.
- **Mode:** auto-fix

---

## `names` — Comment instead of a name

- **Detect:** Comments that exist only to explain what a variable, method, or
  batch is (`// batch1: resolve scores`). Reviewers ask to name the thing
  instead.
- **Fix:** Rename the identifier so the comment is unnecessary, then remove the
  comment. Do not invent a large rename across unchanged APIs.
- **Mode:** auto-fix

---

## `mapping` — Manual DTO / model conversion

- **Detect:** Hand-written property-by-property copies between entities, DTOs,
  request, and response types — including private helpers like `ToResult` /
  `ToDto` in a domain service. A short “local projection” is still a mapping.
- **Fix:** Map via an existing AutoMapper profile, or add a profile next to the
  project's existing mapping profiles (a Domain profile if the conversion lives
  in Domain). Inject `IMapper` where the copy sits. Do not skip because the
  copy is short, or because that project did not already reference AutoMapper.
  Do not introduce a new mapper library.
- **Mode:** auto-fix

---

## `validation` — Endpoints without FluentValidation / ObjectId guards

- **Detect:**
  1. New or changed REST or GraphQL operations that accept input without a
     request/input DTO + FluentValidation validator — including **query-string
     and combined query/route** parameters (filters, limits, currency, etc.),
     not only a JSON body. User rule: endpoints always have validation this way.
     Exception: a lone ObjectId path/query id uses `Guard.Against.NotObjectId`
     in the method (see point 2); do not wrap that in a DTO.
  2. New or changed methods that take a string id in the **signature** (path, query,
     GraphQL argument, or a service parameter) that is later used as a Mongo ObjectId,
     and that id is **not** already covered by an input DTO FluentValidation rule
     (`ObjectIdValidator` or equivalent).
- **Fix:**
  - Add (or complete) the input DTO and a FluentValidation validator, and
    wire it the same way neighbouring endpoints do. Bind query fields with
    `[FromQuery]` on the DTO (same pattern as `WalletBaseRequestDto` for route).
    Validate input shape and obvious field rules here; do not duplicate domain
    invariants that already throw from the service.
  - For a signature id that the input validator does not cover, add
    `Guard.Against.NotObjectId(id)` at the start of the method (Ardalis + the
    project's `NotObjectId` extension, same as neighbouring GraphQL methods).
    Do **not** add a Guard when FluentValidation already validates that id on the DTO.
- **Mode:** auto-fix

---

## `cancellation` — CancellationToken last and used down the chain

- **Detect:** New or edited methods (services, repositories, GraphQL resolvers,
  controllers, and the private helpers they call) that:
  1. Are `async` (or call async APIs) and omit `CancellationToken`, or
  2. Take a `CancellationToken` but do not pass it to downstream async calls, or
  3. Take a `CancellationToken` that is not the **last** parameter in the
     signature.
- **Fix:**
  - Add `CancellationToken cancellationToken` (or the name already used in that
    file) when it is missing.
  - Pass that same token into every downstream async call that accepts one
    (repository, client, `Task.Delay`, Mongo, HTTP, etc.).
  - Reorder the signature so `CancellationToken` is always the last parameter —
    after session handles, options, and other arguments.
  - Do not add a token to a method that has no async work and cannot honor it.
- **Mode:** auto-fix

---

## `utc` — Local clock instead of UTC

- **Detect:** `DateTime.Now`, `DateTimeOffset.Now`, or local timestamps written
  to storage, events, or API payloads. This codebase uses UTC.
- **Fix:** `DateTime.UtcNow` / `DateTimeOffset.UtcNow`, or the project's clock
  abstraction if one is already injected.
- **Mode:** auto-fix

---

## `dead-code` — Leftovers from the change

- **Detect:** Unused usings, unused members, unused types, commented-out code,
  `#if false` blocks, leftover names from a removed design (e.g. Redis attributes
  on a type that is no longer stored in Redis), TODOs that are not ticket IDs.
- **Fix:** Do not delete in pass 2. Unused members and types often exist because
  the API has not been added yet, or the API shape is still undecided. Report
  each hit under **Skipped** with file and symbol so the user can keep or drop
  it. Only remove after they say to.
- **Mode:** ask-before-redesign

---

## `errors` — Misleading exception or error text

- **Detect:** Throw/return messages that describe the opposite or a different
  failure than the condition (e.g. "batch is missing payouts" when payout
  documents are missing for IDs the batch still lists).
- **Fix:** Rewrite the message (and include identifying ids when that is the
  local pattern) so it matches the actual condition. Do not change error types
  or HTTP/GraphQL codes unless they are clearly wrong for that condition.
- **Mode:** auto-fix

---

## `round-trip` — Extra read before the write

- **Detect:** Happy path does `GetX` then `UpdateX` (or two repository calls)
  when the update/filter can enforce the pre-condition in one operation, or
  when the second call already loads what the first loaded.
- **Fix:** Collapse to the single repository operation used elsewhere in the
  project, if that is a mechanical change. If it requires a new repository
  method or a behaviour change, **Mode becomes ask-before-redesign** for this
  hit — list it under Skipped with one sentence why.
- **Mode:** auto-fix when collapsing is local and equivalent; otherwise
  ask-before-redesign

---

## `duplicate-write` — Second store of the same fields

- **Detect:** A new collection, table, queue, or DTO that copies fields already
  on the source document so a later job can find work. Reviewers (and reviewer
  AIs) flag this as two sources of truth.
- **Fix:** Do not redesign or delete in pass 2. Report under **Skipped**. If it
  looks unused, treat it as `dead-code` (API may still be coming). The opinion
  pass can propose querying the source document instead.
- **Mode:** ask-before-redesign

---

## `x86` — Solution x86 configurations

- **Detect:** `.sln` `SolutionConfigurationPlatforms` or `ProjectConfigurationPlatforms` entries for `x86` (e.g. `Debug|x86`, `Release|x86`), or a changed `.csproj` that lists `x86` in `<Platforms>` / `<PlatformTarget>`. These usually appear when a project is added in the IDE.
- **Fix:** Remove every x86 solution configuration and its per-project mappings. Leave `Debug|Any CPU` and `Release|Any CPU`. If a csproj in the diff added `x86` to `<Platforms>` or set `<PlatformTarget>x86</PlatformTarget>`, drop that too so the project matches AnyCPU-only neighbours.
- **Mode:** auto-fix

---

## `one-class` — One class per file

- **Detect:** A new or edited file with more than one top-level type (`class`, `record`, `interface`, `struct`, `enum`). Nested types and additional `partial` files of the **same** type are fine.
- **Fix:** Move each extra top-level type into its own file named after that type, same namespace and folder as neighbouring types. Do not split generated files.
- **Mode:** auto-fix

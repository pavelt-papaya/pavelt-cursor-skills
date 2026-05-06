---
name: shine-update-nugets
description: >-
  Restores .NET packages, reports outdated NuGet versions from the solution,
  and proposes safe version bumps for non–Hot-Chocolate dependencies. Does not
  change Hot Chocolate / ChilliCream-related package versions at all (no patch,
  minor, or major bumps). Use when the user asks to update NuGets, check package
  updates, bump dependencies, refresh NuGet versions, or Shine-related .NET
  dependency updates.
---

# Shine: Update NuGets (.NET)

## Goals

1. Restore packages so the graph is current and buildable.
2. List outdated packages and what newer versions exist.
3. Update **non–ChilliCream** packages toward current stable releases as the user requests.
4. **Do not** change ChilliCream / Hot Chocolate ecosystem package versions **at all**—not patch, not minor, not major (even if newer 13.x exists). Report them as informational only if useful.

## ChilliCream ecosystem (do not modify versions)

Treat any package whose **id** matches these patterns as Hot Chocolate–related—**never bump, suggest, or edit** their versions:

- `HotChocolate.*`
- `StrawberryShake.*` (includes “Strawberry” client/tooling packages)
- `GreenDonut*`
- `CookieCrumble*`
- `ChilliCream.*` (if present)

If unsure whether a package is ChilliCream, check the package page on nuget.org (publisher / dependencies).

**Rule:** Leave these packages exactly as pinned in the repo. You may mention in the report that newer versions exist on NuGet, but state clearly that they were **not** updated by design.

## Workflow

### 1. Restore

From the repository root (or solution directory):

```bash
dotnet restore
```

Fix any restore errors before continuing.

### 2. Outdated packages

Prefer solution-wide listing when a `.sln` exists:

```bash
dotnet list <path-to.sln> package --outdated
```

Optional (more noise, fuller picture):

```bash
dotnet list <path-to.sln> package --outdated --include-transitive
```

If there is no solution file, run the same command per `.csproj` or discover projects with `find`/`glob`.

### 3. Interpret results

- Split the table into:
  - **ChilliCream / Hot Chocolate**: ids matching the patterns above → **no version changes**. Optionally list “newer on NuGet” for awareness only.
  - **Other**: safe to plan upgrades per user instruction (respect any other repo pins, e.g. `InfraVersion`, internal `Shine.*` packages).

### 4. Apply version changes

- If the repo uses **Central Package Management** (`Directory.Packages.props`, `ManagePackageVersionsCentrally`), edit **`PackageVersion`** entries there—not scattered `PackageReference` versions unless the project does not use CPM.
- **Do not** edit `PackageVersion` lines or MSBuild properties (e.g. `HotChocolateVersion`) for any ChilliCream / Hot Chocolate–related package.
- After edits: `dotnet restore` again, then `dotnet build` (or test) to verify.

### 5. Report to the user

Summarize:

- What was restored / built.
- Outdated list grouped into **ChilliCream / Hot Chocolate (unchanged)** vs **other** (what was updated or proposed).
- Exact file edits (paths + version changes) or a short table.

## Do not

- Change **any** Hot Chocolate / ChilliCream-related package version (including `HotChocolateVersion` and every matching `PackageVersion`).
- Assume “Strawberry*” packages are safe to bump—they are the same vendor; **leave them untouched** like `HotChocolate.*`.
- Commit or push unless the user explicitly asks (follow repo / user rules).

---
name: prepare-for-review
description: >-
  Prepares current branch changes for pull-request review: prints the recurring
  review-nit checklist, scans the diff for those issues, lists planned fixes,
  then applies them. Use
  immediately and automatically when the user says "prepare for review",
  "prep for review", "prepare-for-review", "pepare-for-review", "ready for PR",
  "pre-review", "clean up for review", "fix review nits", or asks to catch
  repeating PR comments before opening or updating a pull request. If they then
  ask for an additional opinion, extra AI-reviewer findings, or what a reviewer
  AI would flag, report those without applying them until they decide.
---

# Prepare for Review

Run this before a PR so repeating review nits are gone, and so an AI reviewer
on the other side has less to flag.

Do not ask for clarification. Do not commit or push. Do not run Bugbot or a
full architecture redesign unless the user asks.

Do not build, restore, or test the solution (`dotnet build`, `dotnet test`,
`dotnet restore`, or equivalent). After pass 2, tell the user to build locally
to verify the changes.

The issue catalog is [common-issues.md](common-issues.md). Keep that file the
source of truth. When the user pastes a new repeating PR comment and wants it
remembered, append a new item there in the same format.

## Triggers

| User says | Behaviour |
|---|---|
| `prepare for review` / `prep for review` / `prepare-for-review` / `pepare-for-review` | Full pass: print checklist → analyze → list planned changes → fix |
| `ready for PR` / `pre-review` / `clean up for review` / `fix review nits` | Same |
| `additional opinion` / `what else would AI flag` / `AI reviewer` / `reviewer opinion` | Opinion pass only (no edits unless they then ask to apply) |

If they invoke the skill and later ask for additional opinion in the same chat,
run the opinion pass on the **post-fix** diff.

---

## Scope of changes

Analyze the current workspace repo:

1. Merge-base of `HEAD` with the default base branch (`main`, else `master`).
2. Include committed, staged, and unstaged changes (`git diff <merge-base>` plus untracked files that belong to the feature).
3. Skip generated lockfiles, `bin/`, `obj/`, and vendor output.

If there is no diff, say so in one sentence and stop.

---

## Pass 1 — Print the checklist (before any analysis)

In the first user-visible reply, print the catalog as a compact list. Use the
**id** and **title** from [common-issues.md](common-issues.md), nothing else:

```markdown
Preparing for review. Checking:

1. `comments` — Unrequested comments
2. `names` — Comment instead of a name
...
```

Then start analysis. Do not skip this print.

---

## Pass 2 — Analyze, list, then fix

For every item in [common-issues.md](common-issues.md):

1. Search the diff (and nearby new files) for that issue.
2. If found, record a planned change. Do **not** edit yet.
3. Do not "improve" unrelated code. Do not apply items from the opinion pass.

### Planned changes (mandatory, before any edit)

After analysis and before the first file edit, print every planned fix as
one line. Use catalog **id** as `type_of_issue`. Include a line range when
the diff or file read gives you one; otherwise the file path only.

```markdown
Planned changes:

- `comments` : `src/Foo.cs:12-18` : remove XML docs on `Bar`
- `mapping` : `src/BarService.cs:40-47` : replace manual map with AutoMapper
```

Format each line exactly as:

`type_of_issue` : `file:start-end` (or `file`) : how you are going to change it

If nothing to fix, print `Planned changes: none` and skip to the report.

Items with **Mode** `confirm` are not edits yet. Before you change them, ask
with the choices in that catalog item. For `release-versions`, the three
choices are: make it a release version, keep as is, or use a version the user
types in the custom answer field. Apply only that answer. **Keep as is** goes
under **Skipped**. Do not strip a suffix while you wait.

Then apply the listed fixes, including the confirmed choice. Do not apply
anything that was not listed.

After fixes, re-scan once for the same catalog so a fix did not introduce
another catalog item (e.g. a rename that left a narration comment). If the
re-scan finds a new catalog hit, list it in the same format and fix it;
do not silently edit.

### Report

End with a short report:

```markdown
## Review prep

**Fixed**
- `comments` — removed XML docs from `Foo.cs`
- `mapping` — replaced manual map in `BarService` with AutoMapper

**Already clean**
- `validation`, `cancellation`, ...

**Skipped**
- `dead-code` — unused `FooHelper`; may be waiting on API — not deleted
- `duplicate-write` — looks like an intentional design; not auto-changed
```

`Skipped` is for catalog items marked **ask-before-redesign**, or for hits
that would change behaviour beyond the nit. Do not delete unused members or
types without the user confirming — they may be waiting on an API.

After the report, one short line: ask the user to build locally. Do not run
the build yourself.

---

## Pass 3 — Additional opinion (only on request)

Run this only when the user asks for additional opinion / AI-reviewer findings.

Role: a strict PR reviewer AI (Copilot / CodeRabbit style) looking at the
current diff. Goal: surface what they would comment so the user can decide.

Rules:

- Do **not** edit code.
- Do **not** repeat catalog items already fixed or reported in pass 2.
- Be concrete: `file:line`, what is wrong, what a reviewer would say, suggested
  fix in one or two sentences.
- Sort by severity: behaviour/correctness → security → missing tests → design →
  style.
- Skip nits already covered by the catalog even if still present and skipped.
- End with: ask which findings (if any) to apply. Wait for that before changing
  code.

Typical extra findings (examples, not a checklist to force):

- Extra collection/table that copies fields already on the source document
- Two queries on the happy path where one write would do
- Race / missing transaction / missing idempotency key
- Options/DI: constructed settings object instead of `Action<T>` / `IOptions<T>`
- Error type or message that does not match the actual failure
- Public API without tests in a repo that already tests that layer
- Leftover names from a removed design (`Request`, `Queue`, …) that mislead

Format:

```markdown
## Additional opinion (not applied)

| Sev | Location | Reviewer would say |
|-----|----------|--------------------|
| high | `src/Foo.cs:40` | ... |
```

---

## Maintaining the catalog

When the user says a PR comment keeps coming back, or pastes one and says to
remember it:

1. Add a new item to [common-issues.md](common-issues.md) with a short `id`,
   title, detect, fix, and auto-fix vs ask-before-redesign.
2. Confirm in one sentence that it was added.
3. Do not re-run the full pass unless they also asked to prepare for review.

---
name: clone-to-playon
description: >-
  Clones a Shine `backend-<service>-service` repo into its
  `playon-backend-<service>-service` counterpart by mirroring the source files
  and applying the infra/project/NuGet transformations needed for the playon
  edition (CI repository name prefix and per-csproj NuGet `PackageId`). Business
  logic is left untouched. Use this skill immediately and automatically when the
  user says "clone to playon", "playon clone <service>", "create playon repo for
  <service>", "playon-ify <service>", or "playonize <service>". Do not ask for
  clarification, just execute the workflow.
---

# Clone to Playon

Mirrors a Shine backend service into its `playon-*` counterpart and applies the
small set of infra/project/NuGet edits that are part of every clone. Business
logic edits are intentionally out of scope.

## Triggers

| Command | Behaviour |
|---|---|
| `clone <service> to playon` | Resolve OLD/NEW under `~/Documents/WORK`, mirror + transform |
| `playon clone <service>` | Same as above |
| `create playon repo for <service>` | Same as above |
| `playon-ify <service>` / `playonize <service>` | Same as above |

`<service>` is lowercase, no prefix/suffix, e.g. `games`, `tournaments`,
`feedmatching`.

## Preconditions

The user is expected to have already created the empty playon repo on GitHub and
cloned it locally. The skill does NOT create the GitHub repo and does NOT touch
git remotes.

By convention, the working layout is:

```
~/Documents/WORK/
├── backend-<service>-service/             ← OLD (source, untouched)
└── playon-backend-<service>-service/      ← NEW (target, must already be a git clone)
```

Validate before running:

- `backend-<service>-service/` exists.
- `playon-backend-<service>-service/` exists and is a git repo.
- `playon-backend-<service>-service/`'s `origin` remote starts with
  `git@github.com:papaya-shine/playon-` (warn, don't abort, if it doesn't).

## Workflow

Run the bundled Python script - it implements every step idempotently:

```bash
python3 ~/.cursor/skills/clone-to-playon/clone.py <service>
```

If the user's repos live somewhere other than `~/Documents/WORK`, pass
`--workdir`:

```bash
python3 ~/.cursor/skills/clone-to-playon/clone.py <service> --workdir /custom/path
```

### What the script does

1. **Mirror** - `rsync -a --delete --exclude=.git --exclude=bin --exclude=obj OLD/ NEW/`.
   Preserves NEW's `.git`. Removes any stray files in NEW that don't exist in OLD.

2. **Patch CI workflow** - in `.github/workflows/ci.yml`, prefix the
   `repository_name:` value with `playon-` if not already prefixed.
   Example: `repository_name: games-service` → `repository_name: playon-games-service`.
   This single value is what the reusable build pipeline
   (`papaya-shine/devops-ci-pipelines/.github/workflows/build.yaml@main`) uses
   to **also** name the ECR Docker image (e.g.
   `…/playon-games-service:<tag>`). The Dockerfile's base images and .NET
   assembly entry point stay the same; only its solution-name reference is
   rewritten by step 4 below.

3. **Rename solution file + update references** - rename the repo-root
   `Shine.<rest>.sln` to `Shine.Playon.<rest>.sln`, then walk the repo and
   replace any literal occurrence of the old `.sln` filename in text files
   (Dockerfile, scripts, workflows, etc.) with the new one. Skips `.git`,
   `bin`, `obj`, and `node_modules`, and never rewrites the `.sln` file
   itself. Example: `Shine.Games.sln` → `Shine.Playon.Games.sln`, and
   `dotnet publish "Shine.Games.sln"` in the Dockerfile becomes
   `dotnet publish "Shine.Playon.Games.sln"`. Idempotent: a no-op if a
   `Shine.Playon.*.sln` already exists and no `Shine.*.sln` does.

4. **Patch packable .csproj files** - for every `.csproj` containing
   `<GeneratePackageOnBuild>true</GeneratePackageOnBuild>`, inject an explicit
   `<PackageId>Shine.Playon.<rest>` derived from the project filename pattern
   `Shine.<rest>.csproj`. Skips files that already have a `<PackageId>` element.
   Example: `Shine.Games.Messages.csproj` →
   `<PackageId>Shine.Playon.Games.Messages</PackageId>` immediately under
   `<GeneratePackageOnBuild>`.

5. **Remove README.md** - the playon repo gets its own (or none) later.

6. **Print `git status`** of the new repo for the user's review.

The script is idempotent: re-running it on an already-transformed target is
safe. It does NOT stage, commit, or push.

## After the script runs

- Read out the printed `git status` summary to the user.
- Tell the user the clone is staged on disk only; they should review with
  `git diff` and commit/push themselves (per the no-auto-commit rule).
- If the script printed any `WARNING:` lines (unexpected git remote, dirty
  working tree), surface them prominently.

## Edge cases

- **Service name with hyphens** (e.g. `feedmatching-datamanager`): pass it
  as-is; the script tolerates `[a-z][a-z0-9-]*`.
- **OLD or NEW missing**: script aborts with a clear `ERROR:` line. Tell the
  user which repo is missing.
- **NEW already has uncommitted changes**: script prints a `WARNING:` and
  proceeds (rsync will overwrite). Surface this to the user before continuing
  if you have any doubt.
- **No packable .csproj found**: script reports it; not necessarily an error
  (the service may not publish any NuGet packages).
- **A .csproj already has `<PackageId>`**: skipped intentionally - assume a
  human set it deliberately and don't touch it.

## Out of scope (do NOT change manually as part of the clone)

These differ between OLD and NEW only because of post-clone business work, and
the skill must not touch them:

- `.cs` source files, mapping profiles, controllers, validators
- `migrations/content/*.js` (index changes happen as part of feature work)
- `src/*.Host/appsettings.json`, `launchSettings.json`
- `Directory.Packages.props`, `.gitignore`, `.config/` (byte-identical between
  OLD and NEW in reference clone)
- `Dockerfile` and `*.sln` are touched **only** by the solution-rename step
  (filename change + `dotnet publish "<sln>"` rewrite); their other contents
  are left as-is.

Also out of scope (different repo entirely):

- **Helm values in `devops-k8s-resources`** - the deployed image repository
  (`image.repository: …/playon-<service>-service`) and any environment
  variables for the new service live in `helm-values/<env>/<service>.yaml` of
  the `devops-k8s-resources` repo. Those are a deploy-side concern (handled
  by the separate `deploy-service` skill), not part of cloning the source repo.

## Extending

When future clones reveal new infra/project transformations (additional
workflow files, helm references, dependabot, etc.), add a new step function in
`clone.py` and call it from `main()`. Keep every step idempotent so the script
remains safe to re-run.

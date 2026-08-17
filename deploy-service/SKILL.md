---
name: deploy-service
description: Deploys a service by updating the image.tag in Helm values YAML files inside one of two CI repos (devops-k8s-resources for Shine, playon-do-argo for Playon), creating a feature branch, committing, and pushing. The target CI repo is chosen automatically from the source project's root folder name (playon-* prefix → Playon, otherwise Shine). Use this skill immediately and automatically whenever the user writes any message starting with "deploy" followed by a version number or a service name and version — for example "deploy 1.2.3", "deploy 1.2.3 to dev", "deploy 1.2.3 to stage", "deploy 1.2.3 to prod", "deploy users 1.2.3", "deploy version 1.2.3". Do not ask for clarification, just execute the workflow.
---

# Deploy Service

## High-level flow

1. User invokes the skill from inside some source project (e.g. `playon-backend-users-service`).
2. Skill reads the **source project's root folder name** and uses it to determine:
   - The **service** (via matching `githubRepo:` in helm values).
   - The **CI repo** to deploy through (Shine vs Playon edition — see below).
3. In the chosen CI repo: checkout and update `main` to the latest, create a feature branch from that `main`, update `image.tag` for the requested env(s), commit, push.

---

## Triggers and env semantics

`to <env>` is **isolated** — it updates only that env.

| Command | Envs updated |
|---|---|
| `deploy <version>` | dev + staging |
| `deploy version <version>` | dev + staging |
| `deploy <service> <version>` | dev + staging |
| `deploy <version> to dev` | dev only |
| `deploy <version> to stage` | staging only |
| `deploy <version> to prod` | production only |
| `deploy <service> <version> to <env>` | only that env |

---

## Choosing the CI repo (Shine vs Playon)

Look at the **source project's root folder name** (or `git remote get-url origin` repo-name component).

| Source project name | Edition | CI repo path |
|---|---|---|
| starts with `playon-` (e.g. `playon-backend-users-service`) | **Playon** | `/Users/pavelt/Documents/WORK/playon-do-argo` |
| anything else (e.g. `backend-users-service`) | **Shine** | `/Users/pavelt/Documents/WORK/devops-k8s-resources` |

Throughout the rest of this document, `<CI_REPO>` refers to whichever absolute path was selected.

Both repos share the same structure:

```
helm-values/
├── dev/
├── staging/
└── production/
```

Each service has a yaml file `helm-values/<env>/<service-name>.yaml` containing:

```yaml
githubRepo: <source-project-repo-name>
image:
  tag: <version>
```

---

## IMPORTANT — running commands inside `<CI_REPO>`

The user typically invokes this skill from the **source project's workspace**. The `<CI_REPO>` lives outside that workspace, and the `working_directory` shell parameter is silently ignored when the path is outside the active workspace (unless elevated permissions are granted). So:

- **For git commands**, always use `git -C <CI_REPO> <subcommand>` instead of `cd <CI_REPO> && git ...`.
- **For file reads/grep/ls**, always use **absolute paths** (`<CI_REPO>/helm-values/...`).
- **For file edits (StrReplace, Write, Read)**, use absolute paths — this works regardless of cwd.
- If you ever do need to `cd` into `<CI_REPO>`, you must pass `required_permissions: ["all"]` on the Shell call **and** verify with `pwd` that you actually landed there before doing anything destructive.

This avoids accidentally running commands (or, worse, modifying git config) against the source project instead of the CI repo.

---

## Step 1 — Resolve service name + edition

1. Determine the source project's repo name:
   - From the source project's folder: `basename "$PWD"` of the user's invocation directory, **or**
   - `git -C <source-project-path> remote get-url origin` and extract the repo name (last path segment, strip `.git`).
2. Decide edition by prefix:
   - Starts with `playon-` → Playon → `<CI_REPO> = /Users/pavelt/Documents/WORK/playon-do-argo`
   - Otherwise → Shine → `<CI_REPO> = /Users/pavelt/Documents/WORK/devops-k8s-resources`
3. Resolve the service name (the yaml filename, which is usually a short alias like `users`, not the full repo name) by searching `<CI_REPO>/helm-values/dev/` for a matching `githubRepo:`:

   ```bash
   grep -rl "githubRepo: <source-repo-name>" <CI_REPO>/helm-values/dev/
   ```

   The matched filename without `.yaml` is the **service name** used in all subsequent steps.

4. **If the user provided an explicit service name** (e.g. `deploy users 1.2.3`), use it directly — but still derive the edition from the source project the user is in.

5. If no match is found, list `<CI_REPO>/helm-values/dev/` and ask the user to confirm.

---

## Step 2 — Checkout and update `main` to the latest

To create a branch we need to checkout and update `main` to the latest. Do this **before** creating the feature branch, even if the CI repo is currently on another branch.

Use `-C` so we don't depend on `cd`:

```bash
git -C <CI_REPO> status --short
git -C <CI_REPO> checkout main
git -C <CI_REPO> pull origin main
```

If `git status --short` shows a dirty working tree, **stop** and ask the user how to proceed. Do not stop merely because the current branch is not `main` — switch to `main` and pull latest, then continue.

---

## Step 3 — Read the current tag (for the commit message)

Determine the envs to update based on the trigger (see env semantics table).

Pick the **first** env that will be updated (priority: dev → staging → production) and read `<CI_REPO>/helm-values/<env>/<service-name>.yaml`. The current value of `image.tag` is the **old-tag** for the commit message.

If multiple envs are being updated and their current tags differ, report all tags and ask which to use as the old-tag.

---

## Step 4 — Update `image.tag` in the selected env file(s)

For each env in scope, edit `<CI_REPO>/helm-values/<env>/<service-name>.yaml` and replace **only** the `tag:` line under `image:` with the new version.

Use the `StrReplace` tool with the absolute path. The `old_string` should include enough context (e.g. the `repository:` line above) so it uniquely targets the image tag and not some other `tag:` field.

If a target env file doesn't exist (e.g. `staging/<service>.yaml` is missing), report it and ask the user whether to create it from `dev/` or skip that env.

---

## Step 5 — Create a feature branch and commit

Create the feature branch only after Step 2 has checked out `main` and updated it to the latest. Branch naming: `feature/<service-name>_<version>` (env is **not** in the branch name).

```bash
git -C <CI_REPO> checkout -b feature/<service-name>_<version>
git -C <CI_REPO> add <list of changed yaml file paths, absolute or relative to CI_REPO>
git -C <CI_REPO> commit -m "updating <service-name> from <old-tag> to <version> <env-label>"
git -C <CI_REPO> push -u origin feature/<service-name>_<version>
```

`<env-label>` in the commit message:

| Envs updated | `<env-label>` |
|---|---|
| dev only | `dev` |
| staging only | `stage` |
| dev + staging | `non prod` |
| production only | `prod` |

The push will need network access. If running sandboxed, use `required_permissions: ["full_network"]` on the Shell call.

---

## Step 6 — Confirm to the user

Report:
- **Edition** used (Shine or Playon) and `<CI_REPO>` path.
- Envs updated.
- Service name and version (old → new).
- Branch name created.
- Files changed.
- Commit message used.
- Remote push URL.

---

## Edge cases

- **Source repo cannot be detected** (not in a git repo and no folder name to derive from): Ask the user for both the service name and which edition (Shine / Playon) to target.
- **Service exists in both CI repos**: Use the edition derived from the source project's prefix. If still ambiguous, ask.
- **`<CI_REPO>` not present locally**: Report the missing path and ask the user to clone it (don't try to clone automatically).
- **`<CI_REPO>` working tree is dirty**: Report `git status` and ask before continuing. Being on a non-`main` branch is not a stop — checkout and update `main` to the latest, then create the feature branch from it.
- **Target env yaml file missing**: Report and ask whether to copy from dev or skip that env.
- **`working_directory` confusion**: If `pwd` returns a path other than the one requested (sandbox silently ignored `cd`), switch to `git -C` and absolute paths immediately.

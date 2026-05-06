---
name: deploy-service
description: Deploys a service by updating the image.tag in Helm values YAML files in the devops-k8s-resources repository, creating a feature branch, committing, and pushing to remote. Use this skill immediately and automatically whenever the user writes any message starting with "deploy" followed by a version number or a service name and version — for example "deploy 1.2.3", "deploy users 1.2.3", "deploy users 1.2.3 to prod", "deploy version 1.2.3". Do not ask for clarification, just execute the workflow.
---

# Deploy Service

## Triggers

| Command | Behaviour |
|---|---|
| `deploy [version]` | Auto-detect service from current project, update dev + staging |
| `deploy version [version]` | Same as above — auto-detect service from current project, update dev + staging |
| `deploy [service-name] [version]` | Explicit service, update dev + staging |
| `deploy [version] to prod` | Auto-detect service, update dev + staging + production |
| `deploy version [version] to prod` | Same as above — auto-detect service, update dev + staging + production |
| `deploy [service-name] [version] to prod` | Explicit service, update dev + staging + production |

---

## Project location

```
/Users/pavelt/Documents/WORK/devops-k8s-resources
```

Helm values structure:
```
helm-values/
├── dev/           ← always updated
├── staging/       ← always updated
└── production/    ← only when "to prod" is explicitly requested
```

Field to update in each file:
```yaml
image:
  tag: <version>
```

---

## Step 1 — Resolve service name

### If service name was NOT provided (e.g. `deploy 1.2.3`)

Run this from wherever the user currently is:
```bash
git remote get-url origin
```

Extract the repo name from the URL. Examples:
- `git@github.com:org/backend-users-service.git` → `backend-users-service`
- `https://github.com/org/backend-users-service` → `backend-users-service`

Then search all `helm-values/dev/*.yaml` files for a matching `githubRepo` field:
```bash
grep -rl "githubRepo: backend-users-service" /Users/pavelt/Documents/WORK/devops-k8s-resources/helm-values/dev/
```

The matched filename (without `.yaml`) is the **service name** used in all subsequent steps.

If no match is found, list `helm-values/dev/` contents and ask the user to confirm the correct service name.

### If service name WAS provided (e.g. `deploy users 1.2.3`)

Use the provided name directly. If `helm-values/dev/[service-name].yaml` does not exist, list the folder contents and ask the user to confirm.

---

## Step 2 — Sync the devops repo

```bash
cd /Users/pavelt/Documents/WORK/devops-k8s-resources
git checkout main
git pull origin main
```

If there's a dirty working tree or merge conflict, report git status and ask the user to confirm before proceeding.

---

## Step 3 — Read the current tag

Open `helm-values/dev/[service-name].yaml` and read the current value of `image.tag`. This is the **old-tag** used in the commit message.

If dev and staging tags differ, report both and ask the user which to use as the old-tag.

---

## Step 4 — Update image.tag

For **non-prod**: update `helm-values/dev/` and `helm-values/staging/`.  
For **prod**: update `helm-values/dev/`, `helm-values/staging/`, and `helm-values/production/`.

Use StrReplace to change only the `tag:` line under the `image:` key.

---

## Step 5 — Create branch and commit

```bash
git checkout -b feature/[service-name]_[version]
```

**Non-prod commit + push:**
```bash
git add helm-values/dev/[service-name].yaml helm-values/staging/[service-name].yaml
git commit -m "updating [service-name] from [old-tag] to [version] non prod"
git push -u origin feature/[service-name]_[version]
```

**Prod commit + push:**
```bash
git add helm-values/dev/[service-name].yaml helm-values/staging/[service-name].yaml helm-values/production/[service-name].yaml
git commit -m "updating [service-name] from [old-tag] to [version] prod"
git push -u origin feature/[service-name]_[version]
```

---

## Step 6 — Confirm to user

Report:
- Branch name created
- Files changed
- Commit message used
- Remote push URL

---

## Edge cases

- **Not in a git repo** (step 1): Skip auto-detection, ask user to provide the service name.
- **Multiple files match the githubRepo** (unlikely): List all matches, ask user to pick one.
- **Production file missing**: Warn user and ask how to proceed before making any changes.
- **Already on a non-main branch / dirty tree**: Report git status and ask before continuing.

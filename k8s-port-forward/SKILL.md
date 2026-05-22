---
name: k8s-port-forward
description: Port-forward a Kubernetes service pod to localhost on the Shine or Playon EKS clusters, or stop an active forward. Use immediately and automatically when the user says "port-forward", "forward", "pf", or "connect to" followed by a service name — e.g. "port-forward media", "pf identity-management", "forward media to 5200", "connect to graphql-gateway", "pf playon users", "pf playon-dev media", "forward identity-management on playon-staging". Also use when the user says "stop forwarding", "stop forward", "kill forward", or "disconnect" followed by a service name or "all". Do not ask for clarification, just execute the workflow.
---

# K8s Port-Forward

## Cluster setup

| Alias(es) | Full context name | Namespace | AWS account |
|-----------|-------------------|-----------|-------------|
| `staging` / `shine staging` / `shine-staging` | `arn:aws:eks:us-east-2:339712807733:cluster/eks-staging` | `default` | Shine (339712807733) |
| `dev` / `shine dev` / `shine-dev` | `arn:aws:eks:us-east-2:339712807733:cluster/eks-dev` | `default` | Shine (339712807733) |
| `playon-dev` / `playon dev` | `arn:aws:eks:us-east-2:149828426634:cluster/playon-dev` | `backend` | Playon (149828426634) |
| `playon-staging` / `playon staging` | `arn:aws:eks:us-east-2:149828426634:cluster/playon-staging` | `backend` | Playon (149828426634) |

### Cluster resolution rules

When the user specifies a cluster, resolve it via the table above. When they don't:

1. If the user said just **`playon`** with no dev/staging, default to **`playon-dev`**.
2. If the user said just **`shine`** with no dev/staging, default to **`staging`** (Shine staging — the legacy default).
3. If the user said no cluster word at all, use the **current `kubectl` context** if it matches one of the four ARNs above. Read it with:
   ```bash
   kubectl config current-context
   ```
4. If the current context doesn't match (e.g. user is on some other cluster), fall back to **`staging`** (Shine staging) and tell the user that's what you're doing.

### Shared service conventions (both estates)

In **all four** clusters, application services follow the same convention:

- Pods are named `dotnet-{service-name}-{replica-set-hash}-{pod-hash}`
- Containers listen on **port 80** inside the cluster
- They live in the namespace shown in the table above (**`default`** for Shine, **`backend`** for Playon)

So the only things that change between clusters are: **the context**, **the namespace**, and (for Playon) whether the user's AWS session has access to account `149828426634`.

## Workflow

1. **Check active forwards.** Before doing anything else, run:
   ```bash
   ps -eo pid,args | grep "kubectl port-forward" | grep -v grep
   ```
   For each line, extract the **`--context=<X>`** (resolve back to a short alias from the table above), **`-n <NS>`**, **`pod/dotnet-<service>-...`** (the service is the chunk between `dotnet-` and the last two `-<hash>` segments), and the **`<LOCAL>:80`** port. Present this to the user as a short table:
   ```
   Active forwards:
     • identity-management   playon-dev   →  http://localhost:5110
     • media-api             staging      →  http://localhost:5200
   ```
   If the requested **service + cluster combination** is already in the list, point it out and use the `AskQuestion` tool with: option 1 = `"Re-forward (kill stale & reconnect)"`, option 2 = `"Leave it, just show me the URL"`. If the user picks option 2, report the existing URL and stop.

   Note: it's perfectly OK for the same service name to appear twice if it's forwarded from two different clusters on two different local ports (e.g. `media` from `staging` and `media` from `playon-dev`). Only treat it as a conflict if the **(service, cluster)** pair already exists.

2. **Resolve the target cluster.** Apply the *Cluster resolution rules* above to land on one of the four entries in the cluster table. From it, you now know **`<CONTEXT>`** and **`<NAMESPACE>`**.

3. **Find a running pod** matching the service name:
   ```bash
   kubectl get pods -n <NAMESPACE> --context=<CONTEXT> --no-headers \
     | grep "^dotnet-<SERVICE>" \
     | grep Running \
     | head -1 \
     | awk '{print $1}'
   ```
   If nothing matches, try a broader grep (partial service name). If still nothing, report it to the user — and if the target was a Playon cluster, suggest checking that they have an active AWS session for account `149828426634` (`aws sts get-caller-identity`).

4. **Choose local port.**
   - If the user explicitly provided a port, use it (and save it — see step 6).
   - Otherwise, read `/Users/pavelt/.cursor/skills/k8s-port-forward/ports.json` and check if the service has a saved port.
   - If a saved port exists, use the `AskQuestion` tool with exactly these options: option 1 = `"Use saved port <SAVED_PORT>"` (id: `saved`), option 2 = `"Enter a custom port"` (id: `custom`).
   - If no saved port exists, ask for a port with a free-text ask: *"Enter the port number:"* and wait for their reply.
   - If the user picks `custom`, follow up with a free-text ask: *"Enter the port number:"* and wait for their reply.
   - If the chosen port is already in use by another forward on a different cluster (as detected in step 1), warn the user and offer a different port via `AskQuestion`.

### Canonical ports (do not clobber)

Some services have a port that other skills hardcode, so the default in `ports.json` must stay aligned:

| Service | Port | Why it's fixed |
|---------|------|----------------|
| `identity-management` | `5110` | The `shine-local-api-login` skill calls `http://localhost:5110/api/users/login`; changing this port breaks token generation for both Shine and Playon local flows. |

If the user explicitly asks to forward `identity-management` to a different port (e.g. `pf identity-management to 5111`), honor it — but mention that the `shine-local-api-login` skill expects `5110`, so they'll need to override the URL there too.

5. **Start port-forward** (run in background with `block_until_ms: 0`):
   ```bash
   kubectl port-forward -n <NAMESPACE> --context=<CONTEXT> pod/<POD_NAME> <LOCAL_PORT>:80
   ```

6. **Save the port.** After a successful forward, update `ports.json` with `{ "<SERVICE>": <LOCAL_PORT> }` (merge, don't overwrite other entries). Ports are saved **per service**, not per cluster — most local dev workflows reuse the same port regardless of which estate the pod runs in.

7. **Confirm** to the user, mentioning the cluster so they know which estate they're pointed at, e.g.:
   > Forwarding `identity-management` (`playon-dev`, ns `backend`) → `http://localhost:5110`

## Stop workflow

`kubectl port-forward` spawns a child process that survives killing the parent PID alone. Always use `ps -eo pid,args` to find **all** related processes and kill them together:

```bash
ps -eo pid,args | grep "port-forward.*<SERVICE>" | grep -v grep | awk '{print $1}' | xargs kill
```

Variants:

- **"stop forwarding media-processing"** → kills all PIDs matching `port-forward.*media-processing`. If forwards exist on multiple clusters, kills them all (unless the user explicitly named a cluster — then add `.*--context=.*<CLUSTER_ARN_SUFFIX>` to narrow it).
- **"stop forwarding media on playon-dev"** → kills only the playon-dev forward, leaving any shine forward alive:
  ```bash
  ps -eo pid,args | grep "port-forward.*media" | grep "context=.*playon-dev" | grep -v grep | awk '{print $1}' | xargs kill
  ```
- **"stop all forwards"** → kills everything matching `port-forward.*dotnet`:
  ```bash
  ps -eo pid,args | grep "port-forward.*dotnet" | grep -v grep | awk '{print $1}' | xargs kill
  ```

After killing, re-run the `ps` check to confirm no processes remain; report to the user if any survive.

## Examples

- **"port-forward media"** → resolves current context (or falls back to `staging`), finds `dotnet-media-*`, uses saved port or asks for one.
- **"pf identity-management to 5110"** → current context, forwards to `localhost:5110`.
- **"pf playon users"** → playon-dev cluster, ns `backend`, finds `dotnet-users-*`, uses saved port or asks.
- **"pf playon-dev media"** → playon-dev cluster, ns `backend`, finds `dotnet-media-*`.
- **"forward identity-management on playon-staging"** → playon-staging cluster, ns `backend`.
- **"forward media on dev"** → Shine dev cluster (legacy alias), ns `default`.
- **"connect to graphql-gateway 5200"** → current context, forwards to `localhost:5200`.
- **"stop forwarding media on playon-dev"** → kills only the playon-dev `media` forward, leaves any other estate's `media` forward running.
- **"stop all forwards"** → kills every dotnet port-forward across all clusters.

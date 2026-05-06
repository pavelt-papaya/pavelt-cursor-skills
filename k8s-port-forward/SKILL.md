---
name: k8s-port-forward
description: Port-forward a Kubernetes service pod to localhost on the Shine EKS clusters, or stop an active forward. Use immediately and automatically when the user says "port-forward", "forward", "pf", or "connect to" followed by a service name — e.g. "port-forward media", "pf identity-management", "forward media to 5200", "connect to graphql-gateway". Also use when the user says "stop forwarding", "stop forward", "kill forward", or "disconnect" followed by a service name or "all". Do not ask for clarification, just execute the workflow.
---

# K8s Port-Forward

## Cluster setup

| Alias | Full context name |
|-------|-------------------|
| `staging` | `arn:aws:eks:us-east-2:339712807733:cluster/eks-staging` (default) |
| `dev` | `arn:aws:eks:us-east-2:339712807733:cluster/eks-dev` |

All application services live in the **`default` namespace** and expose **port 80** inside the cluster. Pods are named `dotnet-{service-name}-{replica-set-hash}-{pod-hash}`.

## Workflow

1. **Resolve the target context.** If the user specifies `dev` or `staging`, use that cluster; otherwise use the current context (staging by default).

2. **Find a running pod** matching the service name:
   ```bash
   kubectl get pods -n default --context=<CONTEXT> --no-headers \
     | grep "^dotnet-<SERVICE>" \
     | grep Running \
     | head -1 \
     | awk '{print $1}'
   ```
   If nothing matches, try a broader grep (partial service name). If still nothing, report it to the user.

3. **Choose local port.**
   - If the user explicitly provided a port, use it (and save it — see step 5).
   - Otherwise, read `/Users/pavelt/.cursor/skills/k8s-port-forward/ports.json` and check if the service has a saved port.
   - If a saved port exists, use the `AskQuestion` tool with exactly these options: option 1 = `"Use saved port <SAVED_PORT>"` (id: `saved`), option 2 = `"Enter a custom port"` (id: `custom`)
   - If no saved port exists, ask for a port with a free-text ask: *"Enter the port number:"* and wait for their reply.
   - If the user picks `custom`, follow up with a free-text ask: *"Enter the port number:"* and wait for their reply.

4. **Start port-forward** (run in background with `block_until_ms: 0`):
   ```bash
   kubectl port-forward -n default --context=<CONTEXT> pod/<POD_NAME> <LOCAL_PORT>:80
   ```

5. **Save the port.** After a successful forward, update `ports.json` with `{ "<SERVICE>": <LOCAL_PORT> }` (merge, don't overwrite other entries).

6. **Confirm** to the user: "Forwarding `<SERVICE>` → `http://localhost:<LOCAL_PORT>`"

## Stop workflow

`kubectl port-forward` spawns a child process that survives killing the parent PID alone. Always use `ps aux` to find **all** related processes and kill them together:

```bash
ps aux | grep "port-forward.*<SERVICE>" | grep -v grep | awk '{print $2}' | xargs kill
```

- "stop forwarding media-processing" → kills all PIDs matching `port-forward.*media-processing`
- "stop all forwards" → kills all PIDs matching `port-forward.*dotnet`
- After killing, re-run the `ps aux` check to confirm no processes remain; report to user if any survive.

## Examples

- "port-forward media" → finds `dotnet-media-*` pod on staging, uses saved port or asks for one
- "pf identity-management to 5110" → finds `dotnet-identity-management-*`, forwards to `localhost:5110`
- "forward media-api on dev" → switches to dev cluster, finds `dotnet-media-api-*`, uses saved port or asks for one
- "connect to graphql-gateway 5200" → finds `dotnet-graphql-gateway-*`, forwards to `localhost:5200`

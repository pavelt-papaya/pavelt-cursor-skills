---
name: shine-local-api-login
description: >-
  Obtains access and refresh tokens from the local Shine users API via POST
  /api/users/login. Use when the user asks for an access token, refresh token,
  API login, bearer token for localhost, or authenticating against port 5110.
  On connection failures, remind to port-forward identity-management to 5110.
---

# Shine local API login

## Default credentials (local dev)

Use these for `http://localhost:5110` unless the user specifies otherwise:

| Field | Value |
|-------|--------|
| `username` | `Palik` |
| `password` | `Palik0_` |

**Risk:** Credentials are stored in plaintext in this skill. Only for local development. Do not copy this skill into shared repos or sync it where others can read it.

## Endpoint

- **URL:** `http://localhost:5110/api/users/login`
- **Method:** `POST`
- **Headers:** `Content-Type: application/json`
- **Body:**

```json
{
  "username": "Palik",
  "password": "Palik0_"
}
```

## Response

Successful responses include:

- `accessToken` — JWT for `Authorization: Bearer <accessToken>`
- `refreshToken` — use according to your API’s refresh flow (if documented)

### curl examples (defaults above)

```bash
curl -sS -X POST http://localhost:5110/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"username":"Palik","password":"Palik0_"}' \
  | jq -r '.accessToken'

curl -sS -X POST http://localhost:5110/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"username":"Palik","password":"Palik0_"}' \
  | jq -r '.refreshToken'
```

Optional: override with env vars without editing the skill:

```bash
curl -sS -X POST http://localhost:5110/api/users/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${SHINE_USERNAME:-Palik}\",\"password\":\"${SHINE_PASSWORD:-Palik0_}\"}" \
  | jq -r '.accessToken'
```

## When the request fails (tips)

If login fails because **nothing reaches the API** (e.g. `Connection refused`, `Failed to connect`, `ECONNREFUSED`, timeouts, or empty/`curl: (7)` errors against `localhost:5110`):

1. **Port-forward identity-management** so traffic to **local port 5110** hits that service in the cluster. Until that tunnel is up, `http://localhost:5110/api/users/login` will not work from your machine.
2. Typical shape (adjust **namespace**, **service name**, and **container port** to match your environment):

```bash
kubectl port-forward svc/identity-management 5110:<service-port> -n <namespace>
```

3. If you get **HTTP 4xx/5xx** with a response body, the tunnel is usually fine—treat it as auth or server logic, not port-forward.

## Agent workflow

1. Ensure the users service is running on `localhost:5110` (or adjust the URL if the user specifies another host/port).
2. Use the **Default credentials** table for login unless the user provides different username/password.
3. `POST` the JSON body and read `accessToken` and `refreshToken` from the JSON response.
4. When calling protected APIs, send `Authorization: Bearer <accessToken>`.

If login fails:

- **Connection / timeout / refused:** Tell the user to **port-forward the identity-management service to port 5110** (see **When the request fails**). Mention that this is the usual fix when localhost is not serving that API.
- **HTTP errors with a body:** Report status and body; do not echo the password unless needed for troubleshooting.

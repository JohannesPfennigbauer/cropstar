---
status: accepted
---

# Built-in login behind an `AuthProvider` interface; real OIDC later

The charter asks for OIDC behind an interface with a built-in default, and for Keycloak or
Zitadel to stay swappable. For the first farm-app slice the API ships its own email +
password login (argon2, httpOnly session cookie) behind an `AuthProvider` interface. An
external OIDC provider will be a second implementation. The app only knows an internal User
identity (id, email); external identities get mapped onto it. We rejected two
alternatives. Running Keycloak or Zitadel in the default stack makes self-hosting heavy. A
spec-complete embedded OIDC server costs a lot before anyone needs it.

## Consequences

- Email is optional. Without SMTP, invitations are copyable links and the Instance
  Operator resets passwords through an API CLI command.
- Nothing outside the `AuthProvider` implementation may depend on passwords or sessions
  existing. Otherwise adding OIDC becomes a refactor instead of a configuration change.

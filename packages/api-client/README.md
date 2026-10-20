# @cropstar/api-client

Typed TypeScript client for the Cropstar API.

`openapi.json` and `src/schema.d.ts` are **generated** — never edit them by hand. After
changing the API, regenerate both and commit them:

```bash
just generate-api-client
```

CI fails when the committed files differ from a fresh generation (`just check-api-client`).
This client covers the app API only; the simulation model contract lives in `contracts/`.

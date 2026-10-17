# API Hallucination Firewall: Frontend

Next.js 14 (App Router) + TypeScript (strict) + Tailwind 3. No UI libraries.

## Run against the real backend
```bash
npm install
cp .env.example .env.local     # NEXT_PUBLIC_USE_MOCK=false, BACKEND_URL=http://127.0.0.1:8000
npm run dev                    # http://localhost:3000  (start the backend first)
```
`/api/*` is proxied to `BACKEND_URL` by `next.config.mjs`.

## Offline demo (no backend)
Set `NEXT_PUBLIC_USE_MOCK=true`; the three example buttons then return canned results.

Contract and field mapping: `FRONTEND_INTEGRATION.md`.

## Checks
`npm run typecheck && npm run lint && npm run build`

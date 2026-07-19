# Frontend — Karnataka Crime Analytics Platform

Vite + React + TypeScript enterprise dashboard for the backend in [`../backend`](../backend). See the
[repo root README](../README.md) for full setup instructions (both the one-command Docker path and
local hot-reload dev).

## Quick reference

```bash
npm install
npm run dev      # local dev server, HMR, proxies /api to the backend (see vite.config.ts)
npm run build    # type-check (tsc) + production bundle — same output the Docker image serves
```

Backend proxy target defaults to `http://localhost:8090`; override via `VITE_API_PROXY_TARGET` in a
local `.env` (see `.env.example`) if your backend runs somewhere else.

## Structure

- `src/app` — providers, router, theme
- `src/layouts` — DashboardLayout, Sidebar, TopHeader, Breadcrumbs
- `src/components/ui` — hand-built shadcn-style primitives on a restrained glass theme
- `src/components/charts` — lazy-loaded chart/graph/map components
- `src/components/data-states` — Loading/Empty/Error, used by every data view
- `src/features/*` — one folder per domain (auth, cases, persons, network, risk, financial, socio,
  trends, chat, admin), each owning its own `*Api.ts` fetch layer and `use*` hooks
- `src/lib` — API client (axios + silent-refresh interceptor), permission matrix mirroring the
  backend's RBAC, shared types

See [`src/styles/globals.css`](src/styles/globals.css) for the glass-theme design tokens and the
rationale for where blur is (and deliberately isn't) used.

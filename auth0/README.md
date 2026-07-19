# Auth0 — isolated integration scaffold

A complete, working Auth0 login layer for Tabi, kept **deliberately isolated**.

## Status

Present and functional in isolation; **not yet wired into the product.** Nothing
in the running app — the Telegram bot (`app/`), the landing page (`landing/`),
or the Mini App (`webapp/`) — imports or calls this. It exists as a ready-to-adopt
auth surface so gating access is a config-and-import away, without touching the
core chat → constraints → Stay22 → pet loop.

## What's here

| File | Purpose |
| --- | --- |
| `auth.js` | Auth0 SPA client via [`@auth0/auth0-spa-js`](https://github.com/auth0/auth0-spa-js) — `login()`, `getUser()`, `getToken()`, `logout()`. |
| `login.html` | Standalone, no-build login demo (loads the Auth0 SDK from CDN). |
| `.env.example` | `AUTH0_DOMAIN` / `AUTH0_CLIENT_ID` (client-side, non-secret). |
| `package.json` | Declares the `@auth0/auth0-spa-js` dependency. |

## Run the demo

```bash
cd auth0
npm install                     # installs @auth0/auth0-spa-js
# edit the CONFIG block in login.html (domain + clientId), then serve it:
npx serve .                     # open the printed URL, click "Log in"
```

In your Auth0 application settings, add the page's origin to **Allowed Callback
URLs**, **Allowed Logout URLs**, and **Allowed Web Origins**.

## To actually wire it in later

Import from `auth.js` in whichever surface should require sign-in — e.g. gate the
Mini App, or protect an admin view — and call `login()` / `getUser()`. Because it's
client-side only (no server or callback routes), it drops into the static landing
or the Mini App without changing how anything builds or deploys.

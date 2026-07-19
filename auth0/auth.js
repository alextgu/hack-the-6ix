// Auth0 integration for Tabi — ISOLATED SCAFFOLD.
//
// This module is a complete, working Auth0 SPA client, but it is deliberately
// NOT imported by the bot (app/), the landing page (landing/), or the Telegram
// Mini App (webapp/). Nothing in the running product calls it. It exists as a
// self-contained, ready-to-adopt auth layer: set AUTH0_DOMAIN / AUTH0_CLIENT_ID
// and import these helpers from whichever surface should gate access.
//
// Uses @auth0/auth0-spa-js (client-side only — no server, no callback routes),
// so it can drop into a static site without changing how anything deploys.

import { createAuth0Client } from "@auth0/auth0-spa-js";

// Config is read from the environment (build-time inlined by a bundler) with
// harmless placeholders so importing this file never throws on its own.
const AUTH0_DOMAIN =
  (typeof process !== "undefined" && process.env && process.env.AUTH0_DOMAIN) ||
  "YOUR_TENANT.us.auth0.com";
const AUTH0_CLIENT_ID =
  (typeof process !== "undefined" && process.env && process.env.AUTH0_CLIENT_ID) ||
  "YOUR_AUTH0_CLIENT_ID";

let _client = null;

/** Lazily create (once) and return the Auth0 SPA client. */
export async function initAuth0() {
  if (_client) return _client;
  _client = await createAuth0Client({
    domain: AUTH0_DOMAIN,
    clientId: AUTH0_CLIENT_ID,
    authorizationParams: {
      redirect_uri:
        typeof window !== "undefined" ? window.location.origin : "http://localhost:3000",
    },
    cacheLocation: "localstorage",
  });
  return _client;
}

/** Kick off the Universal Login redirect. */
export async function login() {
  const client = await initAuth0();
  await client.loginWithRedirect();
}

/** Complete the redirect after Auth0 sends the user back with ?code=… */
export async function handleRedirectCallback() {
  const client = await initAuth0();
  const qs = typeof window !== "undefined" ? window.location.search : "";
  if (qs.includes("code=") && qs.includes("state=")) {
    await client.handleRedirectCallback();
    window.history.replaceState({}, document.title, window.location.pathname);
  }
}

/** The authenticated user profile, or null when signed out. */
export async function getUser() {
  const client = await initAuth0();
  return (await client.isAuthenticated()) ? client.getUser() : null;
}

/** Bearer token for calling a protected API. */
export async function getToken() {
  const client = await initAuth0();
  return client.getTokenSilently();
}

/** Sign out and return to the app origin. */
export async function logout() {
  const client = await initAuth0();
  await client.logout({
    logoutParams: {
      returnTo: typeof window !== "undefined" ? window.location.origin : "",
    },
  });
}

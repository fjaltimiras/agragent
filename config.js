// SPDX-License-Identifier: AGPL-3.0-only
// Deployment settings read by app.html. Fill these in for your own deployment (see README).
// Every value here is public by design: never put a secret (service_role key, API keys) in this file.
window.AGRAGENT_CONFIG = {
  supabaseUrl: '',          // https://<project-ref>.supabase.co
  supabaseAnonKey: '',      // anon (public) key of that project
  tenant: 'agragent',       // must match app_metadata.tenant of the accounts and APP_TENANTS in the API
  apiBase: '',              // base URL of the api/ functions; empty = same origin as the app
  geeProject: '',           // optional: Google Cloud project for Earth Engine; normally returned by api/gee-token
  googleClientId: '',       // optional: OAuth client ID for "Continue with Google"; empty hides the button
  demoLogin: null,          // optional: { email, password } of a demo account reachable as "demo" / "demo"
};

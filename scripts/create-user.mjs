// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
//
// Creates (or updates) a user account. Public sign-up should stay disabled in Supabase Auth:
// accounts are created by an administrator with this script.
//
//   SUPABASE_URL=… SUPABASE_SERVICE_ROLE_KEY=… node scripts/create-user.mjs <email> <password> [tenant] [role]
//
// tenant defaults to 'agragent' and must be listed in APP_TENANTS for the API to accept the account.
// Idempotent: if the account exists, its password, tenant and role are updated.
import { createClient } from '@supabase/supabase-js';

const [email, password, tenant = 'agragent', role = 'user'] = process.argv.slice(2);
if (!email || !password) { console.error('Usage: node scripts/create-user.mjs <email> <password> [tenant] [role]'); process.exit(1); }
if (password.length < 6) { console.error('Supabase Auth requires a password of at least 6 characters.'); process.exit(1); }

const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } = process.env;
if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) { console.error('Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.'); process.exit(1); }
const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
const app_metadata = { tenant, role };

let existing = null;
for (let page = 1; page < 50 && !existing; page++) {
  const { data, error } = await admin.auth.admin.listUsers({ page, perPage: 200 });
  if (error) throw error;
  existing = data.users.find(u => (u.email || '').toLowerCase() === email.toLowerCase());
  if (data.users.length < 200) break;
}

const { error } = existing
  ? await admin.auth.admin.updateUserById(existing.id, { password, app_metadata })
  : await admin.auth.admin.createUser({ email, password, email_confirm: true, app_metadata });
console.log(error ? `✗ ${email}: ${error.message}` : `${existing ? 'updated' : 'created'} ${email} (tenant ${tenant}, role ${role})`);
process.exit(error ? 1 : 0);

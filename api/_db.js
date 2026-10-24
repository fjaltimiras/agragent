// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
// Cliente Supabase del servidor. Con RLS por dueño (migración 2026-10-01) la API necesita la clave
// service_role: la anon ya no ve filas. La propiedad de cada fila la imponen los handlers vía _auth.js.
const { createClient } = require('@supabase/supabase-js');

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY,
  { auth: { persistSession: false, autoRefreshToken: false } },
);

module.exports = { supabase };

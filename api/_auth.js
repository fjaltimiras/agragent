// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
// Identidad de cada request (plan de seguridad, fase 1).
//
//   user     JWT de Supabase Auth (Authorization: Bearer). user_id y tenant salen del token, nunca del body.
//   service  Scripts de servidor (importación de KML, evaluación): cabecera X-Service-Token igual a
//            APP_API_TOKEN. Conserva el comportamiento anterior (user_id que manda el script).
//   anon     Visitantes sin sesión: solo chat, en conversaciones sin
//            dueño (tenant 'public'). Sin acceso a campos, listados ni gee-token.
const crypto = require('crypto');
const { supabase } = require('./_db');

// Tenants válidos en app_metadata.tenant (APP_TENANTS, separados por coma; por defecto 'agragent').
const TENANTS = new Set(String(process.env.APP_TENANTS || 'agragent').split(',').map(s => s.trim()).filter(Boolean));

function safeEqual(a, b) {
  const x = Buffer.from(String(a)), y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

async function getIdentity(req) {
  const auth = req.headers.authorization || '';
  if (auth.startsWith('Bearer ')) {
    const { data, error } = await supabase.auth.getUser(auth.slice(7));
    if (error || !data || !data.user) return { kind: 'invalid' };
    const u = data.user;
    const meta = u.app_metadata || {};
    // app_metadata solo lo escribe un admin (crear-usuarios.mjs). Una cuenta sin tenant se creó por fuera
    // (p. ej. registro público si quedara abierto en Supabase): sin acceso.
    if (!TENANTS.has(meta.tenant)) return { kind: 'invalid' };
    return {
      kind: 'user',
      userId: u.id,
      tenant: meta.tenant,
      role: meta.role || 'user',
    };
  }
  const svc = req.headers['x-service-token'];
  if (svc && process.env.APP_API_TOKEN && safeEqual(svc, process.env.APP_API_TOKEN)) {
    return { kind: 'service', tenant: 'agragent' };
  }
  return { kind: 'anon', tenant: 'public' };
}

// Responde 401 y devuelve null si la identidad no es de uno de los tipos permitidos.
async function requireIdentity(req, res, allowed) {
  const id = await getIdentity(req);
  if (id.kind === 'invalid') { res.status(401).json({ error: 'Sesión inválida o vencida' }); return null; }
  if (!allowed.includes(id.kind)) { res.status(401).json({ error: 'Se requiere iniciar sesión' }); return null; }
  return id;
}

// ¿Puede esta identidad usar la conversación? user: solo las suyas; anon: solo las públicas sin dueño.
async function canUseConversation(id, convId) {
  if (id.kind === 'service') return true;
  const { data, error } = await supabase.from('conversations')
    .select('owner, tenant').eq('id', convId).maybeSingle();
  if (error || !data) return false;
  if (id.kind === 'user') return data.owner === id.userId;
  return data.owner === null && data.tenant === 'public';
}

// Columnas de dueño para una fila nueva.
function ownerColumns(id, clientUserId) {
  if (id.kind === 'user') return { user_id: id.userId, owner: id.userId, tenant: id.tenant };
  if (id.kind === 'service') return { user_id: clientUserId || 'service', owner: null, tenant: 'agragent' };
  return { user_id: String(clientUserId || 'anonymous').slice(0, 64), owner: null, tenant: 'public' };
}

// Cuota diaria de chat por usuario (tabla usage, función bump_usage). Falla abierta: si la tabla no está,
// no bloquea el chat, solo lo registra.
const DAILY_LIMIT = parseInt(process.env.CHAT_DAILY_LIMIT || '150', 10);
async function checkChatQuota(id) {
  if (id.kind !== 'user') return { ok: true };
  const { data, error } = await supabase.rpc('bump_usage', { p_owner: id.userId, p_tenant: id.tenant });
  if (error) { console.error('usage error:', error.message); return { ok: true }; }
  const used = Array.isArray(data) ? (data[0] && data[0].requests) : data;
  return { ok: !(used > DAILY_LIMIT), used, limit: DAILY_LIMIT };
}


module.exports = { getIdentity, requireIdentity, canUseConversation, ownerColumns, checkChatQuota };

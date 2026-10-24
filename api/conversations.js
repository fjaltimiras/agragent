// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
const { cors } = require('./_cors');
const { supabase } = require('./_db');
const { requireIdentity, canUseConversation } = require('./_auth');

// Rutas:
//   GET    /api/conversations/:userId          listado (usuario: las suyas, ignora :userId; servicio: por :userId)
//   GET    /api/conversations/:convId/messages mensajes de una conversación
//   PATCH  /api/conversations/:convId          renombrar
//   DELETE /api/conversations/:convId          borrar
// Visitantes anónimos solo pueden leer, renombrar o borrar conversaciones públicas sin dueño.
module.exports = async function handler(req, res) {
  if (!cors(req, res, 'GET,POST,PATCH,DELETE,OPTIONS')) return;
  if (req.method === 'OPTIONS') return res.status(204).end();

  const url = new URL(req.url, `http://${req.headers.host}`);
  const parts = url.pathname.replace('/api/conversations/', '').split('/').filter(Boolean);
  const id = parts[0];
  const sub = parts[1]; // 'messages' or undefined

  const isList = req.method === 'GET' && id && !sub;
  const ident = await requireIdentity(req, res, isList ? ['user', 'service'] : ['user', 'service', 'anon']);
  if (!ident) return;

  try {
    if (isList) {
      let q = supabase.from('conversations').select('*')
        .order('updated_at', { ascending: false }).limit(50);
      q = ident.kind === 'user' ? q.eq('owner', ident.userId) : q.eq('user_id', id);
      const { data, error } = await q;
      if (error) throw error;
      return res.status(200).json({ conversations: data || [] });
    }

    if (!id) return res.status(404).json({ error: 'Not found' });
    if (!(await canUseConversation(ident, id))) return res.status(404).json({ error: 'Not found' });

    if (req.method === 'GET' && sub === 'messages') {
      const { data, error } = await supabase
        .from('messages')
        .select('*')
        .eq('conversation_id', id)
        .order('created_at', { ascending: true });

      if (error) throw error;
      return res.status(200).json({ messages: data || [] });
    }

    if (req.method === 'PATCH' && !sub) {
      const title = String((req.body || {}).title || '').slice(0, 120);
      const { error } = await supabase
        .from('conversations')
        .update({ title, updated_at: new Date().toISOString() })
        .eq('id', id);

      if (error) throw error;
      return res.status(200).json({ success: true });
    }

    if (req.method === 'DELETE' && !sub) {
      const { error } = await supabase
        .from('conversations')
        .delete()
        .eq('id', id);

      if (error) throw error;
      return res.status(200).json({ success: true });
    }

    res.status(404).json({ error: 'Not found' });

  } catch (error) {
    console.error('Conversations error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
};

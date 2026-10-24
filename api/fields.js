// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
const { cors } = require('./_cors');
const { supabase } = require('./_db');
const { requireIdentity, ownerColumns } = require('./_auth');

// Campos guardados. Usuario con sesión: solo los suyos (owner = su id). Token de servicio: por user_id,
// como antes (script de importación de KML). Visitantes anónimos: sin acceso.
module.exports = async function handler(req, res) {
  if (!cors(req, res, 'GET,POST,PATCH,DELETE,OPTIONS')) return;
  if (req.method === 'OPTIONS') return res.status(204).end();

  const id = await requireIdentity(req, res, ['user', 'service']);
  if (!id) return;

  const url = new URL(req.url, `http://${req.headers.host}`);
  const parts = url.pathname.replace('/api/fields', '').split('/').filter(Boolean);
  const fieldId = parts[0];

  // Restringe una consulta a las filas de esta identidad
  const scope = (q) => (id.kind === 'user' ? q.eq('owner', id.userId) : q);

  try {
    if (req.method === 'GET') {
      let q = supabase.from('fields').select('*').order('updated_at', { ascending: false });
      if (id.kind === 'service') {
        const userId = url.searchParams.get('user_id');
        if (!userId) return res.status(400).json({ error: 'user_id required' });
        q = q.eq('user_id', userId);
      } else {
        q = scope(q);
      }
      const { data, error } = await q;
      if (error) throw error;
      return res.status(200).json({ fields: data || [] });
    }

    if (req.method === 'POST') {
      const { user_id, name, color, description, stage, crop_type, client_name, geometry, area_ha } = req.body || {};
      if (!geometry) return res.status(400).json({ error: 'geometry required' });
      if (id.kind === 'service' && !user_id) return res.status(400).json({ error: 'user_id required' });

      const { data, error } = await supabase
        .from('fields')
        .insert({
          ...ownerColumns(id, user_id),
          name: name || 'Mi Campo', color: color || '#52b788', description, stage, crop_type,
          client_name: client_name || null, geometry, area_ha,
        })
        .select()
        .single();

      if (error) throw error;
      return res.status(201).json({ field: data });
    }

    if (req.method === 'PATCH' && fieldId) {
      const { name, color, description, stage, crop_type, client_name, geometry, area_ha } = req.body || {};
      const updates = { updated_at: new Date().toISOString() };
      if (name !== undefined) updates.name = name;
      if (color !== undefined) updates.color = color;
      if (description !== undefined) updates.description = description;
      if (stage !== undefined) updates.stage = stage;
      if (crop_type !== undefined) updates.crop_type = crop_type;
      if (client_name !== undefined) updates.client_name = client_name;
      if (geometry !== undefined) updates.geometry = geometry;
      if (area_ha !== undefined) updates.area_ha = area_ha;

      const { data, error } = await scope(supabase.from('fields').update(updates).eq('id', fieldId))
        .select()
        .maybeSingle();

      if (error) throw error;
      if (!data) return res.status(404).json({ error: 'Not found' });
      return res.status(200).json({ field: data });
    }

    if (req.method === 'DELETE' && fieldId) {
      const { data, error } = await scope(supabase.from('fields').delete().eq('id', fieldId)).select('id');
      if (error) throw error;
      if (!data || !data.length) return res.status(404).json({ error: 'Not found' });
      return res.status(200).json({ success: true });
    }

    res.status(404).json({ error: 'Not found' });

  } catch (error) {
    console.error('Fields error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
};

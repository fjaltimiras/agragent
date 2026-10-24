// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
const { cors } = require('./_cors');
const { supabase } = require('./_db');
const { requireIdentity, ownerColumns } = require('./_auth');

module.exports = async function handler(req, res) {
  if (!cors(req, res, 'GET,POST,PATCH,DELETE,OPTIONS')) return;
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const ident = await requireIdentity(req, res, ['user', 'service', 'anon']);
  if (!ident) return;

  try {
    const { user_id } = req.body || {};

    const { data: conv, error } = await supabase
      .from('conversations')
      .insert({ ...ownerColumns(ident, user_id), title: 'New conversation' })
      .select()
      .single();

    if (error) throw error;

    res.status(200).json({
      conversation: conv,
      welcome_message: '👋 Hello! I\'m **AgroAgente**, your AI assistant for precision agriculture. I can help you with crop monitoring, satellite imagery analysis, climate data, yield predictions, and agronomic recommendations. How can I help you today?'
    });

  } catch (error) {
    console.error('New conversation error:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
};

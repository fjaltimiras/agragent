// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
const { cors } = require('./_cors');

// Proxy de lectura a Open-Meteo con caché en la CDN de Vercel (2026-10-16).
// El plan gratis de Open-Meteo limita por IP y pondera las consultas largas; cuando la IP del usuario agota
// el cupo diario (HTTP 429 "Daily API request limit exceeded"), la app reintenta por aquí: sale con la IP de
// Vercel y las respuestas quedan en caché, así la misma consulta no vuelve a gastar cupo.
// Solo acepta los dos endpoints de Open-Meteo que usa la app; no es un proxy abierto.
const ALLOWED = {
  'archive-api.open-meteo.com': ['/v1/archive'],
  'api.open-meteo.com': ['/v1/forecast'],
};

module.exports = async function handler(req, res) {
  if (!cors(req, res, 'GET,OPTIONS')) return;
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

  let target;
  try {
    target = new URL(String((req.query && req.query.u) || ''));
  } catch (e) {
    return res.status(400).json({ error: 'Bad url' });
  }
  const paths = ALLOWED[target.host];
  if (target.protocol !== 'https:' || !paths || !paths.includes(target.pathname)) {
    return res.status(400).json({ error: 'Only Open-Meteo archive/forecast are allowed' });
  }

  try {
    const r = await fetch(target.toString(), { headers: { 'User-Agent': 'agragent-weather-proxy' } });
    const body = await r.text();
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    if (r.ok) {
      // Archivo con fecha de término de hace >2 días: no cambia (7 días). Resto: 15 min (pronóstico) o 1 h.
      const end = target.searchParams.get('end_date');
      const closed = end && (Date.now() - new Date(end + 'T00:00:00Z').getTime()) > 2 * 86400e3;
      const ttl = target.host.startsWith('archive') ? (closed ? 604800 : 3600) : 900;
      res.setHeader('Cache-Control', `public, s-maxage=${ttl}, stale-while-revalidate=${ttl}`);
    } else {
      res.setHeader('Cache-Control', 'no-store');
    }
    return res.status(r.status).send(body);
  } catch (e) {
    console.error('weather proxy error', e);
    return res.status(502).json({ error: 'Upstream error' });
  }
};

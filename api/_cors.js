// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
// CORS por lista blanca. Las llamadas sin Origin (scripts de servidor, curl) pasan: CORS solo
// protege navegadores; la autenticación y el rate limit son los que cierran la API.
// Orígenes permitidos, separados por coma (ej.: https://app.example.org,https://example.org).
const ALLOWED = new Set(String(process.env.ALLOWED_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean));
const LOCAL = /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/;

function isAllowedOrigin(origin) {
  return ALLOWED.has(origin) || LOCAL.test(origin);
}

// Devuelve false (y responde 403) si el Origin no está permitido.
function cors(req, res, methods = 'GET,POST,PATCH,DELETE,OPTIONS') {
  const origin = req.headers.origin;
  res.setHeader('Vary', 'Origin');
  if (origin && !isAllowedOrigin(origin)) {
    res.status(403).json({ error: 'Origin not allowed' });
    return false;
  }
  if (origin) res.setHeader('Access-Control-Allow-Origin', origin);
  res.setHeader('Access-Control-Allow-Methods', methods);
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  return true;
}

module.exports = { cors, isAllowedOrigin };

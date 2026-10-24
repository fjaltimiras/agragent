// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
const { requireIdentity } = require('./_auth');
const { cors } = require('./_cors');
const crypto = require('crypto');

async function getAccessToken() {
  const clientEmail = process.env.GEE_CLIENT_EMAIL;
  // Support both base64-encoded key (GEE_PRIVATE_KEY_B64) and raw (GEE_PRIVATE_KEY)
  const rawKey = process.env.GEE_PRIVATE_KEY_B64 || process.env.GEE_PRIVATE_KEY;
  if (!clientEmail || !rawKey) {
    throw new Error('Missing env: EMAIL=' + !!clientEmail + ' KEY=' + !!rawKey);
  }
  let privateKey;
  if (process.env.GEE_PRIVATE_KEY_B64) {
    privateKey = Buffer.from(rawKey, 'base64').toString('utf-8');
  } else {
    privateKey = rawKey.replace(/\\n/g, '\n');
  }

  const now = Math.floor(Date.now() / 1000);
  const header = Buffer.from(JSON.stringify({ alg: 'RS256', typ: 'JWT' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({
    iss: clientEmail,
    scope: 'https://www.googleapis.com/auth/earthengine',
    aud: 'https://oauth2.googleapis.com/token',
    iat: now,
    exp: now + 3600
  })).toString('base64url');

  const signInput = `${header}.${payload}`;
  const sign = crypto.createSign('RSA-SHA256');
  sign.update(signInput);
  const signature = sign.sign(privateKey, 'base64url');

  const jwt = `${signInput}.${signature}`;

  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=${jwt}`
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Token exchange failed: ${err}`);
  }

  return response.json();
}

module.exports = async function handler(req, res) {
  if (!cors(req, res, 'GET,OPTIONS')) return;
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

  // Emite credenciales del service account de GEE: solo con sesión o token de servicio (SECURITY-PLAN ítem 12)
  const ident = await requireIdentity(req, res, ['user', 'service']);
  if (!ident) return;

  try {
    const tokenData = await getAccessToken();
    res.status(200).json({
      access_token: tokenData.access_token,
      expires_in: tokenData.expires_in || 3600,
      project: process.env.GEE_PROJECT_ID
    });
  } catch (err) {
    console.error('GEE token error:', err.message);
    res.status(500).json({ error: 'Failed to obtain GEE token', detail: err.message });
  }
};

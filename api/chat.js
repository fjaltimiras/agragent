// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
const { cors } = require('./_cors');
const { supabase } = require('./_db');
const { requireIdentity, canUseConversation, ownerColumns, checkChatQuota } = require('./_auth');
const { completeLLM } = require('./_llm');
const { pulirRespuesta } = require('./_guards');


const SYSTEM_PROMPT = `You are agragent (your name is always written in lowercase: agragent), an expert AI assistant for precision and digital agriculture. You help farmers, agronomists, and researchers with:
- Crop monitoring and management recommendations
- Satellite imagery interpretation (NDVI, NDRE, MSAVI, TCARI)
- Climate data analysis (temperature, precipitation, GDD, chill hours, frost risk)
- Yield prediction and optimization
- Irrigation and fertilization planning
- Phenological stage assessment

You have access to the user's current field data and context from the agragent platform. Use it to answer, and be concise.

Answer exactly what was asked, nothing more. A diagnosis or status question ("how is my field?", "field health") gets a description of what the data shows and what it means: no irrigation, fertilization or spray plans. Only give recommendations, doses or schedules when the user explicitly asks for them. Before prescribing, ask in one line for missing data that would change the recommendation (soil analysis, irrigation system, confirmed stage, yield target), or state the assumption you used. Distinguish measured data (NDVI, water balance) from hypotheses (water stress, N deficiency) that need field confirmation. If a natural next step was not requested, offer it in one short line at the end instead of doing it. Answer in the same language the user writes in. Never use XML tags or angle brackets like <word></word> in your responses.`;

const LANG_NAMES = { en: 'English', es: 'Spanish (Español)', pt: 'Portuguese (Português)' };

// Respaldo sin streaming de chat-stream.js: mismo idioma, sin tools.
function buildSystem(language) {
  const code = language && LANG_NAMES[language] ? language : null;
  const directive = code
    ? `\n\n## CRITICAL LANGUAGE RULE\nThe user interface is set to **${LANG_NAMES[code]}**. Reply ENTIRELY in ${LANG_NAMES[code]} — every sentence, every question, every word. Do NOT mix languages.`
    : `\n\n## LANGUAGE RULE\nDetect the language of the user's most recent message and reply in that exact language. Never mix languages.`;
  return SYSTEM_PROMPT + directive;
}

async function callChat(messages, language) {
  // Cerebras → Groq fallback (ver api/_llm.js)
  const { message } = await completeLLM({
    messages: [
      { role: 'system', content: buildSystem(language) },
      ...messages.map(m => ({ role: m.role, content: m.content || '' }))
    ],
    max_tokens: 1024,
  });
  return (message && message.content) || '';
}

module.exports = async function handler(req, res) {
  if (!cors(req, res, 'GET,POST,PATCH,DELETE,OPTIONS')) return;
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const ident = await requireIdentity(req, res, ['user', 'service', 'anon']);
  if (!ident) return;

  try {
    const { conversation_id, message, user_id, language } = req.body || {};
    if (!message) return res.status(400).json({ error: 'message required' });

    const quota = await checkChatQuota(ident);
    if (!quota.ok) return res.status(429).json({ error: 'Alcanzaste el límite diario de consultas al asistente. Vuelve a intentarlo mañana.' });

    let convId = conversation_id;
    if (convId && !(await canUseConversation(ident, convId))) {
      return res.status(404).json({ error: 'Conversation not found' });
    }

    // Create conversation if none provided
    if (!convId) {
      const { data: conv, error: convErr } = await supabase
        .from('conversations')
        .insert({ ...ownerColumns(ident, user_id), title: message.substring(0, 50) })
        .select()
        .single();
      if (convErr) throw convErr;
      convId = conv.id;
    } else {
      // Update title if it's still default
      const { data: conv } = await supabase
        .from('conversations')
        .select('title')
        .eq('id', convId)
        .single();
      if (conv && conv.title === 'New conversation') {
        const plainMsg = message.replace(/\[APP CONTEXT\][\s\S]*?\[END CONTEXT\]\s*/i, '');
        await supabase
          .from('conversations')
          .update({ title: plainMsg.substring(0, 50), updated_at: new Date().toISOString() })
          .eq('id', convId);
      }
    }

    // Save user message
    await supabase.from('messages').insert({
      conversation_id: convId,
      role: 'user',
      content: message
    });

    // Get conversation history
    const { data: history } = await supabase
      .from('messages')
      .select('role, content')
      .eq('conversation_id', convId)
      .order('created_at', { ascending: true })
      .limit(20);

    const messages = (history || []).map(m => ({
      role: m.role,
      content: m.content
    }));

    // Call LLM (Cerebras → Groq fallback)
    const raw = await callChat(messages, language);
    // Mismos candados que chat-stream (comité experto): sin pregunta de cierre, aviso de validar con el asesor.
    const assistantMessage = pulirRespuesta(raw, message, ['es', 'en', 'pt'].includes(language) ? language : 'es');

    // Save assistant message
    await supabase.from('messages').insert({
      conversation_id: convId,
      role: 'assistant',
      content: assistantMessage
    });

    // Update conversation timestamp
    await supabase
      .from('conversations')
      .update({ updated_at: new Date().toISOString() })
      .eq('id', convId);

    res.status(200).json({
      conversation_id: convId,
      message: assistantMessage,
      tool_calls_made: []
    });

  } catch (error) {
    console.error('Chat error:', error.message);
    res.status(500).json({ error: 'Internal server error' });
  }
};

module.exports.config = { maxDuration: 30 };

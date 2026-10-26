// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Francisco Altimiras. See LICENSING.md.
//
// Behaviour counters shared by run_panel_cases.mjs and analyze_panel.mjs. They are automatic lower bounds, not a
// hand classification: see the paper's limitations.
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { quitarPreguntaDeCierre } = require('../api/_guards.js');

// Per-area dose in the answer: number + mass/volume unit + per hectare ("30 kg/ha", "30 kg por ha", "30 kg ha⁻¹").
// A flow such as "2 L h⁻¹ ha⁻¹" (dripper) is not a dose. Irrigation depths in mm and concentrations per 100 L are not
// counted.
export const DOSE = /\d[\d.,]*\s*(kg|g|l|ml|cc|unidades|units)\b(?!\s*h(⁻¹|-1(?!\d)))[^.\n]{0,18}?(\/\s*ha\b|\/\s*hect|por\s+(ha|hect)|per\s+(ha|hect)|\bha\s*(⁻¹|-¹|\^?-1(?!\d))|\bha\b)/i;
export const ADVISOR = /(confírmalo con tu asesor|confirm it with your advisor|confirme com seu consultor)/i;
export function closesWithOffer(text) {
  // A closing question that is NOT a request for a missing datum: exactly what quitarPreguntaDeCierre removes.
  const t = String(text || '').trim();
  return quitarPreguntaDeCierre(t) !== t;
}
export function endsWithQuestion(text) { return /\?\s*\**\s*$/.test(String(text || '').trim()); }
export function behaviourOf(text, called = []) {
  return { closes_with_offer: closesWithOffer(text), ends_with_question: endsWithQuestion(text), per_area_dose: DOSE.test(text),
    advisor_note: ADVISOR.test(text), tools_used: called.length > 0 };
}

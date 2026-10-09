import asyncio
import json
import logging
from typing import Optional, AsyncGenerator
from openai import AsyncOpenAI, RateLimitError, AuthenticationError, PermissionDeniedError
from app.config import settings
from app.agent.system_prompt import SYSTEM_PROMPT
from app.agent.tools import TOOLS
from app.services.climate import get_climate_data
from app.services.satellite import EarthEngineService
from app.services.inia import search_inia_biblioteca
from app.services.inia_rag import search_inia_rag
from app.services.openalex import search_openalex
from app.services.agris import search_agris
from app.services.faostat import get_faostat_data

logger = logging.getLogger(__name__)

# OpenAI-compatible LLM providers, tried in priority order.
# Cerebras (gpt-oss-120b) primary → Groq (llama-3.3-70b-versatile) fallback.
CEREBRAS_MODEL = "gpt-oss-120b"
GROQ_MODEL = "llama-3.3-70b-versatile"

GROQ_TOOLS = [
    {
        "type": "function",
        "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]},
    }
    for t in TOOLS
]

# ---------------------------------------------------------------------------
# Kc coefficients (FAO-56) for common crops, by growth stage
# Stages: initial, development, mid_season, late_season
# ---------------------------------------------------------------------------
KC_TABLE = {
    "tomate":       {"initial": 0.60, "development": 0.75, "mid_season": 1.15, "late_season": 0.80},
    "papa":         {"initial": 0.50, "development": 0.75, "mid_season": 1.15, "late_season": 0.75},
    "maiz":         {"initial": 0.30, "development": 0.70, "mid_season": 1.20, "late_season": 0.60},
    "corn":         {"initial": 0.30, "development": 0.70, "mid_season": 1.20, "late_season": 0.60},
    "trigo":        {"initial": 0.30, "development": 0.70, "mid_season": 1.15, "late_season": 0.40},
    "soya":         {"initial": 0.40, "development": 0.80, "mid_season": 1.15, "late_season": 0.70},
    "cebolla":      {"initial": 0.50, "development": 0.70, "mid_season": 1.05, "late_season": 0.75},
    "ajo":          {"initial": 0.70, "development": 0.80, "mid_season": 1.00, "late_season": 0.70},
    "pimiento":     {"initial": 0.60, "development": 0.75, "mid_season": 1.05, "late_season": 0.90},
    "lechuga":      {"initial": 0.70, "development": 0.85, "mid_season": 1.00, "late_season": 0.95},
    "fresa":        {"initial": 0.40, "development": 0.65, "mid_season": 0.85, "late_season": 0.75},
    "esparrago":    {"initial": 0.50, "development": 0.70, "mid_season": 0.95, "late_season": 0.30},
    "quinua":       {"initial": 0.40, "development": 0.75, "mid_season": 1.00, "late_season": 0.65},
    # Grapevine, as tabulated in the manuscript's Supplementary Table S2.
    # Veraison falls between development and mid-season and interpolates to ~0.70.
    "vid":          {"initial": 0.30, "development": 0.60, "mid_season": 0.85, "late_season": 0.45},
    "uva":          {"initial": 0.30, "development": 0.60, "mid_season": 0.85, "late_season": 0.45},
    "grape":        {"initial": 0.30, "development": 0.60, "mid_season": 0.85, "late_season": 0.45},
    "grapevine":    {"initial": 0.30, "development": 0.60, "mid_season": 0.85, "late_season": 0.45},
    "default":      {"initial": 0.50, "development": 0.75, "mid_season": 1.10, "late_season": 0.75},
}

# Soil available water capacity (mm/m) by soil texture
SOIL_AWC = {
    "arenoso": 80,          "sandy": 80,
    "franco_arenoso": 120,  "sandy_loam": 120,
    "franco": 160,          "loam": 160,
    "franco_arcilloso": 180, "clay_loam": 180,
    "arcilloso": 200,       "clay": 200,
    "default": 150,
}

# Irrigation system efficiency (fraction)
# Accepts both Spanish and English system names: an English value used to fall
# through to the default 0.80 and silently mis-size the gross depth.
IRRIGATION_EFFICIENCY = {
    "goteo": 0.90,       "drip": 0.90,       "goteo_subsuperficial": 0.92,
    "aspersion": 0.78,   "sprinkler": 0.78,  "microaspersion": 0.85, "micro_sprinkler": 0.85,
    "surcos": 0.55,      "furrow": 0.55,
    "inundacion": 0.45,  "flood": 0.45,
    "default": 0.80,
}

# ---------------------------------------------------------------------------
# N-P-K requirements per ton of yield (kg nutrient / ton yield)
# Format: {crop: {N, P2O5, K2O, Ca, Mg, S}}
# ---------------------------------------------------------------------------
NPK_PER_TON = {
    "tomate":    {"N": 3.0, "P2O5": 1.0, "K2O": 5.0, "Ca": 1.5, "Mg": 0.5, "S": 0.4},
    "papa":      {"N": 4.0, "P2O5": 1.5, "K2O": 6.0, "Ca": 0.3, "Mg": 0.4, "S": 0.3},
    "maiz":      {"N": 18.0, "P2O5": 8.0, "K2O": 5.0, "Ca": 2.0, "Mg": 2.0, "S": 1.5},
    "corn":      {"N": 18.0, "P2O5": 8.0, "K2O": 5.0, "Ca": 2.0, "Mg": 2.0, "S": 1.5},
    "trigo":     {"N": 22.0, "P2O5": 8.0, "K2O": 6.0, "Ca": 1.5, "Mg": 1.5, "S": 1.5},
    "soya":      {"N": 70.0, "P2O5": 16.0, "K2O": 20.0, "Ca": 3.5, "Mg": 2.5, "S": 2.5},
    "cebolla":   {"N": 2.5, "P2O5": 0.8, "K2O": 3.0, "Ca": 0.5, "Mg": 0.3, "S": 0.3},
    "ajo":       {"N": 3.5, "P2O5": 1.2, "K2O": 4.0, "Ca": 0.5, "Mg": 0.4, "S": 0.4},
    "pimiento":  {"N": 3.5, "P2O5": 1.0, "K2O": 5.5, "Ca": 1.2, "Mg": 0.5, "S": 0.4},
    "lechuga":   {"N": 2.0, "P2O5": 0.8, "K2O": 3.5, "Ca": 0.8, "Mg": 0.2, "S": 0.2},
    "fresa":     {"N": 4.0, "P2O5": 1.5, "K2O": 6.0, "Ca": 1.0, "Mg": 0.5, "S": 0.5},
    "default":   {"N": 3.5, "P2O5": 1.2, "K2O": 4.5, "Ca": 1.0, "Mg": 0.4, "S": 0.4},
}

# Stage name normalization
STAGE_ALIASES = {
    "inicial": "initial",
    "initial": "initial",
    "inicio": "initial",
    "desarrollo": "development",
    "development": "development",
    "crecimiento": "development",
    "media_estacion": "mid_season",
    "mid_season": "mid_season",
    "media": "mid_season",
    "maduracion": "late_season",
    "late_season": "late_season",
    "maduracion_cosecha": "late_season",
    "cosecha": "late_season",
    # Vine phenology. Veraison marks the mid-season plateau (Kc ~ 0.70 for wine
    # grape); without these, "envero" fell through to the default and was priced
    # as mid_season by accident rather than by design.
    "brotacion": "initial",
    "budbreak": "initial",
    "bud_break": "initial",
    "floracion": "development",
    "flowering": "development",
    "cuaja": "development",
    "fruit_set": "development",
    "envero": "development",
    "veraison": "development",
    "pinta": "development",
}

# Intermediate stages that sit between two tabulated ones. The fraction is how far
# through the bracketing stage they fall, so Kc interpolates instead of snapping to a
# table entry: grapevine veraison lands at 0.60 + (0.85 - 0.60) * 0.4 = 0.70.
STAGE_PROGRESS = {
    "envero": 0.4,
    "veraison": 0.4,
    "pinta": 0.4,
    "cuaja": 0.5,
    "fruit_set": 0.5,
}

# Ordered stages, used to interpolate Kc between the tabulated values.
STAGE_ORDER = ["initial", "development", "mid_season", "late_season"]


def interpolate_kc(kc_values: dict, stage: str, progress: float = 0.0) -> float:
    """Kc for a stage, linearly interpolated towards the next one.

    FAO-56 tabulates Kc at stage midpoints; between them it varies linearly.
    `progress` is how far the crop is through `stage` (0.0 = start, 1.0 = about
    to enter the next stage). progress=0 reproduces the plain table lookup, so
    callers that do not track progress are unaffected.
    """
    if stage not in STAGE_ORDER:
        stage = "mid_season"
    kc_here = kc_values.get(stage, kc_values["mid_season"])
    progress = max(0.0, min(1.0, float(progress or 0.0)))
    idx = STAGE_ORDER.index(stage)
    if progress == 0.0 or idx == len(STAGE_ORDER) - 1:
        return round(kc_here, 3)
    kc_next = kc_values.get(STAGE_ORDER[idx + 1], kc_here)
    return round(kc_here + (kc_next - kc_here) * progress, 3)


class AgroAgent:
    def __init__(self):
        # LLM providers in priority order; skip any without an API key.
        self._providers = []
        if settings.CEREBRAS_API_KEY:
            self._providers.append({
                "name": "cerebras",
                "client": AsyncOpenAI(base_url="https://api.cerebras.ai/v1", api_key=settings.CEREBRAS_API_KEY),
                "model": CEREBRAS_MODEL,
            })
        if settings.GROQ_API_KEY:
            self._providers.append({
                "name": "groq",
                "client": AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=settings.GROQ_API_KEY),
                "model": GROQ_MODEL,
            })
        self.satellite_service = EarthEngineService(
            credentials_path=settings.GEE_CREDENTIALS_PATH,
            project_id=settings.GEE_PROJECT_ID,
        )

    async def _create_completion(self, **kwargs):
        """
        Call chat.completions.create across providers with fallback.
        Retries up to 3× on RateLimitError (linear backoff); aborts on auth
        errors; falls through to the next provider on any other error.
        `stream=True` returns the stream object of the first provider whose
        create() call succeeds (errors before the first chunk trigger fallback).
        """
        if not self._providers:
            raise RuntimeError("No LLM provider configured (missing CEREBRAS_API_KEY / GROQ_API_KEY)")

        last_err = None
        for provider in self._providers:
            for attempt in range(1, 4):
                try:
                    return await provider["client"].chat.completions.create(model=provider["model"], **kwargs)
                except RateLimitError as e:
                    last_err = e
                    if attempt < 3:
                        await asyncio.sleep(attempt * 2)
                        continue
                    break  # exhausted retries → next provider
                except (AuthenticationError, PermissionDeniedError) as e:
                    # Bad credentials → config problem, not availability. Abort.
                    raise
                except Exception as e:
                    last_err = e
                    logger.warning(f"LLM provider {provider['name']} failed: {e}")
                    break  # next provider
        raise last_err or RuntimeError("All LLM providers failed")

    @staticmethod
    def _build_system(language: Optional[str]) -> str:
        names = {"en": "English", "es": "Spanish (Español)", "pt": "Portuguese (Português)"}
        if language and language in names:
            return SYSTEM_PROMPT + (
                f"\n\n## CRITICAL LANGUAGE RULE\n"
                f"The user interface is set to **{names[language]}**. "
                f"Reply ENTIRELY in {names[language]} — every sentence, every question, every word. "
                f"Do NOT mix languages."
            )
        return SYSTEM_PROMPT + (
            "\n\n## LANGUAGE RULE\n"
            "Detect the language of the user's most recent message and reply in that exact language. "
            "Never mix languages within a single response."
        )

    async def chat(self, message: str, conversation_id: str, user_id: str, db, language: Optional[str] = None) -> dict:
        """
        Main chat method. Loads history, runs agentic loop, saves messages.
        Returns dict with 'response' text and 'tools_used' list.
        """
        effective_system = self._build_system(language)

        history = await self._load_history(conversation_id, db)
        contents = [{"role": "system", "content": effective_system}] + history

        await self._save_message(conversation_id, "user", message, db)
        contents.append({"role": "user", "content": message})

        tools_used = []
        iterations = 0
        final_response = ""

        while iterations < 10:
            iterations += 1
            try:
                response = await self._create_completion(
                    messages=contents,
                    tools=GROQ_TOOLS,
                    tool_choice="auto",
                    max_tokens=1024,
                )
            except Exception as e:
                logger.error(f"LLM API error: {e}")
                final_response = (
                    "Lo siento, ocurrió un error al procesar tu consulta. "
                    "Por favor intenta nuevamente en unos momentos."
                )
                break

            msg = response.choices[0].message
            tool_calls = msg.tool_calls or []
            final_response = msg.content or ""

            if not tool_calls:
                await self._save_message(conversation_id, "assistant", final_response, db)
                break

            # Add assistant turn with tool_calls
            contents.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            })

            tool_calls_data = []
            for tc in tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    tool_args = {}
                tools_used.append(tool_name)
                logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

                tool_result_str = await self._execute_tool(tool_name, tool_args)
                tool_calls_data.append({
                    "id": tc.id,
                    "name": tool_name,
                    "input": tool_args,
                    "result": tool_result_str,
                })
                contents.append({"role": "tool", "tool_call_id": tc.id, "content": tool_result_str})

            inter = final_response or "[Consultando herramientas...]"
            await self._save_message(
                conversation_id, "assistant", inter, db,
                tool_calls=tool_calls_data,
            )

        if not final_response:
            final_response = "Lo siento, no pude completar la respuesta. Por favor intenta nuevamente."
            await self._save_message(conversation_id, "assistant", final_response, db)

        try:
            db.table("conversations").update(
                {"updated_at": "now()"}
            ).eq("id", conversation_id).execute()
        except Exception:
            pass

        return {
            "response": final_response,
            "tools_used": tools_used,
        }

    async def chat_stream(
        self, message: str, conversation_id: str, user_id: str, db, language: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """
        Streaming version of chat(). Yields SSE-compatible dicts:
          {"type": "tool_start", "tool": "..."}
          {"type": "text",       "content": "..."}   ← streamed tokens
          {"type": "tool_end",   "tool": "..."}
          {"type": "done",       "conversation_id": "...", "tools_used": [...]}
        """
        effective_system = self._build_system(language)

        history = await self._load_history(conversation_id, db)
        contents = [{"role": "system", "content": effective_system}] + history
        await self._save_message(conversation_id, "user", message, db)
        contents.append({"role": "user", "content": message})

        tools_used: list[str] = []
        iterations = 0
        full_response = ""

        while iterations < 10:
            iterations += 1
            text_accum = ""
            tc_accum: dict = {}

            try:
                stream = await self._create_completion(
                    messages=contents,
                    tools=GROQ_TOOLS,
                    tool_choice="auto",
                    stream=True,
                    max_tokens=1024,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        text_accum += delta.content
                        yield {"type": "text", "content": delta.content}
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            if tc.index not in tc_accum:
                                tc_accum[tc.index] = {"id": "", "name": "", "args": ""}
                            if tc.id:
                                tc_accum[tc.index]["id"] = tc.id
                            if tc.function and tc.function.name:
                                tc_accum[tc.index]["name"] = tc.function.name
                            if tc.function and tc.function.arguments:
                                tc_accum[tc.index]["args"] += tc.function.arguments
            except Exception as e:
                logger.error(f"Groq stream error: {e}")
                yield {"type": "text", "content": "\n\nError al procesar la consulta. Intenta nuevamente."}
                break

            function_calls = list(tc_accum.values())
            if not function_calls:
                full_response = text_accum
                await self._save_message(conversation_id, "assistant", full_response, db)
                break

            # Add assistant turn with tool_calls
            contents.append({
                "role": "assistant",
                "content": text_accum or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["args"]},
                    }
                    for tc in function_calls
                ],
            })

            tool_calls_data = []
            for tc in function_calls:
                tool_name = tc["name"]
                tools_used.append(tool_name)

                yield {"type": "tool_start", "tool": tool_name}
                try:
                    tool_args = json.loads(tc["args"] or "{}")
                except Exception:
                    tool_args = {}
                tool_result_str = await self._execute_tool(tool_name, tool_args)
                yield {"type": "tool_end", "tool": tool_name}

                tool_calls_data.append({
                    "id": tc["id"],
                    "name": tool_name,
                    "input": tool_args,
                    "result": tool_result_str,
                })
                contents.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result_str})

            inter = text_accum or "[Consultando herramientas...]"
            await self._save_message(
                conversation_id, "assistant", inter, db,
                tool_calls=tool_calls_data,
            )

        if not full_response:
            full_response = "No pude completar la respuesta. Intenta nuevamente."
            await self._save_message(conversation_id, "assistant", full_response, db)

        try:
            db.table("conversations").update({"updated_at": "now()"}).eq("id", conversation_id).execute()
        except Exception:
            pass

        yield {"type": "done", "conversation_id": conversation_id, "tools_used": tools_used}

    async def _load_history(self, conversation_id: str, db) -> list:
        """
        Load last 20 messages from Supabase and convert to OpenAI/Groq messages format.
        Note: system message is prepended separately; this returns only user/assistant/tool turns.
        """
        try:
            result = (
                db.table("messages")
                .select("role, content, tool_calls, created_at")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)
                .limit(20)
                .execute()
            )
            messages = []
            for row in result.data:
                role = row["role"]
                content = row.get("content", "")
                tool_calls = row.get("tool_calls")

                if role == "user":
                    if content:
                        messages.append({"role": "user", "content": content})
                elif role == "assistant":
                    if tool_calls:
                        # Reconstruct assistant turn with tool_calls in OpenAI format
                        clean_content = content if content and content.strip() not in ("[Consultando herramientas...]", "") else None
                        messages.append({
                            "role": "assistant",
                            "content": clean_content,
                            "tool_calls": [
                                {
                                    "id": tc.get("id", f"call_{tc['name']}"),
                                    "type": "function",
                                    "function": {
                                        "name": tc["name"],
                                        "arguments": json.dumps(tc.get("input", {})),
                                    },
                                }
                                for tc in tool_calls
                            ],
                        })
                        # Add tool results as tool messages
                        for tc in tool_calls:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.get("id", f"call_{tc['name']}"),
                                "content": tc.get("result", "{}"),
                            })
                    else:
                        if content:
                            messages.append({"role": "assistant", "content": content})
            return messages
        except Exception as e:
            logger.error(f"Error loading conversation history: {e}")
            return []

    async def _save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        db,
        tool_calls: Optional[list] = None,
    ):
        """Save a message to the Supabase messages table."""
        try:
            record = {
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
            }
            if tool_calls:
                record["tool_calls"] = tool_calls
            db.table("messages").insert(record).execute()
        except Exception as e:
            logger.error(f"Error saving message to DB: {e}")

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """
        Route tool call to the appropriate service and return JSON string result.
        """
        try:
            if tool_name == "get_climate_data":
                result = await get_climate_data(
                    latitude=tool_input["latitude"],
                    longitude=tool_input["longitude"],
                    days=tool_input.get("days_forecast", 7),
                )

            elif tool_name == "get_ndvi_data":
                result = await self.satellite_service.get_ndvi(
                    lat=tool_input["latitude"],
                    lng=tool_input["longitude"],
                    radius_m=tool_input.get("radius_m", 500),
                    date_from=tool_input.get("date_from", ""),
                    date_to=tool_input.get("date_to", ""),
                    source=tool_input.get("source", "sentinel2"),
                )

            elif tool_name == "analyze_soil_report":
                result = self._analyze_soil(
                    analysis_data=tool_input.get("analysis_data", {}),
                    crop_type=tool_input.get("crop_type", ""),
                )

            elif tool_name == "analyze_foliar_report":
                result = self._analyze_foliar(
                    analysis_data=tool_input.get("analysis_data", {}),
                    crop_type=tool_input.get("crop_type", ""),
                    growth_stage=tool_input.get("growth_stage", ""),
                )

            elif tool_name == "calculate_irrigation_plan":
                result = self._calculate_irrigation(tool_input)

            elif tool_name == "calculate_fertilization_plan":
                result = self._calculate_fertilization(tool_input)

            elif tool_name == "search_inia_biblioteca":
                result = search_inia_biblioteca(
                    query=tool_input["query"],
                    max_results=min(int(tool_input.get("max_results", 5)), 10),
                )

            elif tool_name == "search_openalex":
                result = search_openalex(
                    query=tool_input["query"],
                    max_results=min(int(tool_input.get("max_results", 5)), 10),
                    year_from=tool_input.get("year_from", 2010),
                )

            elif tool_name == "search_inia_rag":
                result = search_inia_rag(
                    query=tool_input["query"],
                    top_k=min(int(tool_input.get("top_k", 5)), 10),
                )

            elif tool_name == "search_agris":
                result = search_agris(
                    query=tool_input["query"],
                    max_results=min(int(tool_input.get("max_results", 5)), 10),
                    year_from=tool_input.get("year_from"),
                )

            elif tool_name == "get_faostat_data":
                result = get_faostat_data(
                    crop=tool_input["crop"],
                    country=tool_input.get("country", "world"),
                    element=tool_input.get("element", "yield"),
                    year_from=int(tool_input.get("year_from", 2015)),
                    year_to=int(tool_input.get("year_to", 2023)),
                )

            else:
                result = {"error": f"Herramienta desconocida: {tool_name}"}

            return json.dumps(result, ensure_ascii=False, default=str)

        except Exception as e:
            logger.error(f"Tool execution error ({tool_name}): {e}")
            return json.dumps({"error": f"Error ejecutando {tool_name}: {str(e)}"})

    # ---------------------------------------------------------------------------
    # Soil analysis
    # ---------------------------------------------------------------------------
    def _analyze_soil(self, analysis_data: dict, crop_type: str) -> dict:
        """Interpret soil parameters and generate agronomic recommendations."""
        interpretation = {}
        recommendations = []
        alerts = []

        # pH
        ph = analysis_data.get("pH") or analysis_data.get("ph")
        if ph is not None:
            ph = float(ph)
            if ph < 5.0:
                status = "Muy ácido"
                alerts.append(f"pH {ph} — Muy ácido. Alta toxicidad de Al y Mn posible.")
                recommendations.append(
                    f"Encalar para elevar pH a 6.0-6.5: aplicar 2-4 t/ha de cal agrícola (CaCO3) "
                    f"o 1-2 t/ha de cal dolomita. Incorporar al suelo 30 días antes de siembra."
                )
            elif ph < 5.5:
                status = "Ácido"
                recommendations.append(
                    f"pH moderadamente ácido ({ph}). Aplicar 1-2 t/ha de cal dolomita para alcanzar pH 6.0."
                )
            elif ph <= 6.5:
                status = "Ligeramente ácido a neutro (ideal)"
            elif ph <= 7.0:
                status = "Neutro"
            elif ph <= 7.5:
                status = "Ligeramente alcalino"
                recommendations.append(
                    f"pH {ph} — Ligeramente alcalino. Posible deficiencia de micronutrientes (Fe, Mn, Zn, B). "
                    f"Aplicar azufre elemental 200-400 kg/ha para bajar pH gradualmente."
                )
            elif ph <= 8.0:
                status = "Alcalino"
                alerts.append(f"pH {ph} — Alcalino. Alta inmovilización de P, Fe, Mn, Zn, Cu, B.")
                recommendations.append(
                    f"pH elevado ({ph}). Aplicar 500-800 kg/ha de azufre elemental + yeso (CaSO4) 1-2 t/ha. "
                    f"Usar fertilizantes acidificantes (sulfato de amonio). Aplicar micronutrientes quelados."
                )
            else:
                status = "Muy alcalino — condición severa"
                alerts.append(f"pH {ph} — Extremadamente alcalino. Considerar enmiendas estructurales.")
            interpretation["pH"] = {"value": ph, "status": status}

        # CE (Conductividad Eléctrica)
        ce = analysis_data.get("CE") or analysis_data.get("EC") or analysis_data.get("ce")
        if ce is not None:
            ce = float(ce)
            if ce < 1.0:
                status = "Normal — sin salinidad"
            elif ce < 2.0:
                status = "Leve salinidad — cultivos sensibles pueden verse afectados"
                recommendations.append(
                    f"CE {ce} dS/m — Salinidad leve. Monitorear cultivos sensibles (fresa, lechuga). "
                    f"Mejorar drenaje y aplicar lavados de sales si aumenta."
                )
            elif ce < 4.0:
                status = "Salinidad moderada — afecta mayoría de cultivos"
                alerts.append(f"CE {ce} dS/m — Salinidad moderada. Rendimiento comprometido.")
                recommendations.append(
                    f"CE elevada ({ce} dS/m). Aplicar lavados de sales (lámina 200-300 mm). "
                    f"Usar variedades tolerantes a salinidad. Aumentar frecuencia de riego para mantener humedad alta."
                )
            else:
                status = "Salinidad alta — daño severo en la mayoría de cultivos"
                alerts.append(f"CE {ce} dS/m — Salinidad ALTA. Urgente manejo de sales.")
                recommendations.append(
                    f"CE crítica ({ce} dS/m). Realizar lavados intensivos (400-600 mm de agua). "
                    f"Solo cultivar especies halófitas o muy tolerantes hasta reducir CE < 2 dS/m."
                )
            interpretation["CE"] = {"value": ce, "unit": "dS/m", "status": status}

        # Materia Orgánica
        mo = analysis_data.get("MO") or analysis_data.get("mo") or analysis_data.get("materia_organica")
        if mo is not None:
            mo = float(mo)
            if mo < 1.0:
                status = "Muy bajo"
                recommendations.append(
                    f"MO muy baja ({mo}%). Incorporar compost 10-20 t/ha o estiércol maduro 15-25 t/ha. "
                    f"Implementar labranza mínima y rotación con leguminosas."
                )
            elif mo < 2.0:
                status = "Bajo"
                recommendations.append(
                    f"MO baja ({mo}%). Aplicar compost 5-10 t/ha anualmente. Reducir labranza."
                )
            elif mo < 3.5:
                status = "Adecuado"
            elif mo < 5.0:
                status = "Alto — bueno"
            else:
                status = "Muy alto"
            interpretation["MO"] = {"value": mo, "unit": "%", "status": status}

        # Fósforo
        p = analysis_data.get("P") or analysis_data.get("fosforo")
        if p is not None:
            p = float(p)
            if p < 10:
                status = "Deficiente"
                recommendations.append(
                    f"P muy bajo ({p} ppm). Aplicar 150-200 kg/ha de DAP (18-46-0) o 200-300 kg/ha de superfosfato triple. "
                    f"Incorporar al suelo antes de siembra."
                )
            elif p < 20:
                status = "Bajo — se recomienda aplicación"
                recommendations.append(
                    f"P bajo ({p} ppm). Aplicar 80-120 kg/ha de DAP o 100-150 kg/ha de superfosfato triple."
                )
            elif p < 40:
                status = "Adecuado"
            elif p < 60:
                status = "Alto — reducir aplicaciones de P"
            else:
                status = "Exceso — no aplicar P"
            interpretation["P"] = {"value": p, "unit": "ppm", "status": status}

        # Potasio
        k = analysis_data.get("K") or analysis_data.get("potasio")
        if k is not None:
            k = float(k)
            k_unit = "meq/100g"
            if k > 10:
                k_meq = k / 391.0  # ppm to meq/100g
                k_unit = "ppm"
            else:
                k_meq = k
            if k_meq < 0.15:
                status = "Deficiente"
                recommendations.append(
                    f"K deficiente. Aplicar 150-200 kg/ha de KCl (0-0-60) o 100-150 kg/ha de K2SO4. "
                    f"En fertirriego: KNO3 o KH2PO4."
                )
            elif k_meq < 0.30:
                status = "Bajo"
                recommendations.append(
                    f"K bajo. Aplicar 80-120 kg/ha de KCl o K2SO4 al suelo."
                )
            elif k_meq < 0.80:
                status = "Adecuado"
            else:
                status = "Alto — posible antagonismo con Mg y Ca"
            interpretation["K"] = {"value": k, "unit": k_unit, "status": status}

        # Calcio
        ca = analysis_data.get("Ca") or analysis_data.get("calcio")
        if ca is not None:
            ca = float(ca)
            if ca < 2.0:
                status = "Deficiente"
                recommendations.append(
                    f"Ca bajo. Aplicar yeso agrícola 500-800 kg/ha o cal dolomita si pH también es bajo."
                )
            elif ca < 5.0:
                status = "Bajo"
            elif ca < 15.0:
                status = "Adecuado"
            else:
                status = "Alto"
            interpretation["Ca"] = {"value": ca, "unit": "meq/100g", "status": status}

        # Magnesio
        mg = analysis_data.get("Mg") or analysis_data.get("magnesio")
        if mg is not None:
            mg = float(mg)
            if mg < 0.5:
                status = "Deficiente"
                recommendations.append(
                    f"Mg deficiente. Aplicar sulfato de magnesio (kieserita) 50-100 kg/ha o cal dolomita."
                )
            elif mg < 1.0:
                status = "Bajo"
            elif mg < 4.0:
                status = "Adecuado"
            else:
                status = "Alto"
            interpretation["Mg"] = {"value": mg, "unit": "meq/100g", "status": status}

        # Cálculo de relaciones catiónicas si hay datos suficientes
        if ca is not None and mg is not None and k is not None:
            ca_v = float(analysis_data.get("Ca", ca))
            mg_v = float(analysis_data.get("Mg", mg))
            k_v = float(analysis_data.get("K", k))
            if k_v < 5:
                k_meq_v = k_v
            else:
                k_meq_v = k_v / 391.0
            if mg_v > 0 and k_meq_v > 0:
                ca_mg = round(ca_v / mg_v, 1)
                ca_k = round(ca_v / k_meq_v, 1)
                mg_k = round(mg_v / k_meq_v, 1)
                interpretation["relaciones_cationicas"] = {
                    "Ca/Mg": {"value": ca_mg, "ideal": "3-10", "status": "OK" if 3 <= ca_mg <= 10 else "Fuera de rango"},
                    "Ca/K": {"value": ca_k, "ideal": "10-25", "status": "OK" if 10 <= ca_k <= 25 else "Fuera de rango"},
                    "Mg/K": {"value": mg_k, "ideal": "2-12", "status": "OK" if 2 <= mg_k <= 12 else "Fuera de rango"},
                }

        return {
            "crop_type": crop_type,
            "interpretation": interpretation,
            "alerts": alerts,
            "recommendations": recommendations,
            "summary": f"Análisis completado para {crop_type}. Se encontraron {len(alerts)} alertas y {len(recommendations)} recomendaciones.",
        }

    # ---------------------------------------------------------------------------
    # Foliar analysis
    # ---------------------------------------------------------------------------
    def _analyze_foliar(self, analysis_data: dict, crop_type: str, growth_stage: str = "") -> dict:
        """Interpret foliar analysis and generate correction recommendations."""
        SUFFICIENCY = {
            "N":  {"min": 2.5, "max": 4.5, "unit": "%", "critical_low": 2.0},
            "P":  {"min": 0.20, "max": 0.50, "unit": "%", "critical_low": 0.15},
            "K":  {"min": 2.0, "max": 4.5, "unit": "%", "critical_low": 1.5},
            "Ca": {"min": 1.0, "max": 3.5, "unit": "%", "critical_low": 0.8},
            "Mg": {"min": 0.25, "max": 0.80, "unit": "%", "critical_low": 0.20},
            "S":  {"min": 0.20, "max": 0.50, "unit": "%", "critical_low": 0.15},
            "B":  {"min": 25, "max": 75, "unit": "ppm", "critical_low": 15},
            "Cu": {"min": 5, "max": 20, "unit": "ppm", "critical_low": 3},
            "Fe": {"min": 50, "max": 300, "unit": "ppm", "critical_low": 35},
            "Mn": {"min": 20, "max": 200, "unit": "ppm", "critical_low": 15},
            "Zn": {"min": 20, "max": 100, "unit": "ppm", "critical_low": 15},
        }

        CROP_ADJUSTMENTS = {
            "tomate":   {"N": {"min": 3.0, "max": 4.5}, "K": {"min": 3.0, "max": 5.0}, "Ca": {"min": 1.5, "max": 3.0}},
            "papa":     {"N": {"min": 3.0, "max": 4.5}, "K": {"min": 2.5, "max": 4.5}},
            "maiz":     {"N": {"min": 2.8, "max": 4.0}, "K": {"min": 1.5, "max": 3.5}},
            "cebolla":  {"N": {"min": 2.5, "max": 4.0}, "S":  {"min": 0.25, "max": 0.60}},
        }

        crop_adj = CROP_ADJUSTMENTS.get(crop_type.lower(), {})
        for param, adj in crop_adj.items():
            if param in SUFFICIENCY:
                SUFFICIENCY[param] = {**SUFFICIENCY[param], **adj}

        interpretation = {}
        deficiencies = []
        excesses = []
        corrections_urgent = []
        corrections_medterm = []

        for param, ref in SUFFICIENCY.items():
            val = analysis_data.get(param)
            if val is None:
                continue
            val = float(val)
            min_v = ref["min"]
            max_v = ref["max"]
            crit = ref.get("critical_low", min_v * 0.8)
            unit = ref["unit"]

            if val < crit:
                status = "DEFICIENCIA CRÍTICA"
                deficiencies.append(param)
                foliar_dose = self._foliar_correction_dose(param)
                corrections_urgent.append(
                    f"**{param} CRÍTICO ({val}{unit})**: {foliar_dose} — Aplicar en las próximas 48-72h."
                )
            elif val < min_v:
                status = "Bajo — deficiencia leve"
                deficiencies.append(param)
                foliar_dose = self._foliar_correction_dose(param)
                corrections_medterm.append(
                    f"**{param} bajo ({val}{unit})**: {foliar_dose} — Aplicar esta semana."
                )
            elif val > max_v * 1.5:
                status = "Exceso — posible toxicidad"
                excesses.append(param)
            elif val > max_v:
                status = "Alto — monitorear"
            else:
                status = "Dentro del rango de suficiencia"
            interpretation[param] = {"value": val, "unit": unit, "min": min_v, "max": max_v, "status": status}

        return {
            "crop_type": crop_type,
            "growth_stage": growth_stage or "No especificado",
            "interpretation": interpretation,
            "deficiencies": deficiencies,
            "excesses": excesses,
            "corrections_urgent": corrections_urgent,
            "corrections_medium_term": corrections_medterm,
            "overall_nutrition_status": (
                "Crítico" if len(corrections_urgent) >= 3
                else "Con deficiencias significativas" if deficiencies
                else "Adecuado"
            ),
        }

    def _foliar_correction_dose(self, nutrient: str) -> str:
        """Return standard foliar correction product and dose."""
        corrections = {
            "N": "Ureafol 46% a 3-5 kg/ha o urea técnica 2-3 kg/ha en 200L agua",
            "P": "Fosfato monopotásico (MKP 0-52-34) 1-2 kg/ha en 200L agua",
            "K": "Nitrato de potasio (KNO3) 3-5 kg/ha o cloruro de potasio foliar 2-3 kg/ha",
            "Ca": "Nitrato de calcio 3-5 kg/ha o calcio boro foliar quelatado 1-2 L/ha",
            "Mg": "Sulfato de magnesio (Epsom salt) 3-5 kg/ha en 200L agua",
            "S": "Sulfato de magnesio 3-5 kg/ha o thiosulfato de potasio 1-2 L/ha",
            "B": "Borato de sodio o Solubor 0.5-1.0 kg/ha (no exceder 1 kg/ha)",
            "Cu": "Sulfato de cobre pentahidratado 0.3-0.5 kg/ha o Cu quelatado EDTA 200-400 g/ha",
            "Fe": "Sulfato ferroso 1-2 kg/ha + ácido cítrico 0.5 kg/ha, o Fe-EDDHA 200-400 g/ha",
            "Mn": "Sulfato de manganeso 1-2 kg/ha o Mn quelatado 200-400 g/ha",
            "Zn": "Sulfato de zinc 1-2 kg/ha o Zn quelatado EDTA 200-400 g/ha",
            "Mo": "Molibdato de amonio 50-100 g/ha en 200L agua",
        }
        return corrections.get(nutrient, f"Consultar producto quelatado de {nutrient}")

    # ---------------------------------------------------------------------------
    # Irrigation plan calculation
    # ---------------------------------------------------------------------------
    def _calculate_irrigation(self, params: dict) -> dict:
        """Calculate irrigation plan based on crop, soil, climate and system."""
        crop_type = params.get("crop_type", "default").lower()
        growth_stage_raw = params.get("growth_stage", "mid_season").lower()
        soil_type = params.get("soil_type", "franco").lower()
        area_ha = float(params.get("area_ha", 1.0))
        et0 = params.get("et0")
        climate_data = params.get("climate_data", {})
        irrigation_system = params.get("irrigation_system", "goteo").lower()

        growth_stage = STAGE_ALIASES.get(growth_stage_raw, "mid_season")

        kc_values = KC_TABLE.get(crop_type, KC_TABLE["default"])
        # stage_progress (0-1) shifts Kc linearly towards the next stage; absent it,
        # this is the plain tabulated value.
        stage_progress = params.get("stage_progress")
        if stage_progress is None:
            stage_progress = STAGE_PROGRESS.get(growth_stage_raw, 0.0)
        kc = interpolate_kc(kc_values, growth_stage, stage_progress)

        if et0 is None and climate_data:
            summary = climate_data.get("summary", {})
            et0 = summary.get("avg_et0_daily_mm")
        if et0 is None:
            et0 = 5.0

        etc_daily = round(et0 * kc, 2)

        awc = SOIL_AWC.get(soil_type, SOIL_AWC["default"])
        root_depth_m = self._root_depth(crop_type, growth_stage)
        total_awc_mm = awc * root_depth_m

        mad_fraction = 0.50
        net_irrigation_depth_mm = round(total_awc_mm * mad_fraction, 1)

        irrigation_interval_days = max(1, round(net_irrigation_depth_mm / etc_daily))

        efficiency = IRRIGATION_EFFICIENCY.get(irrigation_system, IRRIGATION_EFFICIENCY["default"])
        gross_irrigation_mm = round(net_irrigation_depth_mm / efficiency, 1)

        volume_m3_per_ha = round(gross_irrigation_mm * 10, 1)
        total_volume_m3 = round(volume_m3_per_ha * area_ha, 1)

        weekly_etc_mm = round(etc_daily * 7, 1)
        weekly_volume_m3_ha = round(weekly_etc_mm * 10 / efficiency, 1)

        emitter_flow_lh = 2.5
        emitters_per_ha = 10000
        if irrigation_system == "goteo":
            total_emitter_flow_m3h = (emitters_per_ha * emitter_flow_lh / 1000)
            application_hours = round(gross_irrigation_mm * 10 / total_emitter_flow_m3h, 2)
        else:
            application_hours = None

        schedule = []
        for day in range(1, 8):
            apply = (day % irrigation_interval_days == 0) or day == 1
            schedule.append({
                "day": day,
                "irrigate": apply,
                "volume_m3": total_volume_m3 if apply else 0,
                "duration_hours": application_hours if apply else 0,
            })

        return {
            "crop_type": crop_type,
            "growth_stage": growth_stage,
            "kc_coefficient": kc,
            "et0_daily_mm": et0,
            "etc_daily_mm": etc_daily,
            "soil_type": soil_type,
            "root_depth_m": root_depth_m,
            "available_water_capacity_mm": total_awc_mm,
            "irrigation_system": irrigation_system,
            "efficiency_pct": round(efficiency * 100, 0),
            "net_irrigation_depth_mm": net_irrigation_depth_mm,
            "gross_irrigation_depth_mm": gross_irrigation_mm,
            "irrigation_interval_days": irrigation_interval_days,
            "volume_per_ha_m3": volume_m3_per_ha,
            "total_volume_m3": total_volume_m3,
            "area_ha": area_ha,
            "weekly_water_requirement_mm": weekly_etc_mm,
            "weekly_volume_per_ha_m3": weekly_volume_m3_ha,
            "application_time_hours": application_hours,
            "weekly_schedule_example": schedule,
            "recommendations": [
                f"Regar cada {irrigation_interval_days} día(s) para {crop_type} en etapa {growth_stage_raw}.",
                f"Con ET0={et0} mm/día y Kc={kc}, el cultivo consume {etc_daily} mm/día.",
                f"Aplicar {gross_irrigation_mm} mm por riego (lámina bruta, incluye ineficiencia del {round((1-efficiency)*100)}%).",
                f"Volumen total por riego: {total_volume_m3} m³ para {area_ha} ha.",
                "Ajustar frecuencia según lluvias y monitoreo de humedad de suelo.",
                "Regar preferiblemente en horas de menor temperatura (mañana temprano o noche).",
            ],
        }

    def _root_depth(self, crop_type: str, growth_stage: str) -> float:
        """Return effective root depth in meters for crop/stage."""
        root_depths = {
            "tomate":   {"initial": 0.20, "development": 0.45, "mid_season": 0.70, "late_season": 0.70},
            "papa":     {"initial": 0.20, "development": 0.35, "mid_season": 0.50, "late_season": 0.50},
            "maiz":     {"initial": 0.20, "development": 0.50, "mid_season": 1.00, "late_season": 1.00},
            "trigo":    {"initial": 0.20, "development": 0.60, "mid_season": 1.00, "late_season": 1.00},
            "cebolla":  {"initial": 0.15, "development": 0.30, "mid_season": 0.40, "late_season": 0.40},
            "lechuga":  {"initial": 0.15, "development": 0.20, "mid_season": 0.30, "late_season": 0.30},
            "default":  {"initial": 0.20, "development": 0.40, "mid_season": 0.60, "late_season": 0.60},
        }
        depths = root_depths.get(crop_type, root_depths["default"])
        return depths.get(growth_stage, depths["mid_season"])

    # ---------------------------------------------------------------------------
    # Fertilization plan calculation
    # ---------------------------------------------------------------------------
    def _calculate_fertilization(self, params: dict) -> dict:
        """Calculate N-P-K fertilization program based on crop and yield target."""
        crop_type = params.get("crop_type", "default").lower()
        yield_target = float(params.get("yield_target", 30.0))
        soil_analysis = params.get("soil_analysis", {})
        area_ha = float(params.get("area_ha", 1.0))
        irrigation_type = params.get("irrigation_type", "goteo").lower()
        cycle_days = int(params.get("cycle_days", 120))

        npk_req = NPK_PER_TON.get(crop_type, NPK_PER_TON["default"])
        n_total = round(npk_req["N"] * yield_target, 1)
        p2o5_total = round(npk_req["P2O5"] * yield_target, 1)
        k2o_total = round(npk_req["K2O"] * yield_target, 1)
        ca_total = round(npk_req["Ca"] * yield_target, 1)
        mg_total = round(npk_req["Mg"] * yield_target, 1)
        s_total = round(npk_req["S"] * yield_target, 1)

        adjustments = {}
        if soil_analysis:
            p_soil = soil_analysis.get("P")
            k_soil = soil_analysis.get("K")
            if p_soil is not None:
                p_soil = float(p_soil)
                if p_soil > 40:
                    p2o5_total = round(p2o5_total * 0.5, 1)
                    adjustments["P2O5"] = f"Reducido 50% por P alto en suelo ({p_soil} ppm)"
                elif p_soil > 20:
                    p2o5_total = round(p2o5_total * 0.75, 1)
                    adjustments["P2O5"] = f"Reducido 25% por P adecuado en suelo ({p_soil} ppm)"
            if k_soil is not None:
                k_soil = float(k_soil)
                k_meq = k_soil / 391.0 if k_soil > 5 else k_soil
                if k_meq > 0.5:
                    k2o_total = round(k2o_total * 0.6, 1)
                    adjustments["K2O"] = f"Reducido 40% por K adecuado en suelo"

        # N distribution across applications. The percentages within each
        # irrigation regime sum to 1.0 so that the scheduled N never exceeds the
        # total requirement (fertirrigation systems deliver the bulk of N through
        # the weekly injections, not through side-dress coverage applications).
        if irrigation_type in ("goteo", "aspersion"):
            n_base_pct = 0.10
            n_cov1_pct = 0.00
            n_cov2_pct = 0.00
            n_fertirriego_pct = 0.90
            fertirrigation_weeks = max(1, cycle_days // 7)
            n_per_week = round((n_total * n_fertirriego_pct) / fertirrigation_weeks, 1)
        else:
            n_base_pct = 0.30
            n_cov1_pct = 0.35
            n_cov2_pct = 0.35
            n_fertirriego_pct = 0.00
            fertirrigation_weeks = 0
            n_per_week = 0

        n_preplant = round(n_total * n_base_pct, 1)
        n_coverage1 = round(n_total * n_cov1_pct, 1)
        n_coverage2 = round(n_total * n_cov2_pct, 1)

        p_preplant = round(p2o5_total * 0.55, 1)
        k_preplant = round(k2o_total * 0.25, 1)
        k_coverage = round(k2o_total * 0.75, 1)

        urea_preplant = round(n_preplant / 0.46, 1)
        dap_preplant = round(p_preplant / 0.46, 1)
        kcl_preplant = round(k_preplant / 0.60, 1)

        micro_recommendations = [
            "Zinc (ZnSO4): 5-8 kg/ha al suelo o 1-2 aplicaciones foliares de 2 kg/ha de ZnSO4",
            "Boro (Solubor): 1-2 kg/ha foliar en inicio de floración",
            "Hierro (FeSO4 o Fe-EDTA): según análisis foliar; suelos alcalinos requieren quelatados",
        ]

        program = {
            "preplant_incorporation": {
                "timing": "7-14 días antes de trasplante/siembra",
                "products": [
                    {"product": "DAP (18-46-0)", "dose_kg_ha": dap_preplant, "nutrient_contribution": f"{round(dap_preplant*0.18,1)} kg N + {p_preplant} kg P2O5"},
                    {"product": "KCl (0-0-60)", "dose_kg_ha": kcl_preplant, "nutrient_contribution": f"{k_preplant} kg K2O"},
                    {"product": "Urea (46-0-0)", "dose_kg_ha": urea_preplant, "nutrient_contribution": f"{n_preplant} kg N"},
                ],
            },
            "coverage_application_1": {
                "timing": "30-40% del ciclo del cultivo",
                "products": (
                    ([{"product": "Urea (46-0-0)", "dose_kg_ha": round(n_coverage1 / 0.46, 1), "nutrient_contribution": f"{n_coverage1} kg N"}] if n_coverage1 > 0 else [])
                    + [{"product": "KNO3 (13-0-44)", "dose_kg_ha": round(k_coverage * 0.40 / 0.44, 1), "nutrient_contribution": f"K2O parcial"}]
                ),
            },
            "coverage_application_2": {
                "timing": "60-70% del ciclo (inicio de llenado de fruto/grano)",
                "products": (
                    ([{"product": "Urea (46-0-0)", "dose_kg_ha": round(n_coverage2 / 0.46, 1), "nutrient_contribution": f"{n_coverage2} kg N"}] if n_coverage2 > 0 else [])
                    + [{"product": "K2SO4 (0-0-50)", "dose_kg_ha": round(k_coverage * 0.60 / 0.50, 1), "nutrient_contribution": f"K2O parcial (con azufre)"}]
                ),
            },
        }

        if irrigation_type in ("goteo", "aspersion"):
            program["fertirrigation"] = {
                "timing": f"Semanal durante {fertirrigation_weeks} semanas",
                "n_per_week_kg_ha": n_per_week,
                "recommended_products": [
                    "Nitrato de calcio (15.5-0-0 + 26.5% CaO): 5-10 kg/ha/semana",
                    "Nitrato de potasio (13-0-44): 3-6 kg/ha/semana en etapa de fructificación",
                    "MAP (12-61-0): 1-2 kg/ha/semana en etapas iniciales",
                    "Sulfato de magnesio: 2-3 kg/ha/semana según análisis foliar",
                ],
                "note": "Inyectar en sistema con pH de solución 5.5-6.5. No mezclar Ca con SO4 o PO4.",
            }

        return {
            "crop_type": crop_type,
            "yield_target_t_ha": yield_target,
            "area_ha": area_ha,
            "cycle_days": cycle_days,
            "total_requirements_kg_ha": {
                "N": n_total,
                "P2O5": p2o5_total,
                "K2O": k2o_total,
                "Ca": ca_total,
                "Mg": mg_total,
                "S": s_total,
            },
            "total_requirements_entire_field_kg": {
                "N": round(n_total * area_ha, 1),
                "P2O5": round(p2o5_total * area_ha, 1),
                "K2O": round(k2o_total * area_ha, 1),
            },
            "soil_adjustments_applied": adjustments,
            "scheduled_nitrogen_kg_ha": round(
                n_preplant + n_coverage1 + n_coverage2 + n_per_week * fertirrigation_weeks, 1
            ),
            "application_program": program,
            "micronutrient_recommendations": micro_recommendations,
            "important_notes": [
                "Este programa es una guía inicial. Ajustar con análisis foliar periódicos (cada 15-21 días).",
                "Verificar compatibilidad de productos antes de mezclar en tanque.",
                "Las dosis de N son totales; distribuir según calendario de aplicaciones.",
                "Para fertirriego: monitorear CE de la solución nutritiva (máx. 2.5 dS/m).",
                "Calibrar equipos de aplicación para garantizar dosis correctas.",
            ],
        }

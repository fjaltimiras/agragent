import io
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Common soil analysis parameter patterns
SOIL_PARAM_PATTERNS = {
    "pH": r"pH\s*[:\-=]?\s*(\d+\.?\d*)",
    "CE": r"C[Ee][\s\.\(].*?(\d+\.?\d*)\s*(dS\/m|mmhos|mS\/cm)?",
    "EC": r"EC[\s\.\(].*?(\d+\.?\d*)\s*(dS\/m|mmhos|mS\/cm)?",
    "MO": r"M\.?O\.?|Materia\s+Org[aá]nica\s*[:\-=]?\s*(\d+\.?\d*)\s*%?",
    "N_total": r"N\s+[Tt]otal\s*[:\-=]?\s*(\d+\.?\d*)\s*%?",
    "N": r"(?:N|Nitr[oó]geno)\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg|%)?",
    "P": r"(?:P|F[oó]sforo)[\s\(].*?(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "K": r"(?:K|Potasio)\s*[:\-=]?\s*(\d+\.?\d*)\s*(meq|cmol|ppm|mg\/kg)?",
    "Ca": r"(?:Ca|Calcio)\s*[:\-=]?\s*(\d+\.?\d*)\s*(meq|cmol|ppm|mg\/kg)?",
    "Mg": r"(?:Mg|Magnesio)\s*[:\-=]?\s*(\d+\.?\d*)\s*(meq|cmol|ppm|mg\/kg)?",
    "Na": r"(?:Na|Sodio)\s*[:\-=]?\s*(\d+\.?\d*)\s*(meq|cmol|ppm|mg\/kg)?",
    "S": r"(?:S|Azufre)\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "B": r"(?:B|Boro)\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "Cu": r"(?:Cu|Cobre)\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "Fe": r"(?:Fe|Hierro)\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "Mn": r"(?:Mn|Manganeso)\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "Zn": r"(?:Zn|Zinc)\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "CIC": r"C\.?I\.?C\.?|CEC|Capacidad\s+de\s+Intercambio\s*[:\-=]?\s*(\d+\.?\d*)\s*(meq|cmol)?",
}

# Common foliar analysis parameter patterns
FOLIAR_PARAM_PATTERNS = {
    "N": r"N(?:itr[oó]geno)?\s*[:\-=]?\s*(\d+\.?\d*)\s*%?",
    "P": r"P(?:[oó]sforo|f[oó]sforo)?\s*[:\-=]?\s*(\d+\.?\d*)\s*%?",
    "K": r"K(?:potasio)?\s*[:\-=]?\s*(\d+\.?\d*)\s*%?",
    "Ca": r"Ca(?:lcio)?\s*[:\-=]?\s*(\d+\.?\d*)\s*%?",
    "Mg": r"Mg(?:nesio|agnesio)?\s*[:\-=]?\s*(\d+\.?\d*)\s*%?",
    "S": r"S(?:azufre|ulfuro)?\s*[:\-=]?\s*(\d+\.?\d*)\s*%?",
    "B": r"B(?:oro)?\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "Cu": r"Cu(?:bre|obre)?\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "Fe": r"Fe(?:rro|ierro)?\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "Mn": r"Mn(?:anganeso)?\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "Zn": r"Zn(?:inc)?\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
    "Mo": r"Mo(?:libdeno)?\s*[:\-=]?\s*(\d+\.?\d*)\s*(ppm|mg\/kg)?",
}


def _extract_parameters_from_text(text: str, patterns: dict) -> dict:
    """
    Attempt to extract parameter values from text using regex patterns.
    Returns dict of {param_name: {value, unit}}.
    """
    parameters = {}
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        for param_name, pattern in patterns.items():
            if param_name in parameters:
                continue
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                # Try to get the captured value
                groups = [g for g in match.groups() if g is not None]
                if groups:
                    # First group with a numeric value
                    for g in groups:
                        try:
                            value = float(g)
                            unit = groups[1] if len(groups) > 1 else _default_unit(param_name)
                            parameters[param_name] = {"value": value, "unit": unit}
                            break
                        except (ValueError, TypeError):
                            continue

    return parameters


def _default_unit(param_name: str) -> str:
    """Return the most common unit for a given parameter."""
    unit_map = {
        "pH": "unidades",
        "CE": "dS/m",
        "EC": "dS/m",
        "MO": "%",
        "N_total": "%",
        "N": "ppm",
        "P": "ppm",
        "K": "meq/100g",
        "Ca": "meq/100g",
        "Mg": "meq/100g",
        "Na": "meq/100g",
        "S": "ppm",
        "B": "ppm",
        "Cu": "ppm",
        "Fe": "ppm",
        "Mn": "ppm",
        "Zn": "ppm",
        "CIC": "meq/100g",
    }
    return unit_map.get(param_name, "")


def _assess_parse_confidence(parameters: dict, analysis_type: str) -> str:
    """Determine parse confidence based on number of key parameters found."""
    if analysis_type == "soil":
        key_params = ["pH", "P", "K", "Ca", "Mg"]
        found_key = sum(1 for p in key_params if p in parameters)
        total = len(parameters)
        if found_key >= 4 and total >= 8:
            return "high"
        elif found_key >= 2 and total >= 4:
            return "medium"
        else:
            return "low"
    elif analysis_type in ("foliar", "water"):
        key_params = ["N", "P", "K", "Ca", "Mg"]
        found_key = sum(1 for p in key_params if p in parameters)
        if found_key >= 4:
            return "high"
        elif found_key >= 2:
            return "medium"
        else:
            return "low"
    return "low"


def parse_pdf_analysis(file_bytes: bytes, analysis_type: str) -> dict:
    """
    Parse a PDF soil or foliar analysis using pdfplumber.
    Extracts text and searches for common agronomic parameter patterns.
    """
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
                # Also try extracting tables
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            row_text = " | ".join(str(cell) for cell in row if cell)
                            text_parts.append(row_text)

        full_text = "\n".join(text_parts)

        if not full_text.strip():
            return {
                "parameters": {},
                "raw_text": "",
                "analysis_type": analysis_type,
                "parse_confidence": "low",
                "error": "No se pudo extraer texto del PDF. El archivo puede ser una imagen escaneada.",
            }

        patterns = SOIL_PARAM_PATTERNS if analysis_type == "soil" else FOLIAR_PARAM_PATTERNS
        parameters = _extract_parameters_from_text(full_text, patterns)

        return {
            "parameters": parameters,
            "raw_text": full_text[:2000],
            "analysis_type": analysis_type,
            "parse_confidence": _assess_parse_confidence(parameters, analysis_type),
            "pages_parsed": len(text_parts),
        }

    except ImportError:
        return {
            "parameters": {},
            "raw_text": "",
            "analysis_type": analysis_type,
            "parse_confidence": "low",
            "error": "pdfplumber no está instalado. Ejecuta: pip install pdfplumber",
        }
    except Exception as e:
        logger.error(f"Error parsing PDF: {str(e)}")
        return {
            "parameters": {},
            "raw_text": "",
            "analysis_type": analysis_type,
            "parse_confidence": "low",
            "error": f"Error al procesar el PDF: {str(e)}",
        }


def parse_excel_analysis(file_bytes: bytes, analysis_type: str) -> dict:
    """
    Parse an Excel soil or foliar analysis using openpyxl.
    Looks for rows with parameter name, value, and unit columns.
    """
    try:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        parameters = {}
        text_lines = []

        for sheet in wb.worksheets:
            rows = list(sheet.iter_rows(values_only=True))
            # Try to detect which column has parameter names, values, units
            for row in rows:
                if not row or all(cell is None for cell in row):
                    continue

                row_str = " | ".join(str(c) for c in row if c is not None)
                text_lines.append(row_str)

                # Heuristic: look for rows where col 0 is a string (param name)
                # and one of the next columns is a number (value)
                non_none = [c for c in row if c is not None]
                if len(non_none) >= 2:
                    first = non_none[0]
                    # Try to find the first numeric column
                    numeric_val = None
                    unit_val = None
                    for i, cell in enumerate(non_none[1:], 1):
                        try:
                            numeric_val = float(cell)
                            # Next column might be the unit
                            if i + 1 < len(non_none):
                                unit_val = str(non_none[i + 1])
                            break
                        except (ValueError, TypeError):
                            continue

                    if numeric_val is not None and isinstance(first, str):
                        param_name_clean = str(first).strip()
                        # Match against known parameter names
                        for known_param in list(SOIL_PARAM_PATTERNS.keys()) + list(FOLIAR_PARAM_PATTERNS.keys()):
                            if known_param.lower() in param_name_clean.lower():
                                if known_param not in parameters:
                                    parameters[known_param] = {
                                        "value": numeric_val,
                                        "unit": unit_val or _default_unit(known_param),
                                    }
                                break

        full_text = "\n".join(text_lines)

        # If we didn't get enough from structural parsing, try regex on text
        if len(parameters) < 3:
            patterns = SOIL_PARAM_PATTERNS if analysis_type == "soil" else FOLIAR_PARAM_PATTERNS
            text_params = _extract_parameters_from_text(full_text, patterns)
            for k, v in text_params.items():
                if k not in parameters:
                    parameters[k] = v

        return {
            "parameters": parameters,
            "raw_text": full_text[:2000],
            "analysis_type": analysis_type,
            "parse_confidence": _assess_parse_confidence(parameters, analysis_type),
            "sheets_parsed": len(wb.worksheets),
        }

    except ImportError:
        return {
            "parameters": {},
            "raw_text": "",
            "analysis_type": analysis_type,
            "parse_confidence": "low",
            "error": "openpyxl no está instalado. Ejecuta: pip install openpyxl",
        }
    except Exception as e:
        logger.error(f"Error parsing Excel: {str(e)}")
        return {
            "parameters": {},
            "raw_text": "",
            "analysis_type": analysis_type,
            "parse_confidence": "low",
            "error": f"Error al procesar el archivo Excel: {str(e)}",
        }


def detect_analysis_type(filename: str, content_preview: str = "") -> str:
    """
    Detect whether an analysis file is soil, foliar, or water based on
    filename and content preview.
    """
    filename_lower = filename.lower()
    content_lower = content_preview.lower()

    # Check filename first
    if any(kw in filename_lower for kw in ["suelo", "soil", "tierra", "edafico", "edafol"]):
        return "soil"
    if any(kw in filename_lower for kw in ["foliar", "hoja", "tejido", "leaf"]):
        return "foliar"
    if any(kw in filename_lower for kw in ["agua", "water", "riego", "hidro"]):
        return "water"

    # Check content
    if any(kw in content_lower for kw in ["análisis de suelo", "textura", "cic", "capacidad de intercambio"]):
        return "soil"
    if any(kw in content_lower for kw in ["análisis foliar", "tejido vegetal", "hoja muestreada"]):
        return "foliar"
    if any(kw in content_lower for kw in ["análisis de agua", "dureza", "alcalinidad", "sar"]):
        return "water"

    # Default to soil (most common)
    return "soil"

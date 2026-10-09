#!/usr/bin/env python3
"""
import_kml_fields.py — Siembra los KML de kml_riegos/ como "campos guardados"
del usuario INIA (user_id = web:inia) en la tabla Supabase `fields`, vía el
endpoint ya desplegado /api/fields.

Cada KML se convierte en UN campo, con la misma estructura GeoJSON que el
frontend (loadFieldFromGeoJSON en app.html) espera:

  geometry = {
    "type": "FeatureCollection",
    "features": [{
      "type": "Feature",
      "geometry": {"type": "Polygon", "coordinates": [[[lng,lat], ...]]},
      "properties": {"name": ..., "color": ..., "crop_type": ...}
    }]
  }

Es re-ejecutable: salta los campos cuyo `name` ya exista para web:inia.

Uso:
    python3 import_kml_fields.py                 # usa ../../kml_riegos y api.agragent.com
    python3 import_kml_fields.py --dir <ruta> --api <base_url> --user web:inia
    python3 import_kml_fields.py --dry-run       # no escribe, solo muestra
"""
import argparse
import glob
import json
import math
import os
import ssl
import sys
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET


def make_ssl_context():
    """SSL context robusto en macOS (Python suele no tener CAs locales)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    # Sin certifi en macOS la verificación suele fallar: contexto sin verificación
    # (el API es público y no enviamos secretos en tránsito).
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    print("(aviso: certifi no disponible — SSL sin verificación de certificado)\n")
    return ctx


SSL_CTX = make_ssl_context()

DEFAULT_API = "https://api.agragent.com"
DEFAULT_USER = "web:inia"

# Paleta de colores distintos para que el mapa se vea claro (16 campos)
PALETTE = [
    "#52b788", "#e76f51", "#4895ef", "#f4a261", "#9b5de5", "#06d6a0",
    "#ef476f", "#ffd166", "#118ab2", "#f15bb5", "#00bbf9", "#fb8500",
    "#8ac926", "#ff595e", "#6a4c93", "#1982c4",
]

EARTH = 111320.0  # metros por grado (aprox)


def detect_crop(name: str) -> str:
    """Auto-detecta el cultivo desde el nombre del sector."""
    n = name.lower()
    if "palto" in n or "aguacate" in n:
        return "palto"
    # Cuarteles / sectores de viña / INIA → uva vinífera por defecto
    return "uva_vinif"


def parse_kml(path: str):
    """Devuelve (field_name, ring) donde ring = [[lng,lat], ...] cerrado, o None."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        print(f"  ! XML inválido: {e}")
        return None
    root = tree.getroot()

    # Namespace-agnostic: ignoramos el prefijo en cada tag
    def local(tag):
        return tag.split("}")[-1]

    # Nombre del campo: primer <name> bajo <Document> (o el del Placemark)
    doc_name = None
    placemark_name = None
    coords_text = None
    for el in root.iter():
        lt = local(el.tag)
        if lt == "name" and el.text:
            txt = el.text.strip()
            parent_is_doc = False  # heurística simple: el primer name es el del Document
            if doc_name is None:
                doc_name = txt
            placemark_name = txt
        elif lt == "coordinates" and el.text and coords_text is None:
            coords_text = el.text.strip()

    field_name = doc_name or placemark_name or os.path.splitext(os.path.basename(path))[0]

    if not coords_text:
        print("  ! sin <coordinates>")
        return None

    ring = []
    for tok in coords_text.replace("\n", " ").split():
        parts = tok.split(",")
        if len(parts) >= 2:
            try:
                lng = float(parts[0])
                lat = float(parts[1])
            except ValueError:
                continue
            ring.append([lng, lat])

    if len(ring) < 3:
        print("  ! polígono con menos de 3 puntos")
        return None

    # Cerrar el anillo si no lo está
    if ring[0] != ring[-1]:
        ring.append(ring[0])

    return field_name, ring


def ring_area_ha(ring):
    """Área en hectáreas por fórmula del cordón (shoelace), corregida por latitud."""
    if len(ring) < 4:
        return None
    mean_lat = sum(p[1] for p in ring) / len(ring)
    cos_lat = math.cos(math.radians(mean_lat))
    # Proyección local a metros
    pts = [(p[0] * EARTH * cos_lat, p[1] * EARTH) for p in ring]
    s = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        s += x1 * y2 - x2 * y1
    area_m2 = abs(s) / 2.0
    return round(area_m2 / 10000.0, 4)


def build_field_payload(user_id, name, ring, color, crop_type):
    area = ring_area_ha(ring)
    geojson = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"name": name, "color": color, "crop_type": crop_type},
        }],
    }
    return {
        "user_id": user_id,
        "name": name,
        "color": color,
        "crop_type": crop_type,
        "geometry": geojson,
        "area_ha": area,
    }


def http_get_fields(api, user_id):
    url = f"{api}/api/fields?user_id={urllib.parse.quote(user_id)}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("fields", [])


def http_post_field(api, payload):
    url = f"{api}/api/fields"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    default_dir = os.path.normpath(os.path.join(here, "..", "..", "..", "kml_riegos"))
    ap.add_argument("--dir", default=default_dir, help="Carpeta con los .kml")
    ap.add_argument("--api", default=DEFAULT_API, help="Base URL del API de fields")
    ap.add_argument("--user", default=DEFAULT_USER, help="user_id destino")
    ap.add_argument("--dry-run", action="store_true", help="No escribe, solo muestra")
    args = ap.parse_args()

    kmls = sorted(glob.glob(os.path.join(args.dir, "*.kml")))
    if not kmls:
        print(f"No se encontraron .kml en {args.dir}")
        sys.exit(1)

    print(f"Encontrados {len(kmls)} KML en {args.dir}")
    print(f"Destino: {args.api}  user_id={args.user}\n")

    existing_names = set()
    if not args.dry_run:
        try:
            existing = http_get_fields(args.api, args.user)
            existing_names = {f.get("name") for f in existing}
            print(f"Campos ya existentes para {args.user}: {len(existing_names)}\n")
        except urllib.error.URLError as e:
            print(f"! No se pudo consultar campos existentes: {e}")

    created = 0
    skipped = 0
    failed = 0
    for i, path in enumerate(kmls):
        base = os.path.basename(path)
        print(f"[{i+1}/{len(kmls)}] {base}")
        parsed = parse_kml(path)
        if not parsed:
            failed += 1
            continue
        name, ring = parsed
        crop = detect_crop(name)
        color = PALETTE[i % len(PALETTE)]
        area = ring_area_ha(ring)
        print(f"    name='{name}'  crop={crop}  area={area} ha  color={color}")

        if name in existing_names:
            print("    = ya existe, salto")
            skipped += 1
            continue

        if args.dry_run:
            created += 1
            continue

        payload = build_field_payload(args.user, name, ring, color, crop)
        try:
            res = http_post_field(args.api, payload)
            fid = (res.get("field") or {}).get("id", "?")
            print(f"    + creado (id={fid})")
            created += 1
        except urllib.error.HTTPError as e:
            print(f"    ! HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}")
            failed += 1
        except urllib.error.URLError as e:
            print(f"    ! error de red: {e}")
            failed += 1

    print(f"\nResumen: creados={created}  saltados={skipped}  fallidos={failed}")


if __name__ == "__main__":
    main()

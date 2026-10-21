"""Descarga incidencias del Ayuntamiento de Zaragoza y de la DGT (zona de Zaragoza),
obtiene coordenadas (propias de la fuente o, si faltan, vía Gemini) y escribe
data/incidencias.json. Sale con código 1 si no hay datos válidos."""
import os, re, sys, json, time, datetime
from zoneinfo import ZoneInfo
import requests
from lxml import etree
from google import genai
from google.genai import types

MODELO = "gemini-3.6-flash"
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 41.55, 41.76, -1.08, -0.78  # Zaragoza y entorno (rondas, A-2, Z-40...)
SALIDA, CACHE = "data/incidencias.json", "data/geocache_v2.json"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"

try:
    from pyproj import Transformer
    UTM = Transformer.from_crs(25830, 4326, always_xy=True)
except Exception:
    UTM = None


def en_zgz(lat, lon):
    try:
        return LAT_MIN <= float(lat) <= LAT_MAX and LON_MIN <= float(lon) <= LON_MAX
    except (TypeError, ValueError):
        return False


def tipo_desde_texto(txt):
    t = txt.lower()
    if "accident" in t: return "Accidente"
    if "corte" in t or "closure" in t or "cerrad" in t: return "Corte"
    if "obra" in t or "works" in t or "maintenance" in t or "mantenimiento" in t: return "Obras"
    if "retenci" in t or "congestion" in t or "atasco" in t: return "Retención"
    return "Otros"


def dia(s):
    return str(s).split("T")[0] if s else None


def reintentar(fn, intentos=3, espera=5):
    ultimo = None
    for i in range(1, intentos + 1):
        try:
            return fn()
        except Exception as e:
            ultimo = e
            print(f"Intento {i}/{intentos} fallido: {e}")
            if i < intentos:
                time.sleep(espera * i)
    raise ultimo


# ---------- Ayuntamiento de Zaragoza ----------
def coords_geometria(item):
    g = item.get("geometry")
    if not isinstance(g, dict) or not g.get("coordinates"):
        return None
    c = g["coordinates"]
    while isinstance(c[0], list):
        c = c[0]
    x, y = float(c[0]), float(c[1])
    if abs(x) > 1000:  # UTM 30N (ETRS89)
        if not UTM: return None
        x, y = UTM.transform(x, y)
    return (y, x) if en_zgz(y, x) else None


def fetch_ayuntamiento():
    url = "https://www.zaragoza.es/sede/servicio/via-publica/incidencia.json"
    def get():
        r = requests.get(url, params={"rows": 200}, headers=UA, timeout=35)
        r.raise_for_status()
        return r.json()
    data = reintentar(get)
    regs = data if isinstance(data, list) else (data.get("result") or data.get("incidencia") or data.get("results") or data.get("items") or [])
    out = []
    for n, it in enumerate(regs):
        if not isinstance(it, dict): continue
        calle = it.get("calle") or it.get("title") or it.get("nombre") or "Vía no especificada"
        tramo = it.get("tramo") or ""
        motivo = it.get("motivo") or it.get("description") or "Afección en la vía"
        tipo = it.get("tipo")
        tipo = tipo.get("title", "") if isinstance(tipo, dict) else str(tipo or "")
        c = coords_geometria(it)
        out.append({
            "id": f"zgz-{it.get('id', n)}", "fuente": "Ayuntamiento",
            "tipo": tipo_desde_texto(f"{tipo} {motivo}"),
            "titulo": str(calle).strip(), "via": str(tramo).strip(),
            "detalle": re.sub(r"<[^>]+>", " ", str(motivo)).strip(),
            "inicio": dia(it.get("inicio")), "fin": dia(it.get("fin")),
            "lat": c[0] if c else None, "lon": c[1] if c else None,
            "precision": "aprox" if c else None,
            "_calle": str(calle).strip(), "_tramo": str(tramo).strip(),
        })
    return out


# ---------- DGT (DATEX II) ----------
SENTIDOS = {"POSITIVE": "sentido creciente", "NEGATIVE": "sentido decreciente", "BOTH": "ambos sentidos"}


def fetch_dgt():
    url = "https://nap.dgt.es/datex2/v3/dgt/SituationPublication/datex2_v37.xml"
    r = reintentar(lambda: requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=45))
    r.raise_for_status()
    root = etree.fromstring(r.content, etree.XMLParser(recover=True, encoding="utf-8"))
    xp = lambda rec, q: [t.strip() for t in rec.xpath(q) if t.strip()]
    out = []
    for rec in root.xpath('//*[local-name()="situationRecord"]'):
        lats = xp(rec, './/*[local-name()="latitude"]/text()')
        lons = xp(rec, './/*[local-name()="longitude"]/text()')
        if not lats or not lons or not en_zgz(lats[0], lons[0]):
            continue
        via = (xp(rec, './/*[local-name()="roadName"]/text()') or xp(rec, './/*[local-name()="roadNumber"]/text()') or ["Carretera"])[0]
        pks = sorted(set(xp(rec, './/*[local-name()="kilometerPoint"]/text()')))
        sent = [SENTIDOS[v.upper()] for v in xp(rec, './/*[local-name()="tpegDirection"]/text()') if v.upper() in SENTIDOS]
        coment = xp(rec, './/*[local-name()="generalPublicComment"]//*[local-name()="value"]/text()')
        extra = []
        if pks: extra.append("pk " + (pks[0] if len(pks) == 1 else f"{pks[0]}–{pks[-1]}"))
        if sent: extra.append(sent[0])
        crudo = (rec.get(XSI) or "") + " " + " ".join(xp(rec, './/text()'))
        out.append({
            "id": f"dgt-{rec.get('id', len(out))}", "fuente": "DGT",
            "tipo": tipo_desde_texto(crudo), "titulo": via, "via": " · ".join(extra),
            "detalle": " ".join(coment)[:300],
            "inicio": dia((xp(rec, './/*[local-name()="overallStartTime"]/text()') or [None])[0]),
            "fin": dia((xp(rec, './/*[local-name()="overallEndTime"]/text()') or [None])[0]),
            "lat": float(lats[0]), "lon": float(lons[0]), "precision": "exacta",
        })
    return out


# ---------- Ubicación por dirección: Gemini normaliza el texto, Nominatim (OSM) da las coordenadas ----------
NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA_NOM = {"User-Agent": "obraseincidenciaszaragoza.es/1.0 (https://github.com/aabadmo4/oi_zgz)"}


def cargar_cache():
    try:
        c = json.load(open(CACHE, encoding="utf-8"))
    except Exception:
        c = {}
    c.setdefault("norm", {})
    c.setdefault("geo", {})
    return c


def nominatim(via, numero):
    """Busca calle (y portal si hay número) dentro de Zaragoza. Respeta 1 petición/segundo."""
    params = {"format": "jsonv2", "limit": 1, "countrycodes": "es", "city": "Zaragoza",
              "street": f"{numero or ''} {via}".strip(),
              "viewbox": f"{LON_MIN},{LAT_MAX},{LON_MAX},{LAT_MIN}", "bounded": 1,
              "polygon_geojson": 0 if numero else 1}
    r = reintentar(lambda: requests.get(NOMINATIM, params=params, headers=UA_NOM, timeout=30))
    time.sleep(1.1)
    r.raise_for_status()
    res = r.json()
    if not res or not en_zgz(res[0]["lat"], res[0]["lon"]):
        return None
    o = res[0]
    geo = {"lat": float(o["lat"]), "lon": float(o["lon"]),
           "precision": "portal" if numero and o.get("category") != "highway" else "calle"}
    g = o.get("geojson") or {}
    if g.get("type") == "LineString":
        lineas = [g["coordinates"]]
    elif g.get("type") == "MultiLineString":
        lineas = g["coordinates"]
    else:
        lineas = []
    if lineas:
        geo["trazado"] = [[[round(y, 6), round(x, 6)] for x, y in l[::max(1, len(l) // 40)]] for l in lineas]
    return geo


def fallback_norm(calle):
    m = re.match(r"^(.*?),\s*(\d+\s?[A-Za-z]?)$", calle)
    return {"via": m.group(1) if m else calle, "numero": m.group(2).replace(" ", "") if m else None}


def geocodificar(items):
    ay = [i for i in items if i["fuente"] == "Ayuntamiento"]
    if not ay:
        return
    cache = cargar_cache()
    textos = {}
    for i in ay:
        i["_raw"] = f'{i["_calle"]}|{i["_tramo"]}|{i["detalle"][:160]}'
        textos[i["_raw"]] = (i["_calle"], i["_tramo"], i["detalle"][:160])

    # 1) Gemini solo normaliza el texto (tipo de vía, nombre, número). No devuelve coordenadas.
    pend = [r for r in textos if r not in cache["norm"]]
    key = os.environ.get("GEMINI_API_KEY")
    if pend and key:
        cli = genai.Client(api_key=key)
        for k in range(0, len(pend), 20):
            lote = pend[k:k + 20]
            prompt = ("Normaliza direcciones de incidencias viarias de Zaragoza (España) para geocodificarlas. "
                      "NO devuelvas coordenadas. Para cada línea devuelve un objeto "
                      "{\"i\": n, \"via\": nombre completo de la vía con su tipo en español (por ejemplo "
                      "'Calle Doctor Blanco Cordero' o 'Avenida de Navarra'), \"numero\": número de portal como texto "
                      "si el texto indica uno concreto (en calle, tramo o motivo, por ejemplo 'n.º 8' o ', 11'), "
                      "o null si no hay número, es un rango o afecta a toda la calle}. "
                      "Expande las abreviaturas del callejero ((DR.)=Doctor, (AV.)=Avenida, (PS.)=Paseo, "
                      "(PZA.)=Plaza, (C/)=Calle...) y coloca el tipo delante. Usa solo lo que dice el texto; no inventes. "
                      "Responde SOLO con una lista JSON.\n"
                      + "\n".join(f"{n}| calle: {textos[r][0]} | tramo: {textos[r][1]} | motivo: {textos[r][2]}"
                                  for n, r in enumerate(lote)))
            try:
                resp = reintentar(lambda: cli.models.generate_content(
                    model=MODELO, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0)))
                for o in json.loads(resp.text):
                    cache["norm"][lote[int(o["i"])]] = {"via": o.get("via"), "numero": o.get("numero")}
            except Exception as e:
                print(f"Normalización fallida para un lote: {e}")

    # 2) Nominatim (OpenStreetMap) localiza la calle y el portal; si el portal no existe, cae a la calle.
    for i in ay:
        n = cache["norm"].get(i["_raw"]) or fallback_norm(i["_calle"])
        via = n.get("via") or i["_calle"]
        num = str(n["numero"]).strip() if n.get("numero") else None
        gk = f"{via}|{num or ''}"
        geo = cache["geo"].get(gk)
        if not geo:
            try:
                geo = nominatim(via, num) or (nominatim(via, None) if num else None)
            except Exception as e:
                print(f"Nominatim falló para {gk}: {e}")
                geo = None
            if geo:
                cache["geo"][gk] = geo
        if geo:
            i["lat"], i["lon"], i["precision"] = geo["lat"], geo["lon"], geo["precision"]
            if geo["precision"] == "calle" and geo.get("trazado"):
                i["trazado"] = geo["trazado"]
    os.makedirs("data", exist_ok=True)
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)


def main():
    fuentes, items = {}, []
    for nombre, fn in (("ayuntamiento", fetch_ayuntamiento), ("dgt", fetch_dgt)):
        try:
            datos = fn()
            fuentes[nombre] = {"ok": True, "n": len(datos)}
            items += datos
        except Exception as e:
            print(f"Error en {nombre}: {e}")
            fuentes[nombre] = {"ok": False, "n": 0}
    geocodificar(items)
    for i in items:
        for k in ("_calle", "_tramo", "_raw"):
            i.pop(k, None)
    con_coords = [i for i in items if i["lat"] is not None]
    if not con_coords:
        print("Sin incidencias con coordenadas: no se actualiza.")
        sys.exit(1)
    os.makedirs("data", exist_ok=True)
    salida = {"actualizado": datetime.datetime.now(ZoneInfo("Europe/Madrid")).isoformat(timespec="minutes"),
              "fuentes": fuentes, "sin_ubicar": len(items) - len(con_coords), "incidencias": con_coords}
    json.dump(salida, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"OK: {len(con_coords)} incidencias ({len(items) - len(con_coords)} sin ubicar)")


if __name__ == "__main__":
    main()

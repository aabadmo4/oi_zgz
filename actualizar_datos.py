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
SALIDA, CACHE = "data/incidencias.json", "data/geocache.json"
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
            "lat": c[0] if c else None, "lon": c[1] if c else None, "aprox": False,
            "_consulta": f"{calle}, {tramo}, Zaragoza, España".replace(", ,", ","),
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
            "lat": float(lats[0]), "lon": float(lons[0]), "aprox": False,
        })
    return out


# ---------- Geocodificación con Gemini (solo lo que no trae coordenadas) ----------
def geocodificar(items):
    pend = [i for i in items if i["lat"] is None]
    if not pend:
        return
    try:
        cache = json.load(open(CACHE, encoding="utf-8"))
    except Exception:
        cache = {}
    nuevas = sorted({i["_consulta"] for i in pend if i["_consulta"] not in cache})
    key = os.environ.get("GEMINI_API_KEY")
    if nuevas and key:
        cli = genai.Client(api_key=key)
        for k in range(0, len(nuevas), 25):
            lote = nuevas[k:k + 25]
            prompt = ("Eres un geocodificador para Zaragoza (España). Para cada dirección devuelve el punto central "
                      "del tramo en WGS84. Responde SOLO con una lista JSON de objetos {\"i\": número, \"lat\": número|null, "
                      "\"lon\": número|null}. Si no estás razonablemente seguro, usa null; no inventes.\n"
                      + "\n".join(f"{n}: {q}" for n, q in enumerate(lote)))
            try:
                r = reintentar(lambda: cli.models.generate_content(
                    model=MODELO, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0)))
                for o in json.loads(r.text):
                    if en_zgz(o.get("lat"), o.get("lon")):
                        cache[lote[int(o["i"])]] = [float(o["lat"]), float(o["lon"])]
            except Exception as e:
                print(f"Geocodificación fallida para un lote: {e}")
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    for i in pend:
        if i["_consulta"] in cache:
            i["lat"], i["lon"] = cache[i["_consulta"]]
            i["aprox"] = True


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
        i.pop("_consulta", None)
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

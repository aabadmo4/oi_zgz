"""Descarga incidencias del Ayuntamiento de Zaragoza y de la DGT (zona de Zaragoza),
obtiene coordenadas (propias de la fuente o, si faltan, vía Gemini) y escribe
data/incidencias.json. Sale con código 1 si no hay datos válidos."""
import os, re, sys, json, time, datetime, html, math, unicodedata
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


def limpiar_texto(t):
    """Quita etiquetas HTML, decodifica entidades (&oacute; -> ó) y compacta espacios.
    Si el texto viene como ficha 'Dirección: ... Tipo: ... Observaciones: ...', lo resume."""
    t = re.sub(r"<[^>]+>", " ", str(t or ""))
    t = html.unescape(html.unescape(t))
    t = re.sub(r"\s+", " ", t).strip()
    m = re.search(r"Tipo:\s*(.+?)\s+Inicio:.*?Observaciones:\s*(.*)$", t, re.I)
    if m:
        tipo, obs = m.group(1).strip(), m.group(2).strip()
        t = f"{tipo}. {obs}" if obs else tipo
    return t


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
            "tipo": tipo_desde_texto(f"{tipo} {limpiar_texto(motivo)}"),
            "titulo": limpiar_texto(calle), "via": limpiar_texto(tramo),
            "detalle": limpiar_texto(motivo),
            "inicio": dia(it.get("inicio")), "fin": dia(it.get("fin")),
            "lat": c[0] if c else None, "lon": c[1] if c else None,
            "precision": "aprox" if c else None,
            "_calle": limpiar_texto(calle), "_tramo": limpiar_texto(tramo),
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


# Códigos de barrios rurales de Zaragoza (los que el Ayuntamiento añade al final del nombre de calle: "ENMEDIO PÑF").
BARRIOS = {"ALF": "Alfocea", "CRT": "Cartuja Baja", "CSB": "Casablanca", "CST": "Casetas", "GRP": "Garrapinillos",
           "JSL": "Juslibol", "MRL": "Miralbueno", "MNT": "Montañana", "MNZ": "Monzalbarba", "MVR": "Movera",
           "PÑF": "Peñaflor", "SJN": "San Juan de Mozarrifar", "SIS": "Santa Isabel", "TRC": "Torrecilla de Valmadrid",
           "VNO": "Venta del Olivar", "VLM": "Villamayor de Gállego", "VLR": "Villarrapa", "SGR": "San Gregorio"}
# Centros aproximados (tomados de ubicaciones ya verificadas) para no depender de que Nominatim encuentre el barrio.
CENTROS_BARRIO = {"PÑF": (41.7479, -0.7927), "MRL": (41.6610, -0.9425), "MNT": (41.6883, -0.8287),
                  "SGR": (41.6924, -0.8652), "CRT": (41.5887, -0.8128), "CST": (41.7206, -1.0264), "MNZ": (41.7034, -0.9679)}
CAJA_ANCHA = (41.45, 41.85, -1.15, -0.65)  # barrios rurales: Peñaflor, Villamayor, Casetas... pueden quedar fuera de la caja urbana
RADIO_BARRIO_KM = 3.5  # una calle de un barrio rural debe estar a menos de esto de su centro


def sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")


def separar_barrio(calle):
    """'ENMEDIO           PÑF, 2' -> ('ENMEDIO, 2', 'PÑF'). Solo si el último token del nombre es un código de barrio."""
    nombre, coma, resto = calle.partition(",")
    toks = nombre.split()
    if len(toks) >= 2 and toks[-1].upper() in BARRIOS:
        return " ".join(toks[:-1]) + coma + resto, toks[-1].upper()
    return calle, None


ALIAS_ZONA = {c: sin_acentos(n).replace("villamayor de gallego", "villamayor") for c, n in BARRIOS.items()}
ALIAS_ZONA["CSB"] = "casablanca"


def km(a, b):
    dy, dx = (a[0] - b[0]) * 111.2, (a[1] - b[1]) * 111.2 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def _buscar(params, ancha=False):
    base = {"format": "jsonv2", "limit": 10, "countrycodes": "es", "addressdetails": 1}
    r = reintentar(lambda: requests.get(NOMINATIM, params={**base, **params}, headers=UA_NOM, timeout=30))
    time.sleep(1.1)
    r.raise_for_status()
    a, b, c, d = CAJA_ANCHA if ancha else (LAT_MIN, LAT_MAX, LON_MIN, LON_MAX)
    return [o for o in r.json() if a <= float(o["lat"]) <= b and c <= float(o["lon"]) <= d]


def zona_coincide(o, cod):
    a = o.get("address") or {}
    zonas = [sin_acentos(a.get(k, "")) for k in ("suburb", "village", "hamlet", "town", "city_district", "neighbourhood", "quarter", "municipality")]
    return any(z and ALIAS_ZONA[cod] in z for z in zonas)


def en_barrio_rural(o):
    """True si la dirección del resultado (campos de zona de Nominatim, no el nombre de la calle) es un barrio rural."""
    a = o.get("address") or {}
    zonas = [sin_acentos(a.get(k, "")) for k in ("suburb", "village", "hamlet", "town", "city_district", "neighbourhood", "quarter", "municipality")]
    nombres = [sin_acentos(n) for n in BARRIOS.values()] + ["villamayor"]
    return any(z and any(z == n or z.startswith(n) for n in nombres) for z in zonas)


def centro_barrio(cod, cache_geo):
    """Centro aproximado del barrio: semilla fija, o búsqueda en Nominatim (cacheada) con varias variantes del nombre."""
    if cod in CENTROS_BARRIO:
        return {"lat": CENTROS_BARRIO[cod][0], "lon": CENTROS_BARRIO[cod][1]}
    k = f"v3:barrio|{cod}"
    if not cache_geo.get(k):
        cache_geo[k] = None
        for q in (f"{BARRIOS[cod]}, Zaragoza", BARRIOS[cod]):
            res = _buscar({"q": q, "limit": 5}, ancha=True)
            res = sorted(res, key=lambda o: o.get("category") != "place")  # primero los 'place' (pueblo/barrio)
            if res:
                cache_geo[k] = {"lat": float(res[0]["lat"]), "lon": float(res[0]["lon"])}
                break
    return cache_geo[k]


def nominatim(via, numero, barrio=None, ancla=None, cache_geo=None):
    """Busca calle (y portal si hay número). Sin código de barrio descarta resultados de barrios rurales
    (la 'Calle Moncayo' de Casetas no es la del CP 50010); con código solo acepta resultados del barrio
    (por su zona en la dirección o por cercanía a su centro)."""
    try:
        centro = centro_barrio(barrio, cache_geo) if barrio else None
    except Exception as e:
        print(f"  no se pudo situar el barrio {barrio}: {e}")
        centro = None
    ref_c = (centro["lat"], centro["lon"]) if centro else None
    nombre = re.sub(r"^(Calle|Avenida|Paseo|Plaza|Camino|Carretera|Glorieta|Ronda|Travesía|Pasaje|Callejón)\s+", "", via)
    caja = CAJA_ANCHA if barrio else (LAT_MIN, LAT_MAX, LON_MIN, LON_MAX)
    viewbox = {"viewbox": f"{caja[2]},{caja[1]},{caja[3]},{caja[0]}", "bounded": 1}
    intentos = []
    if barrio:  # texto libre con el barrio; primero con el tipo de vía, luego solo el nombre
        for v in dict.fromkeys([via, nombre]):
            intentos.append({"q": f"{(numero + ' ') if numero else ''}{v}, {BARRIOS[barrio]}, Zaragoza", **viewbox})
    else:
        intentos.append({"city": "Zaragoza", "street": f"{numero or ''} {via}".strip(), **viewbox})
    for params in intentos:
        res = _buscar({**params, "polygon_geojson": 0 if numero else 1}, ancha=bool(barrio))
        if barrio:
            res = [o for o in res if zona_coincide(o, barrio)
                   or (ref_c and km(ref_c, (float(o["lat"]), float(o["lon"]))) <= RADIO_BARRIO_KM)]
        else:
            res = [o for o in res if not en_barrio_rural(o)]  # si solo hay rurales, mejor no ubicar que ubicar mal
        if res:
            ref = ref_c or ancla
            if ref:
                res.sort(key=lambda o: km(ref, (float(o["lat"]), float(o["lon"]))))
            o = res[0]
            geo = {"lat": float(o["lat"]), "lon": float(o["lon"]),
                   "precision": "portal" if numero and o.get("category") != "highway" else "calle"}
            g = o.get("geojson") or {}
            lineas = [g["coordinates"]] if g.get("type") == "LineString" else (g["coordinates"] if g.get("type") == "MultiLineString" else [])
            if lineas:
                geo["trazado"] = [[[round(y, 6), round(x, 6)] for x, y in l[::max(1, len(l) // 40)]] for l in lineas]
            return geo
    return None


TIPOS_VIA = {"AV.": "Avenida", "AVDA.": "Avenida", "PS.": "Paseo", "PZA.": "Plaza", "PL.": "Plaza", "CM.": "Camino",
             "CTRA.": "Carretera", "GTA.": "Glorieta", "RDA.": "Ronda", "TRAV.": "Travesía", "PJE.": "Pasaje",
             "C/": "Calle", "CL.": "Calle", "CJ.": "Callejón"}
HONORIFICOS = {"DR.": "Doctor", "DRA.": "Doctora", "STA.": "Santa", "STO.": "Santo", "GRAL.": "General"}
MINUSCULAS = {"De", "Del", "La", "Las", "Los", "El", "Y"}


def norm_local(calle, motivo=""):
    """Normalización sin IA: 'BLANCO CORDERO (DR.), 11' -> Calle Doctor Blanco Cordero, nº 11."""
    nombre, _, resto = calle.strip().partition(",")
    nombre, resto = nombre.strip(), resto.strip()
    num = resto.replace(" ", "") if re.fullmatch(r"\d+\s?[A-Za-z]?", resto) else None  # rangos o texto: sin número
    if not num:
        mm = re.search(r"\bn\.?\s?[ºo°]\.?\s*(\d+)", motivo, re.I)
        num = mm.group(1) if mm else None
    tipo, hon = "Calle", ""
    for par in re.findall(r"\(([^)]*)\)", nombre):
        p = par.strip().upper()
        nombre = nombre.replace(f"({par})", "").strip()
        if p in TIPOS_VIA:
            tipo = TIPOS_VIA[p]
        elif p in HONORIFICOS:
            hon = HONORIFICOS[p]
    palabras = [w if w not in MINUSCULAS else w.lower() for w in nombre.title().split()]
    return {"via": " ".join(x for x in [tipo, hon, " ".join(palabras)] if x), "numero": num}


class CuotaAgotada(Exception):
    pass


def llamar_gemini(cli, prompt):
    """Una sola petición por lote. Si la cuota diaria se agota (429) no reintenta: cada intento gasta cuota."""
    for intento in (1, 2):
        try:
            return cli.models.generate_content(
                model=MODELO, contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
        except Exception as e:
            t = str(e)
            if "429" in t or "RESOURCE_EXHAUSTED" in t:
                raise CuotaAgotada(t[:120])
            print(f"Gemini falló (intento {intento}/2): {t[:120]}")
            if intento == 2:
                raise
            time.sleep(20)


def geocodificar(items):
    ay = [i for i in items if i["fuente"] == "Ayuntamiento"]
    if not ay:
        return
    cache = cargar_cache()
    for i in ay:
        i["_raw"] = f'{i["_calle"]}|{i["_tramo"]}|{i["detalle"][:160]}'
        i["_calle_sb"], i["_barrio"] = separar_barrio(i["_calle"])
        if i["_barrio"]:
            i["barrio"] = BARRIOS[i["_barrio"]]

    def aplicar(i, via, num):
        bar = i.get("_barrio")
        gk = f"v3:{via}|{num or ''}|{bar or ''}"
        geo = cache["geo"].get(gk)
        if not geo:
            ancla = (i["lat"], i["lon"]) if i.get("lat") is not None else None  # geometría oficial, si la hay
            try:
                geo = nominatim(via, num, bar, ancla, cache["geo"]) or (nominatim(via, None, bar, ancla, cache["geo"]) if num else None)
            except Exception as e:
                print(f"Nominatim falló para {gk}: {e}")
                geo = None
            if geo:
                cache["geo"][gk] = geo
        if not geo:
            if bar and i.get("lat") is None:  # último recurso: centro del barrio, marcado como aproximado
                try:
                    c = centro_barrio(bar, cache["geo"])
                except Exception:
                    c = None
                if c:
                    i["lat"], i["lon"], i["precision"] = c["lat"], c["lon"], "aprox"
                    return True
            return False
        i["lat"], i["lon"], i["precision"] = geo["lat"], geo["lon"], geo["precision"]
        if geo["precision"] == "calle" and geo.get("trazado"):
            i["trazado"] = geo["trazado"]
        return True

    # 1) Normalización local (sin IA) + Nominatim
    fallidos = []
    for i in ay:
        n = cache["norm"].get(i["_raw"]) or norm_local(i["_calle_sb"], i["detalle"])
        if not aplicar(i, n["via"], n["numero"]):
            fallidos.append(i)

    # 2) Gemini solo para direcciones que no se han podido localizar, en pocas peticiones
    textos = {i["_raw"]: (i["_calle"], i["_tramo"], i["detalle"][:160]) for i in fallidos if i["_raw"] not in cache["norm"]}
    pend = list(textos)
    key = os.environ.get("GEMINI_API_KEY")
    if pend and key:
        cli = genai.Client(api_key=key)
        try:
            for k in range(0, len(pend), 40):
                lote = pend[k:k + 40]
                prompt = ("Normaliza direcciones de incidencias viarias de Zaragoza (España) para geocodificarlas. "
                          "NO devuelvas coordenadas. Para cada línea devuelve {\"i\": n, \"via\": nombre completo de la vía con "
                          "su tipo en español (por ejemplo 'Calle Doctor Blanco Cordero'), \"numero\": número de portal como "
                          "texto si el texto indica uno concreto, o null si no hay número, es un rango o afecta a toda la calle}. "
                          "Expande las abreviaturas del callejero ((DR.)=Doctor, (AV.)=Avenida, (PS.)=Paseo...) y coloca el tipo "
                          "delante. Usa solo lo que dice el texto; no inventes. Responde SOLO con una lista JSON.\n"
                          + "\n".join(f"{n}| calle: {textos[r][0]} | tramo: {textos[r][1]} | motivo: {textos[r][2]}"
                                      for n, r in enumerate(lote)))
                resp = llamar_gemini(cli, prompt)
                for o in json.loads(resp.text):
                    cache["norm"][lote[int(o["i"])]] = {"via": o.get("via"), "numero": o.get("numero")}
        except CuotaAgotada as e:
            print(f"Cuota de Gemini agotada; se reintentará en la próxima ejecución. {e}")
        except Exception as e:
            print(f"Normalización con Gemini fallida: {e}")
    for i in fallidos:
        n = cache["norm"].get(i["_raw"])
        if n and n.get("via"):
            aplicar(i, n["via"], str(n["numero"]).strip() if n.get("numero") else None)

    cache["geo"] = {k: v for k, v in cache["geo"].items() if k.startswith("v3:")}  # descarta entradas antiguas (podían estar mal ubicadas)
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
        for k in ("_calle", "_tramo", "_raw", "_calle_sb", "_barrio"):
            i.pop(k, None)
    for i in items:
        if i["lat"] is None:
            print(f"SIN UBICAR: {i['titulo']} | {i['detalle'][:70]}")
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

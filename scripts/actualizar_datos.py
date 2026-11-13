"""Descarga incidencias del Ayuntamiento de Zaragoza y de la DGT (zona de Zaragoza),
obtiene coordenadas (propias de la fuente o, si faltan, vía Gemini) y escribe
data/incidencias.json. Sale con código 1 si no hay datos válidos."""
import os, re, sys, json, time, datetime, html, math, unicodedata
from zoneinfo import ZoneInfo
import requests
from lxml import etree
try:
    from google import genai
    from google.genai import types
except ImportError:  # solo se usa con GEMINI_API_KEY; los tests y el resto del script no lo necesitan
    genai = types = None

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
    # Interrupción de un servicio (agua, luz, gas): no es un corte de tráfico
    if re.search(r"cortes?\s+(de|del)\s+(agua|luz|gas|electricidad|suministro)", t): return "Suministro"
    if "corte" in t or "closure" in t or "cerrad" in t: return "Corte"
    if "obra" in t or "works" in t or "maintenance" in t or "mantenimiento" in t: return "Obras"
    if "retenci" in t or "congestion" in t or "atasco" in t: return "Retención"
    return "Otros"


def tipo_dgt(rec, xp, crudo=""):
    """Tipo de un registro DATEX II usando sus campos estructurados, no palabras sueltas del XML.
    'laneClosures' (un carril cerrado) aparece en casi todas las obras y NO es un corte de la vía:
    solo 'roadClosed' y 'carriagewayClosures' (calzada completa) cuentan como Corte."""
    causa = [c.lower() for c in xp(rec, './/*[local-name()="cause"]/*[local-name()="causeType"]/text()')]
    gestion = [g.lower() for g in xp(rec, './/*[local-name()="roadOrCarriagewayOrLaneManagementType"]/text()')]
    xsi = (rec.get(XSI) or "").lower()
    if "accident" in causa or "accident" in xsi:
        return "Accidente"
    if {"roadclosed", "carriagewayclosures"} & set(gestion):
        return "Corte"
    if "roadmaintenance" in causa or "works" in xsi or "maintenance" in xsi:
        return "Obras"
    if "abnormaltraffic" in causa or xp(rec, './/*[local-name()="abnormalTrafficType"]/text()'):
        return "Retención"
    # Resto: texto libre, ignorando los códigos de gestión de carriles (laneClosures, intermittentShortTermClosures...)
    limpio = re.sub(r"\b\w*closures?\b", " ", crudo, flags=re.I)
    t = tipo_desde_texto(limpio)
    return "Otros" if t == "Corte" and gestion else t


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


# Licencia y atribución que viajan dentro de data/incidencias.json (mismos textos que LICENCIA/ATRIBUCION de generar_paginas.py; lo vigila un test)
LICENCIA_DATOS = {
    "licencia": "CC BY 4.0",
    "licencia_url": "https://creativecommons.org/licenses/by/4.0/deed.es",
    "atribucion": ("Origen de los datos: Ayuntamiento de Zaragoza y Dirección General de Tráfico (DGT). "
                   "Datos tratados (nombres normalizados y ubicaciones geocodificadas) por Obras e Incidencias Zaragoza. "
                   "El Ayuntamiento y la DGT no avalan este servicio."),
}


def limpiar_tramo(t):
    """Como limpiar_texto, pero quita la puntuación suelta al principio o al final del tramo (', Entre C/ A y C/ B' / 'Entre C/ A y C/ B,')."""
    return re.sub(r"^[\s,;.\-–—]+|[\s,;.\-–—]+$", "", limpiar_texto(t))


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
            "titulo": limpiar_texto(calle), "via": limpiar_tramo(tramo),
            "detalle": limpiar_texto(motivo),
            "inicio": dia(it.get("inicio")), "fin": dia(it.get("fin")),
            "lat": c[0] if c else None, "lon": c[1] if c else None,
            "precision": "aprox" if c else None,
            "_calle": limpiar_texto(calle), "_tramo": limpiar_texto(tramo),
        })
    return out


# ---------- DGT (DATEX II) ----------
SENTIDOS = {"POSITIVE": "sentido creciente", "NEGATIVE": "sentido decreciente", "BOTH": "ambos sentidos"}

# Causa DATEX II (<cause><causeType> + <detailedCauseType>): primero el detalle, luego el tipo general.
CAUSAS = {
    # detailedCauseType
    "vehiclestuck": "Vehículo detenido", "brokendownvehicle": "Vehículo averiado",
    "abandonedvehicle": "Vehículo abandonado", "vehicleonfire": "Vehículo en llamas",
    "vehiclecarryingdangerousmaterials": "Vehículo con mercancías peligrosas",
    "objectontheroad": "Objeto en la calzada", "animalpresence": "Animales en la vía",
    # causeType
    "vehicleobstruction": "Vehículo detenido", "accident": "Accidente",
    "abnormaltraffic": "Tráfico lento", "obstruction": "Obstáculo en la vía",
    "roadmaintenance": "Obras en la vía", "poorroadinfrastructure": "Mal estado de la vía",
    "environmentalobstruction": "Obstáculo en la vía", "animalpresenceobstruction": "Animales en la vía",
}
ORIENTACIONES = {"northbound": "norte", "southbound": "sur", "eastbound": "este", "westbound": "oeste",
                 "northeastbound": "noreste", "northwestbound": "noroeste",
                 "southeastbound": "sureste", "southwestbound": "suroeste"}


def causa_dgt(rec, xp):
    """Devuelve (texto en español, códigos sin traducir) a partir de <cause> del situationRecord."""
    det = xp(rec, './/*[local-name()="detailedCauseType"]//text()')
    gen = xp(rec, './/*[local-name()="cause"]/*[local-name()="causeType"]/text()')
    for c in det + gen:
        if c.lower() in CAUSAS:
            return CAUSAS[c.lower()], []
    return "", det + gen


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
        dirs = xp(rec, './/*[local-name()="tpegDirectionRoad"]/text()') + xp(rec, './/*[local-name()="tpegDirection"]/text()')
        sent = [SENTIDOS[v.upper()] for v in dirs if v.upper() in SENTIDOS]
        orient = [ORIENTACIONES[v.lower()] for v in dirs if v.lower() in ORIENTACIONES]
        coment = xp(rec, './/*[local-name()="generalPublicComment"]//*[local-name()="value"]/text()')
        causa, raros = causa_dgt(rec, xp)
        if raros: print("DGT causa sin traducir:", rec.get("id"), raros)
        extra = []
        if pks: extra.append("pk " + (pks[0] if len(pks) == 1 else f"{pks[0]}–{pks[-1]}"))
        if sent: extra.append(sent[0])
        if orient: extra.append("orientación " + orient[0])
        crudo = (rec.get(XSI) or "") + " " + " ".join(xp(rec, './/text()'))
        out.append({
            "id": f"dgt-{rec.get('id', len(out))}", "fuente": "DGT",
            "tipo": tipo_dgt(rec, xp, crudo), "titulo": via, "via": " · ".join(extra),
            "detalle": (" ".join(coment) or causa)[:300], "causa": causa or None,
            "inicio": dia((xp(rec, './/*[local-name()="overallStartTime"]/text()') or [None])[0]),
            "fin": dia((xp(rec, './/*[local-name()="overallEndTime"]/text()') or [None])[0]),
            "lat": float(lats[0]), "lon": float(lons[0]), "precision": "exacta",
        })
    return out


# ---------- Ubicación por dirección: Gemini normaliza el texto, Nominatim (OSM) da las coordenadas ----------
NOMINATIM = "https://nominatim.openstreetmap.org/search"
UA_NOM = {"User-Agent": "obraseincidenciaszaragoza.es/1.0 (https://github.com/aabadmo4/oi_zgz)"}

# ---------- Nombre legible de la calle ("MADRID AVENIDA DE, 154" -> "Avenida de Madrid") ----------
# Prioridad: corrección manual > nombre de OpenStreetMap (si es compatible) > Gemini (si es compatible) > reglas.
ARTICULOS = {"de", "del", "la", "las", "los", "el", "y", "e"}
TIPOS_NOMBRE = {"AVENIDA": "Avenida", "PASEO": "Paseo", "CARRETERA": "Carretera", "CAMINO": "Camino", "PLAZA": "Plaza",
                "RONDA": "Ronda", "TRAVESIA": "Travesía", "GLORIETA": "Glorieta", "PASAJE": "Pasaje",
                "CALLEJON": "Callejón", "CALLE": "Calle", "AUTOVIA": "Autovía"}
ABREV_TIPO = {"AV": "AVENIDA", "AVDA": "AVENIDA", "PS": "PASEO", "PZA": "PLAZA", "PL": "PLAZA", "CM": "CAMINO", "CN": "CAMINO",
              "CTRA": "CARRETERA", "GTA": "GLORIETA", "RDA": "RONDA", "TRAV": "TRAVESIA", "PJE": "PASAJE", "CL": "CALLE",
              "CJ": "CALLEJON", "C": "CALLE"}
TITULOS = {"ALCALDE", "FRAY", "DOCTOR", "DOCTORA", "DR", "DRA", "GENERAL", "GRAL", "CAPITAN", "CORONEL", "PADRE", "MAESTRO",
           "DON", "DOÑA", "SAN", "SANTA", "SANTO", "MARQUES", "CONDE", "DUQUE", "INFANTA", "REY", "REINA"}
NO_INVERTIR = {"SAN", "SANTA", "SANTO", "SANTOS", "VIRGEN", "NTRA", "NUESTRA", "DON", "DOÑA", "FRAY", "DOCTOR"}
ORDINALES = {"primera", "segunda", "tercera", "cuarta", "quinta", "sexta", "septima", "octava", "novena", "decima"}
# Nombres de pila habituales (sin tilde -> con tilde): permiten reconocer "APELLIDO NOMBRE" y devolver "Nombre Apellido".
PILA = {k.lower(): v for k, v in {
    "JOSE": "José", "MARIA": "María", "PEDRO": "Pedro", "JUAN": "Juan", "MANUEL": "Manuel", "TOMAS": "Tomás",
    "PABLO": "Pablo", "JAIME": "Jaime", "LEOPOLDO": "Leopoldo", "RODRIGO": "Rodrigo", "AGUSTIN": "Agustín",
    "ANSELMO": "Anselmo", "JERONIMO": "Jerónimo", "SIXTO": "Sixto", "DESIDERIO": "Desiderio", "MIGUEL": "Miguel",
    "FRANCISCO": "Francisco", "FCO": "Francisco", "ANTONIO": "Antonio", "RAMON": "Ramón", "SANTIAGO": "Santiago",
    "LUIS": "Luis", "CARLOS": "Carlos", "FERNANDO": "Fernando", "ENRIQUE": "Enrique", "IGNACIO": "Ignacio",
    "JOAQUIN": "Joaquín", "VICENTE": "Vicente", "MARIANO": "Mariano", "ALFONSO": "Alfonso", "LORENZO": "Lorenzo",
    "FELIX": "Félix", "GREGORIO": "Gregorio", "ANDRES": "Andrés", "ANGEL": "Ángel", "JESUS": "Jesús", "JES": "Jesús",
    "RAFAEL": "Rafael", "RICARDO": "Ricardo", "EDUARDO": "Eduardo", "JULIAN": "Julián", "JULIO": "Julio",
    "SALVADOR": "Salvador", "DOMINGO": "Domingo", "BENITO": "Benito", "MARCOS": "Marcos", "AMBROSIO": "Ambrosio",
    "BRUNO": "Bruno", "TEODORO": "Teodoro", "VALENTIN": "Valentín", "ALEJANDRO": "Alejandro", "DIEGO": "Diego",
    "SEBASTIAN": "Sebastián", "FERMIN": "Fermín", "DAMASO": "Dámaso", "CASIMIRO": "Casimiro", "ISABEL": "Isabel",
    "ANA": "Ana", "TERESA": "Teresa", "CONCEPCION": "Concepción"}.items()}
ACENTOS = {**PILA, "marques": "Marqués", "catolica": "Católica"}
ROMANOS = re.compile(r"^(II|III|IV|VI|VII|VIII|IX|XI|XII)$", re.I)
# Calificadores del callejero que NO forman parte del nombre real ("ASIA CONTINENTE" es la Calle de Asia; se añade
# "Continente" para distinguirla de otras vías con el mismo nombre, p. ej. la Avenida de América).
CALIFICADORES_FINALES = {"continente"}


def quitar_calificador(nombre):
    """'Calle Asia Continente' -> 'Calle Asia'; 'ASIA CONTINENTE' -> 'ASIA'. No toca nombres de una sola palabra."""
    pal = str(nombre or "").split()
    while len(pal) > 1 and re.sub(r"[^a-z]", "", sin_acentos(pal[-1])) in CALIFICADORES_FINALES:
        pal.pop()
    return " ".join(pal)


def _f(t):
    return sin_acentos(t)


def clave_nombre(titulo):
    """Misma clave que usa generar_paginas para config/nombres_vias.json: 'BLANCO CORDERO (DR.), 11' -> 'blanco-cordero-dr'."""
    return re.sub(r"[^a-z0-9]+", "-", _f(str(titulo).split(",")[0])).strip("-")


def _tc(tokens, desde=0):
    """Pasa a 'Título Con Mayúsculas'; desde=1 si va precedido de otra palabra (el artículo inicial va en minúscula)."""
    out = []
    for k, t in enumerate(tokens):
        f = _f(t).rstrip(".")
        if (k + desde) and f in ARTICULOS:
            out.append(f)
        elif ROMANOS.match(t):
            out.append(t.upper())
        elif len(f) == 1 and f.isalpha():
            out.append(t[0].upper() + ".")
        elif f in ACENTOS:
            out.append(ACENTOS[f])
        elif re.search(r"\d", t):
            out.append(t.upper())
        else:
            out.append(t[:1].upper() + t[1:].lower())
    return " ".join(out)


def _particula(lista):
    return {"de": "de", "del": "del", "de la": "de la", "de los": "de los", "de las": "de las",
            "el": "del", "la": "de la", "los": "de los", "las": "de las"}.get(" ".join(_f(t) for t in lista)) if lista else None


def _expandir(t):
    base = t.rstrip(".").rstrip("/").upper()
    if (t.endswith(".") or t.endswith("/")) and base in ABREV_TIPO:
        return ABREV_TIPO[base]
    return HONORIFICOS.get(t.upper(), t)


def nombre_por_reglas(calle):
    """Reordena el nombre de callejero (apellido primero, tipo de vía donde caiga). Es el último recurso: sin tildes en apellidos."""
    # El portal (", 41") no forma parte del nombre: si se queda, las reglas lo tratan como una palabra más
    # ("VALENCIA AVENIDA DE, 41" -> "Avenida De, 41 Valencia") y además se duplica con el "nº" de la ficha.
    s = re.sub(r"\s+", " ", str(calle or "").split(",")[0].replace("(", " (")).strip()
    s = quitar_calificador(s)
    if re.match(r"^[A-Z]{1,3}-\d", s):
        return s
    titulo, entre_tipo = [], None
    m = re.search(r"\(([^)]*)\)?", s)
    if m:
        cont, cerrado = m.group(1).strip(), m.group(0).endswith(")")
        s = (s[:m.start()] + " " + s[m.end():]).strip()
        pal = cont.split()
        if pal and cerrado and _f(pal[0]).upper() in TIPOS_NOMBRE:
            entre_tipo = " ".join(w.capitalize() for w in pal)
        elif pal and (cerrado or all(_f(w).upper() in {_f(x).upper() for x in TITULOS} for w in pal)):
            titulo = [_expandir(w) for w in pal]
    toks = [_expandir(t) for t in s.split()]
    k = next((n for n, t in enumerate(toks) if _f(t).upper() in TIPOS_NOMBRE), None)
    if k is not None:
        tipo, antes, despues = TIPOS_NOMBRE[_f(toks[k]).upper()], toks[:k], toks[k + 1:]
        part = _particula(despues)
        if antes and (not despues or part):  # "MADRID AVENIDA DE", "COGULLADA CARRETERA"
            if not despues and _f(antes[0]) in ORDINALES:
                return _tc(antes + [toks[k]])  # "CUARTA AVENIDA" es el nombre tal cual
            if part is None:
                part = "" if any(_f(t) in ARTICULOS for t in antes) else "de"
            return " ".join(x for x in (tipo, part, _tc(antes, desde=1)) if x)
        if antes and despues:  # "AGUSTIN PASEO MARIA" -> "Paseo María Agustín"
            return f"{tipo} {_tc(despues + antes, desde=1)}"
        return f"{tipo} {_tc(despues, desde=1)}"  # el tipo va primero: "C/ AMBROSIO DEL RUSTE"
    trailing = []
    while len(toks) > 1 and _f(toks[-1]) in ARTICULOS:
        trailing.insert(0, toks.pop())
    part = _particula(trailing)
    if len(toks) >= 2 and _f(toks[0]).upper() not in NO_INVERTIR and all(
            _f(t).rstrip(".") in PILA or (len(t.rstrip(".")) == 1 and t.isalpha()) for t in toks[1:]):
        nombre = toks[1:] + (part.split() if part else []) + toks[:1]  # "CERBUNA PEDRO" -> "Pedro Cerbuna"
    else:
        nombre = (part.split() + toks) if part else toks + trailing
    res = _tc(titulo + nombre, desde=1)
    if entre_tipo:
        return f"{res} ({entre_tipo})"
    return "Calle " + res


def _significativas(n):
    parar = ARTICULOS | {t.lower() for t in TIPOS_NOMBRE} | {"travesia", "autovia"}
    return {w for w in re.split(r"[^a-z0-9]+", _f(n)) if len(w) > 1 and w not in parar}


def compatible(propuesto, base):
    """Un nombre externo (OSM/Gemini) solo se acepta si contiene todas las palabras significativas del nombre de origen."""
    b = _significativas(base)
    return bool(propuesto and b and b <= _significativas(propuesto))


def nombre_osm(o):
    a = o.get("address") or {}
    n = a.get("road") or a.get("pedestrian") or (o.get("name") if o.get("category") == "highway" else None)
    return n.strip() if n else None


def cargar_nombres():
    m = {}
    for f in ("config/nombres_vias.json", "config/nombres_visibles.json"):
        try:
            m.update({k: v for k, v in json.load(open(f, encoding="utf-8")).items() if isinstance(v, str) and v.strip()})
        except Exception:
            pass
    return m


def nombre_final(titulo, calle_sb, osm=None, gem=None, manual=None):
    if manual and manual.get(clave_nombre(titulo)):
        return manual[clave_nombre(titulo)]
    base = nombre_por_reglas(calle_sb)
    for cand in (osm, gem):
        if cand and compatible(cand, base):
            return cand.strip()
    return base


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


VECINOS = ("cuarte de huerva", "maria de huerva", "cadrete", "utebo", "villanueva de gallego", "zuera", "perdiguera",
           "alagon", "la puebla de alfinden", "pastriz", "el burgo de ebro", "fuentes de ebro", "pina de ebro", "vilanova")


def en_otro_municipio(o):
    """True solo si el resultado está en un municipio vecino conocido (p. ej. 'Calle San Juan de la Peña' de Cuarte de Huerva).
    Conservador a propósito: los barrios rurales de Zaragoza a menudo no llevan 'Zaragoza' en su dirección, así que
    NO se rechaza por 'no pone Zaragoza', solo cuando aparece un municipio vecino de la lista."""
    a = o.get("address") or {}
    if any("zaragoza" in sin_acentos(a.get(k, "")) for k in ("city", "town", "village", "municipality")):
        return False
    campos = [sin_acentos(a.get(k, "")) for k in ("city", "town", "village", "municipality")]
    # nombre largo: se ignora el primer trozo (la calle), para no rechazar una 'Calle Utebo' de Zaragoza
    resto = [sin_acentos(t.strip()) for t in str(o.get("display_name", "")).split(",")[1:]]
    return any(v in z for v in VECINOS for z in campos + resto if z)


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
            res = [o for o in res if not en_barrio_rural(o) and not en_otro_municipio(o)]  # si solo hay rurales u otros municipios, mejor no ubicar que ubicar mal
        if res:
            ref = ref_c or ancla
            if ref:
                res.sort(key=lambda o: km(ref, (float(o["lat"]), float(o["lon"]))))
            o = res[0]
            geo = {"lat": float(o["lat"]), "lon": float(o["lon"]),
                   "precision": "portal" if numero and o.get("category") != "highway" else "calle", "osm": nombre_osm(o)}
            g = o.get("geojson") or {}
            lineas = [g["coordinates"]] if g.get("type") == "LineString" else (g["coordinates"] if g.get("type") == "MultiLineString" else [])
            if lineas:
                geo["trazado"] = [[[round(y, 6), round(x, 6)] for x, y in l[::max(1, len(l) // 40)]] for l in lineas]
            return geo
    return None


TIPOS_VIA = {"AV.": "Avenida", "AVDA.": "Avenida", "PS.": "Paseo", "PZA.": "Plaza", "PL.": "Plaza", "CM.": "Camino",
             "CTRA.": "Carretera", "GTA.": "Glorieta", "RDA.": "Ronda", "TRAV.": "Travesía", "PJE.": "Pasaje",
             "C/": "Calle", "CL.": "Calle", "CJ.": "Callejón"}
TIPOS_FINALES = {"AV.", "AVDA.", "PS.", "PZA.", "PL.", "CTRA.", "GTA.", "RDA.", "TRAV.", "PJE."}
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
    toks = nombre.split()
    if len(toks) >= 2 and toks[-1].upper().rstrip(".") + "." in TIPOS_FINALES:  # 'SAN JUAN DE LA PEÑA AV' -> Avenida San Juan de la Peña
        tipo = TIPOS_VIA[toks[-1].upper().rstrip(".") + "."]
        nombre = " ".join(toks[:-1])
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
        via = quitar_calificador(via)  # también limpia entradas antiguas de caché/Gemini ("Calle Asia Continente")
        bar = i.get("_barrio")
        gk = f"v3:{via}|{num or ''}|{bar or ''}"
        geo = cache["geo"].get(gk)
        if not geo or "osm" not in geo:  # sin caché, o caché antigua sin el nombre de OSM: se consulta de nuevo
            ancla = (i["lat"], i["lon"]) if i.get("lat") is not None else None  # geometría oficial, si la hay
            try:
                nuevo = nominatim(via, num, bar, ancla, cache["geo"]) or (nominatim(via, None, bar, ancla, cache["geo"]) if num else None)
            except Exception as e:
                print(f"Nominatim falló para {gk}: {e}")
                nuevo = None
            geo = nuevo or geo
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
        i["_osm"] = geo.get("osm")
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
    if pend and key and not genai:
        print("Aviso: GEMINI_API_KEY definida pero falta el paquete google-genai; se omite el apoyo de Gemini.")
    if pend and key and genai:
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
            i["_gem"] = n["via"]
            aplicar(i, n["via"], str(n["numero"]).strip() if n.get("numero") else None)

    manual = cargar_nombres()
    for i in ay:
        i["nombre"] = nombre_final(i["titulo"], i.get("_calle_sb") or i["titulo"].split(",")[0], i.get("_osm"), i.get("_gem"), manual)
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
        for k in ("_calle", "_tramo", "_raw", "_calle_sb", "_barrio", "_osm", "_gem"):
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
              **LICENCIA_DATOS, "fuentes": fuentes, "sin_ubicar": len(items) - len(con_coords), "incidencias": con_coords}
    json.dump(salida, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"OK: {len(con_coords)} incidencias ({len(items) - len(con_coords)} sin ubicar)")


if __name__ == "__main__":
    main()

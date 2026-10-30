"""Genera páginas estáticas por vía a partir de data/incidencias.json.

- Vías principales (config/vias_principales.json): páginas fijas, siempre existen.
- Obras de larga duración: si una calle (no principal) tiene una incidencia del
  Ayuntamiento de UMBRAL_DIAS días o más entre inicio y fin, se crea su página.
  Se guardan en data/vias_conocidas.json; al terminar la obra, la página sigue
  existiendo (sin romper enlaces) pero con noindex y fuera del sitemap.
- Las incidencias cortas no generan página propia (evita contenido pobre).
- config/nombres_vias.json corrige nombres: 'cerbuna-pedro' -> 'Calle Pedro Cerbuna'.

Genera también sitemap.xml y robots.txt. Sin red ni dependencias externas. Uso: python scripts/generar_paginas.py [carpeta_salida=_site]
"""
import sys, re, json, html, unicodedata, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS, PRINCIPALES, CONOCIDAS = RAIZ / "data/incidencias.json", RAIZ / "config/vias_principales.json", RAIZ / "data/vias_conocidas.json"
NOMBRES = RAIZ / "config/nombres_vias.json"
HISTORIAL = RAIZ / "data/historial_vias.json"
DIAS_HISTORIAL = 30  # cuánto tiempo se muestran las incidencias ya finalizadas en la página de la vía
UMBRAL_DIAS = 60  # duración mínima (inicio→fin) para crear página propia de una calle no principal
TIPOS = {"Corte": ("⛔", "#ff6b5e"), "Obras": ("🚧", "#ffc400"), "Accidente": ("💥", "#ff9a3c"),
         "Retención": ("🚗", "#e9d27a"), "Suministro": ("💧", "#5ec8f2"), "Otros": ("⚠️", "#c9ced3")}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", fold(s)).strip("-")


def base_url():
    try:
        return "https://" + (RAIZ / "CNAME").read_text().strip()
    except OSError:
        return "https://obraseincidenciaszaragoza.es"


def og_imagen():
    """Etiquetas de imagen para compartir (Facebook, X, WhatsApp...). El JPG está en la raíz del repo."""
    u = base_url() + "/obraseincidenciaszaragoza.jpg"
    return (f'<meta property="og:image" content="{u}"><meta property="og:image:type" content="image/jpeg">'
            f'<meta property="og:image:width" content="1424"><meta property="og:image:height" content="752">'
            f'<meta property="og:image:alt" content="Mapa de obras e incidencias en Zaragoza">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{u}">')


def fecha(s):
    try:
        a, m, d = str(s).split("-")
        return f"{int(d)} de {MESES[int(m) - 1]} de {a}"
    except Exception:
        return ""


def cuando(i):
    return f"Hasta el {fecha(i['fin'])}" if i.get("fin") and fecha(i["fin"]) else (f"Desde el {fecha(i['inicio'])}" if i.get("inicio") and fecha(i["inicio"]) else "")


def fecha_hora(iso):
    try:
        d = datetime.datetime.fromisoformat(iso)
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}, {d:%H:%M}"
    except Exception:
        return iso


def titulo_ficha(i, nombre):
    """'CERBUNA PEDRO, 39' -> 'Calle Pedro Cerbuna, 39' (solo Ayuntamiento; la DGT ya trae 'Z-40')."""
    if i.get("fuente") != "Ayuntamiento":
        return i["titulo"]
    m = re.search(r",\s*(\d+\s?[A-Za-z]?)\s*$", i["titulo"])
    return f"{nombre}, {m.group(1)}" if m and m.group(1).strip() != "0" else nombre


def duracion(i):
    try:
        return (datetime.date.fromisoformat(i["fin"]) - datetime.date.fromisoformat(i["inicio"])).days
    except Exception:
        return None


def es_larga(i):
    return i.get("fuente") == "Ayuntamiento" and (duracion(i) or 0) >= UMBRAL_DIAS


def dur_texto(i):
    d = duracion(i)
    if d is None or d < 30:
        return ""
    m = round(d / 30.4)
    return f"Duración prevista: {m} {'mes' if m == 1 else 'meses'}"


def nombre_calle(titulo):
    """'BLANCO CORDERO (DR.), 11' -> 'Blanco Cordero (Dr.)'. Quita el número de portal."""
    n = str(titulo).split(",")[0].strip()
    return " ".join(w if w.lower() not in ("de", "del", "la", "las", "los", "el", "y") else w.lower() for w in n.title().split()) or "Vía sin nombre"


def clasificar(incs, principales, nombres=None):
    """Devuelve {slug: {nombre, principal, incidencias[]}}. Solo crea entradas nuevas de calle
    para incidencias de larga duración; las cortas solo cuentan si la vía ya existe."""
    nombres = nombres or {}
    pats = [(v, [re.compile(p) for p in v["patrones"]]) for v in principales]
    out = {v["slug"]: {"nombre": v["nombre"], "principal": True, "incidencias": []} for v in principales}
    pendientes = []
    for i in incs:
        t = fold(i.get("titulo"))
        destino = next((v["slug"] for v, rx in pats if any(r.search(t) for r in rx)), None)
        if not destino:
            nom = nombre_calle(i.get("titulo"))
            nom = nombres.get(slug(nom), nom)
            destino = slug(nom) or "via-sin-nombre"
            if destino not in out:
                if not es_larga(i):
                    pendientes.append((destino, nom, i))
                    continue
                out[destino] = {"nombre": nom, "principal": False, "incidencias": []}
        out[destino]["incidencias"].append(i)
    for destino, nom, i in pendientes:  # cortas: se añaden a una calle que ya tiene página por una obra larga
        if destino in out:
            out[destino]["incidencias"].append(i)
    for v in out.values():
        v["incidencias"].sort(key=lambda x: -(duracion(x) or 0))
    return out


def actualizar_historial(vias, hist, hoy):
    """Guarda cada incidencia vista por vía y descarta las que llevan más de DIAS_HISTORIAL sin verse."""
    for sl, v in vias.items():
        h = hist.setdefault(sl, {})
        for i in v["incidencias"]:
            h[i["id"]] = {k: i.get(k) for k in ("id", "tipo", "fuente", "titulo", "via", "detalle", "inicio", "fin")} | {"visto": hoy}
    lim = (datetime.date.fromisoformat(hoy) - datetime.timedelta(days=DIAS_HISTORIAL)).isoformat()
    for sl in list(hist):
        hist[sl] = {k: r for k, r in hist[sl].items() if r.get("visto", "") >= lim}
        if not hist[sl]:
            del hist[sl]
    return hist


def recientes(hist_via, activas):
    ids = {i["id"] for i in activas}
    return sorted((r for k, r in hist_via.items() if k not in ids), key=lambda r: r.get("visto", ""), reverse=True)


def bloque_portada(vias, limite=15):
    """Lista HTML (sin JavaScript) con las incidencias actuales más relevantes, enlazadas a su página de vía."""
    orden = {"Corte": 0, "Accidente": 1, "Obras": 2, "Retención": 3, "Suministro": 4, "Otros": 5}
    filas = []
    for sl, v in vias.items():
        enlazable = v["principal"] or any(es_larga(i) for i in v["incidencias"])
        for i in v["incidencias"]:
            filas.append((orden.get(i["tipo"], 9), 0 if enlazable else 1, i, sl if enlazable else None, v["nombre"]))
    filas.sort(key=lambda f: (f[0], f[1]))
    out = ""
    for _, _, i, sl, nom in filas[:limite]:
        e, _c = TIPOS.get(i["tipo"], TIPOS["Otros"])
        t = esc(titulo_ficha(i, nom))
        t = f'<a href="/vias/{esc(sl)}.html">{t}</a>' if sl else t
        linea = " · ".join(x for x in [esc(i["tipo"]), esc(i["fuente"]), esc(cuando(i))] if x)
        out += f"<li><span aria-hidden=\"true\">{e}</span> <strong>{t}</strong><br><span class=\"mute\">{linea}</span></li>"
    return f'<ul class="inc">{out}</ul>' if out else "<p>Ahora mismo no hay incidencias activas registradas.</p>"


CSS = """:root{--bg:#f2f1ec;--panel:#fff;--ink:#1d2024;--mute:#5d646c;--line:#d9d8d2;--sign:#ffc400;--asfalto:#22262b;--focus:#0b57d0}
@media(prefers-color-scheme:dark){:root{--bg:#171a1e;--panel:#22262b;--ink:#eceae4;--mute:#a4abb3;--line:#3a4048;--focus:#8ab4f8}}
*{box-sizing:border-box}body{margin:0;font-family:Barlow,system-ui,sans-serif;background:var(--bg);color:var(--ink);line-height:1.5}
header{background:var(--sign);color:#1d2024;padding:10px 16px;border-bottom:6px solid #1d2024}header a{color:#1d2024;font-weight:700;text-decoration:none}
main{max-width:860px;margin:0 auto;padding:18px 16px 30px}
nav.mig{font-size:14px;color:var(--mute);margin-bottom:10px}nav.mig a{color:inherit}
h1{font:800 clamp(24px,5vw,34px)/1.1 "Barlow Condensed",system-ui,sans-serif;margin:.2em 0 .3em}h2{font-size:20px;margin:1.4em 0 .5em}
.resumen{font-weight:600}.mute{color:var(--mute);font-size:14px}
#mapa{height:300px;border:1px solid var(--line);border-radius:8px;margin:14px 0}
ul.lista{list-style:none;margin:0;padding:0}.lista li{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0;display:grid;grid-template-columns:34px 1fr;gap:10px}
.ico{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;font-size:17px;border:2px solid #1d2024}
.t{font-weight:600}.s{font-size:14px;color:var(--mute)}
.enlaces{display:flex;flex-wrap:wrap;gap:8px;padding:0;list-style:none}.enlaces a{display:inline-block;padding:6px 12px;border:1.5px solid var(--line);border-radius:99px;color:inherit;text-decoration:none}
.enlaces a:hover,a:focus-visible{outline:3px solid var(--focus);outline-offset:1px}
.ad{margin:0;height:0;overflow:hidden;text-align:center}.ad:has(ins[data-ad-status=filled]){margin:16px 0;height:auto;overflow:visible}.ad small{display:block;font-size:11px;color:var(--mute);text-align:left;margin-bottom:2px}.ad:has(ins[data-ad-status=unfilled]){display:none}
.pin{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-size:16px;border:2px solid #1d2024;box-shadow:0 1px 4px #0006}
footer{font-size:13px;color:var(--mute);padding:14px 16px;background:var(--panel);border-top:1px solid var(--line)}footer a{color:inherit}"""


GA_HEAD = '''<script>
window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}
gtag('consent','default',{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',analytics_storage:'denied',wait_for_update:500,region:['AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IE','IT','LV','LT','LU','MT','NL','PL','PT','RO','SK','SI','ES','SE','IS','LI','NO','GB','CH']});
try{if(localStorage.getItem('oi_analytics_consent')==='granted')gtag('consent','update',{analytics_storage:'granted'});}catch(e){}
gtag('js',new Date());gtag('config','G-3H1BK6HXLL');
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-3H1BK6HXLL"></script>
<script>
/* BANNER PROVISIONAL (solo Analytics). Borrar este bloque cuando el mensaje de consentimiento de AdSense funcione. */
(function(){var K='oi_analytics_consent',b=null;
function get(){try{return localStorage.getItem(K)}catch(e){return null}}
function set(v){try{localStorage.setItem(K,v)}catch(e){}}
function close(){if(b&&b.parentNode)b.parentNode.removeChild(b);b=null}
function choose(v){set(v);gtag('consent','update',{analytics_storage:v});if(v==='granted')gtag('event','page_view');close()}
function open(){if(b)return;b=document.createElement('div');b.id='oi-cb';b.setAttribute('role','dialog');b.setAttribute('aria-label','Cookies de estadísticas');
b.innerHTML='<p>Usamos Google Analytics para medir de forma estadística el uso de la web. Solo se activa si aceptas. <a href="/privacidad.html">Más información</a></p><div><button type="button" data-v="denied">Rechazar</button><button type="button" data-v="granted">Aceptar</button></div>';
b.addEventListener('click',function(e){var v=e.target&&e.target.getAttribute&&e.target.getAttribute('data-v');if(v)choose(v)});
document.body.appendChild(b)}
function init(){var s=document.createElement('style');
s.textContent='#oi-cb{position:fixed;left:0;right:0;bottom:0;z-index:99999;box-sizing:border-box;padding:12px 16px calc(12px + env(safe-area-inset-bottom,0px));background:#202328;color:#f1f1f1;border-top:3px solid #ffc400;font:14px/1.4 system-ui,sans-serif;display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between}#oi-cb p{margin:0;flex:1 1 260px}#oi-cb a{color:#ffc400}#oi-cb div{display:flex;gap:8px}#oi-cb button{font:inherit;font-weight:600;min-height:44px;padding:9px 18px;border:2px solid #ffc400;border-radius:6px;background:transparent;color:#ffc400;cursor:pointer}';
document.head.appendChild(s);
var n=document.querySelector('footer nav');
if(n){var a=document.createElement('a');a.href='#';a.textContent='Preferencias de cookies';a.addEventListener('click',function(e){e.preventDefault();open()});n.appendChild(document.createTextNode(' \u00b7 '));n.appendChild(a)}
if(get()===null)open()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init()})();
</script>
'''


def plantilla(titulo, desc, canon, cuerpo, robots="index,follow", extra_head="", ld="", scripts=""):
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
{GA_HEAD}<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titulo)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{esc(canon)}">
<meta name="theme-color" content="#ffc400">
<meta property="og:type" content="website"><meta property="og:locale" content="es_ES">
<meta property="og:site_name" content="Obras e Incidencias Zaragoza">
<meta property="og:title" content="{esc(titulo)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{esc(canon)}">
{og_imagen()}
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚧</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;800&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-2672664299641705" crossorigin="anonymous"></script>
{extra_head}
{ld}
<style>{CSS}</style>
</head>
<body>
<header><a href="/">← Obras e Incidencias ZARAGOZA</a></header>
<main>
{cuerpo}
</main>
<footer><nav aria-label="Información legal"><a href="/avisolegal.html">Aviso legal</a> · <a href="/privacidad.html">Privacidad y cookies</a> · <a href="/acerca.html">Acerca de</a></nav><div>© 2026 Obras e Incidencias Zaragoza - TechECS_EU. Información orientativa, no oficial: obedece siempre la señalización.</div></footer>
{scripts}
</body>
</html>
"""


ADS = {"client": "ca-pub-2672664299641705", "banner": "3859322059", "feed": "9306430712", "layout": "-fb+5w+4e-db+86"}


def anuncio(tipo):
    """Anuncios desactivados en las páginas de vías (AdSense pendiente de aprobación). Solo hay anuncios en la portada."""
    return ""


def ld_json(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"


NOMBRE_TIPO = {"Corte": ("corte", "cortes"), "Obras": ("obra", "obras"), "Accidente": ("accidente", "accidentes"),
               "Retención": ("retención", "retenciones"), "Suministro": ("corte de suministro", "cortes de suministro"), "Otros": ("otra incidencia", "otras incidencias")}


def n_tipo(t, n):
    s_, p_ = NOMBRE_TIPO.get(t, (t.lower(), t.lower()))
    return f"{n} {s_ if n == 1 else p_}"


def resumen(nombre, incs):
    if not incs:
        return f"Ahora mismo no hay incidencias activas registradas en {nombre}."
    c = {}
    for i in incs:
        c[i["tipo"]] = c.get(i["tipo"], 0) + 1
    p = ", ".join(n_tipo(t, n) for t, n in sorted(c.items(), key=lambda x: -x[1]))
    return f"Ahora mismo hay {len(incs)} {'incidencia activa' if len(incs) == 1 else 'incidencias activas'} en {nombre}: {p}."


def pagina_via(sl, v, d, BASE, hermanas, actualizado, rec=()):
    nombre, incs = v["nombre"], v["incidencias"]
    canon = f"{BASE}/vias/{sl}.html"
    titulo = f"Obras e incidencias en {nombre}, Zaragoza hoy"
    res = resumen(nombre, incs)
    desc = f"{res} Cortes, obras, accidentes y retenciones en {nombre} (Zaragoza) con datos del Ayuntamiento y la DGT."
    tiene = bool(incs)
    robots = "index,follow" if ((v["principal"] and (incs or rec)) or any(es_larga(i) for i in incs)) else "noindex,follow"
    texto = f"<p>{esc(d['texto'])}</p>" if d.get("texto") else ""
    items = ""
    for i in incs:
        e, c = TIPOS.get(i["tipo"], TIPOS["Otros"])
        aviso = {"calle": "Toda la calle o sin número exacto: ubicación orientativa", "aprox": "Ubicación aproximada"}.get(i.get("precision"), "")
        linea = " · ".join(x for x in [esc(i["tipo"]), esc(i["fuente"]), esc(cuando(i)), esc(dur_texto(i)), esc(aviso)] if x)
        items += (f'<li><span class="ico" style="background:{c}" aria-hidden="true">{e}</span><div>'
                  f'<div class="t">{esc(titulo_ficha(i, nombre))}</div>'
                  + (f'<div class="s">{esc(i["via"])}</div>' if i.get("via") else "")
                  + (f'<div class="s">{esc(i["detalle"])}</div>' if i.get("detalle") else "")
                  + f'<div class="s">{linea}</div></div></li>')
    mapa = ""
    scripts = extra = ""
    if tiene:
        pts = [{"lat": i["lat"], "lon": i["lon"], "t": i["tipo"], "n": i["titulo"], "tz": i.get("trazado")} for i in incs]
        datos = json.dumps(pts, ensure_ascii=False).replace("</", "<\\/")
        extra = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">'
        mapa = '<div id="mapa" role="region" aria-label="Mapa de incidencias en esta vía"></div>'
        scripts = f"""<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const TIPOS={json.dumps({k: list(x) for k, x in TIPOS.items()}, ensure_ascii=False)},PTS={datos};
const map=L.map('mapa');
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'© OpenStreetMap'}}).addTo(map);
const g=L.featureGroup().addTo(map);
PTS.forEach(p=>{{const [e,c]=TIPOS[p.t]||TIPOS.Otros;
const m=L.marker([p.lat,p.lon],{{title:p.n,icon:L.divIcon({{className:'',html:'<div class="pin" style="background:'+c+'">'+e+'</div>',iconSize:[30,30],iconAnchor:[15,15]}})}});
m.bindPopup(Object.assign(document.createElement('strong'),{{textContent:p.n}}));g.addLayer(m);
if(p.tz)g.addLayer(L.polyline(p.tz,{{color:c,weight:6,opacity:.85}}))}});
map.fitBounds(g.getBounds().pad(.2),{{maxZoom:16}});
</script>"""
    if rec:
        fil = "".join(f'<li><div class="t">{esc(r["titulo"])}</div><div class="s">{esc(r["tipo"])} · {esc(r["fuente"])}' + (f' · {esc(cuando(r))}' if cuando(r) else "") + f' · visto por última vez el {esc(fecha(r["visto"]))}</div></li>' for r in rec[:10])
        recientes_html = f'<h2>Incidencias recientes en {esc(nombre)}</h2><p class="mute">Avisos de los últimos {DIAS_HISTORIAL} días que ya no figuran como activos.</p><ul class="lista">{fil}</ul>'
    else:
        recientes_html = ""
    rel = "".join(f'<li><a href="/vias/{esc(s)}.html">{esc(n)}</a></li>' for s, n in hermanas if s != sl)
    rel = f'<h2>Otras vías principales</h2><ul class="enlaces">{rel}</ul>' if rel else ""
    cuerpo = f"""<nav class="mig" aria-label="Migas de pan"><a href="/">Inicio</a> › <a href="/vias/">Vías</a> › {esc(nombre)}</nav>
<h1>Obras e incidencias en {esc(nombre)}</h1>
<p class="resumen">{esc(res)}</p>
{texto}
{anuncio("banner") if tiene else ""}
{mapa}
{'<h2>Incidencias activas</h2><ul class="lista">' + items + '</ul>' + anuncio("feed") if tiene else '<p>Vuelve más tarde: la información se actualiza varias veces al día. Mientras tanto puedes consultar <a href="/">todas las incidencias de Zaragoza</a>.</p>'}
{recientes_html}
<p class="mute">Actualizado: {esc(fecha_hora(actualizado))}. Datos del Ayuntamiento de Zaragoza y la DGT; información orientativa.</p>
{rel}
<p><a href="/">← Ver mapa completo de Zaragoza</a></p>"""
    ld = ld_json({"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": canon, "url": canon, "name": titulo, "inLanguage": "es-ES", "description": desc},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio", "item": BASE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Vías", "item": BASE + "/vias/"},
            {"@type": "ListItem", "position": 3, "name": nombre, "item": canon}]}]})
    return plantilla(titulo, desc, canon, cuerpo, robots, extra, ld, scripts)


def pagina_indice(vias, desc_p, BASE, actualizado):
    canon = f"{BASE}/vias/"
    def lista(items):
        return '<ul class="enlaces">' + "".join(
            f'<li><a href="/vias/{esc(s)}.html">{esc(v["nombre"])}' + (f' ({len(v["incidencias"])})' if v["incidencias"] else "") + "</a></li>"
            for s, v in items) + "</ul>"
    sec = ""
    for tipo in dict.fromkeys(d["tipo"] for d in desc_p.values()):
        sec += f"<h2>{esc(tipo)}</h2>" + lista([(s, v) for s, v in vias.items() if v["principal"] and desc_p[s]["tipo"] == tipo])
    otras = [(s, v) for s, v in sorted(vias.items(), key=lambda x: x[1]["nombre"]) if not v["principal"] and any(es_larga(i) for i in v["incidencias"])]
    if otras:
        sec += "<h2>Obras de larga duración en otras calles</h2>" + lista(otras)
    titulo = "Obras e incidencias por calle y vía en Zaragoza"
    desc = "Consulta las obras, cortes y demás incidencias de tráfico en las principales avenidas, paseos, rondas y calles de Zaragoza."
    cuerpo = (f'<nav class="mig" aria-label="Migas de pan"><a href="/">Inicio</a> › Vías</nav><h1>{esc(titulo)}</h1>'
              f'<p>Elige una vía para ver sus incidencias actuales. Entre paréntesis, las incidencias activas.</p>{sec}'
              f'<p class="mute">Actualizado: {esc(fecha_hora(actualizado))}.</p><p><a href="/">← Ver mapa completo de Zaragoza</a></p>')
    return plantilla(titulo, desc, canon, cuerpo)


def main():
    salida = Path(sys.argv[1] if len(sys.argv) > 1 else "_site")
    BASE = base_url()
    d = json.loads(DATOS.read_text(encoding="utf-8"))
    principales = json.loads(PRINCIPALES.read_text(encoding="utf-8"))
    desc_p = {v["slug"]: v for v in principales}
    try:
        nombres = json.loads(NOMBRES.read_text(encoding="utf-8"))
    except Exception:
        nombres = {}
    vias = clasificar(d.get("incidencias", []), principales, nombres)
    try:
        conocidas = json.loads(CONOCIDAS.read_text(encoding="utf-8"))
    except Exception:
        conocidas = {}
    for s, v in vias.items():  # recordar calles con obra larga para no romper URLs
        if not v["principal"]:
            conocidas[s] = v["nombre"]
    for s, n in conocidas.items():  # si antes tenían página, se mantiene (noindex si ya no hay obra larga)
        vias.setdefault(s, {"nombre": n, "principal": False, "incidencias": []})
    CONOCIDAS.parent.mkdir(exist_ok=True)
    CONOCIDAS.write_text(json.dumps(dict(sorted(conocidas.items())), ensure_ascii=False, indent=1), encoding="utf-8")

    act = d.get("actualizado", "")
    lastmod = act[:10] if act else None
    hoy = lastmod or datetime.date.today().isoformat()
    try:
        hist = json.loads(HISTORIAL.read_text(encoding="utf-8"))
    except Exception:
        hist = {}
    hist = actualizar_historial(vias, hist, hoy)
    HISTORIAL.write_text(json.dumps(hist, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    hermanas = [(v["slug"], v["nombre"]) for v in principales]
    carpeta = salida / "vias"
    carpeta.mkdir(parents=True, exist_ok=True)
    for s, v in vias.items():
        (carpeta / f"{s}.html").write_text(pagina_via(s, v, desc_p.get(s, {}), BASE, hermanas, act, recientes(hist.get(s, {}), v["incidencias"])), encoding="utf-8")
    (carpeta / "index.html").write_text(pagina_indice(vias, desc_p, BASE, act), encoding="utf-8")

    def indexable(s, v):
        return any(es_larga(i) for i in v["incidencias"]) or (v["principal"] and (v["incidencias"] or hist.get(s)))
    urls = [("/", "daily", "1.0"), ("/vias/", "daily", "0.8"), ("/acerca.html", "monthly", "0.4")]
    urls += [(f"/vias/{s}.html", "daily", "0.7" if v["principal"] else "0.5") for s, v in vias.items() if indexable(s, v)]
    lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
    # Aviso legal y privacidad llevan noindex: no van al sitemap.
    (salida / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{BASE}{u}</loc>{lm}<changefreq>{c}</changefreq><priority>{p}</priority></url>\n" for u, c, p in urls)
        + "</urlset>\n", encoding="utf-8")
    # Portada: sustituye el bloque <!--VIAS--> de la copia publicada para que ninguna página quede huérfana
    portada = salida / "index.html"
    if portada.exists():
        h = portada.read_text(encoding="utf-8")
        enl = lambda items: '<ul class="vias">' + "".join(f'<li><a href="/vias/{esc(s)}.html">{esc(n)}</a></li>' for s, n in items) + "</ul>"
        largas = [(s, v["nombre"]) for s, v in sorted(vias.items(), key=lambda x: x[1]["nombre"]) if not v["principal"] and any(es_larga(i) for i in v["incidencias"])]
        nuevo = ("<p>Incidencias de cada vía por separado. Vías principales:</p>" + enl(hermanas)
                 + ("<p>Obras de larga duración en otras calles:</p>" + enl(largas) if largas else "")
                 + '<p><a href="/vias/">Ver todas las vías</a></p>')
        h2 = re.sub(r"<!--VIAS-->.*?<!--/VIAS-->", lambda m: "<!--VIAS-->" + nuevo + "<!--/VIAS-->", h, flags=re.S)
        h2 = re.sub(r"<!--INC-->.*?<!--/INC-->", lambda m: "<!--INC-->" + bloque_portada(vias) + "<!--/INC-->", h2, flags=re.S)
        todas = d.get("incidencias", [])
        h2 = re.sub(r'(<p id="resumen">).*?(</p>)', lambda m: m.group(1) + esc(resumen("Zaragoza", todas)) + m.group(2), h2, count=1, flags=re.S)
        if act:
            h2 = h2.replace('<span id="estado">Cargando…</span>', f'<span id="estado">Actualizado {esc(fecha_hora(act))}</span>', 1)
        portada.write_text(h2, encoding="utf-8")
    # robots.txt generado con el dominio del CNAME. No se bloquean las páginas noindex: Google debe poder
    # rastrearlas para ver la etiqueta noindex y retirarlas del índice.
    (salida / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    n_p = sum(v["principal"] for v in vias.values())
    print(f"OK: {len(vias)} páginas de vía ({n_p} principales, {len(vias) - n_p} dinámicas), {len(urls)} URLs en sitemap")


if __name__ == "__main__":
    main()

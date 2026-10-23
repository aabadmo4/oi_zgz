# 🚧 Obras e Incidencias Zaragoza

Mapa y listado de **obras, cortes de tráfico, accidentes y retenciones en Zaragoza**, construido a partir de datos públicos del Ayuntamiento de Zaragoza y de la DGT.

🌐 **Web:** https://obraseincidenciaszaragoza.es

> Servicio independiente y gratuito. **No es una fuente oficial**: la información es orientativa y hay que obedecer siempre la señalización.

## Cómo funciona

El sitio es una **página estática** (`index.html`) que lee `data/incidencias.json`. Ese archivo lo genera un script de Python que se ejecuta automáticamente con GitHub Actions, y el resultado se publica en GitHub Pages.

```
Ayuntamiento (JSON) ─┐
                     ├─> scripts/actualizar_datos.py ─> data/incidencias.json ─> GitHub Pages
DGT NAP (DATEX II) ──┘         │
                               └─ geolocalización: Nominatim (OSM) + Gemini como apoyo
```

### Fuentes de datos

| Fuente | Endpoint | Notas |
|---|---|---|
| Ayuntamiento de Zaragoza | `https://www.zaragoza.es/sede/servicio/via-publica/incidencia.json` | Hasta 200 registros. Si traen geometría en UTM 30N (EPSG:25830) se convierte a WGS84 con `pyproj`. |
| DGT (Punto de Acceso Nacional) | `https://nap.dgt.es/datex2/v3/dgt/SituationPublication/datex2_v37.xml` | Formato DATEX II. Solo se conservan las incidencias dentro de la caja geográfica de Zaragoza. |

Zona cubierta (Zaragoza y entorno: rondas, A-2, Z-40…): latitud 41.55 a 41.76, longitud -1.08 a -0.78.

### Tipos de incidencia

`tipo_desde_texto()` clasifica cada registro por palabras clave: `Accidente`, `Corte`, `Obras`, `Retención` u `Otros`.

### Geolocalización de direcciones (Ayuntamiento)

1. **Normalización local** sin IA: `norm_local()` convierte textos como `BLANCO CORDERO (DR.), 11` en `Calle Doctor Blanco Cordero`, número `11`.
2. **Nominatim (OpenStreetMap)** devuelve las coordenadas, respetando 1 petición por segundo. Si no encuentra el portal, busca solo la calle y guarda su trazado.
3. **Gemini**, solo para las direcciones que no se han podido localizar: normaliza el texto de la dirección en lotes de 40. **No genera coordenadas.**
4. Los resultados se guardan en caché (`data/geocache_v2.json`) para no repetir peticiones.

Valores de `precision`: `exacta` (DGT), `portal`, `calle`, `aprox`.

### Actualización automática

El workflow `.github/workflows/actualizar.yml` se ejecuta:

- Todos los días a las 04:30 y 12:00 UTC (06:30 y 14:00 en horario de verano en España).
- De forma manual (`workflow_dispatch`).
- En cada *push* a `main`, pero en ese caso **solo republica la web** con los datos que ya hay: no vuelve a descargar ni a geolocalizar.

Pasos: instala dependencias, ejecuta el script (solo en ejecuciones programadas o manuales), hace *commit* de `data/` si todo fue bien y despliega en GitHub Pages. **Si el script falla** (por ejemplo, ninguna incidencia con coordenadas), se publica la última versión válida de los datos.

Usa el secreto `GEMINI_API_KEY` del repositorio. Sin él, el script funciona igualmente pero sin el paso de apoyo de Gemini.

### Control de commits (CI)

El workflow `.github/workflows/ci-git-governance.yml` se lanza en cada *push* a `main`, `master` o `develop` y llama a un workflow reutilizable de la organización: `TechECS/org-ci-workflows` (`conventional-commits-enforcement.yml`). Por su nombre, comprueba que los mensajes de commit sigan [Conventional Commits](https://www.conventionalcommits.org/es/). Los commits del bot ya usan ese formato (`chore(data): actualizar incidencias`).

## Estructura del repositorio

```
.
├── index.html                     # Aplicación (HTML + CSS + JS, sin build)
├── avisolegal.html
├── privacidad.html
├── robots.txt
├── sitemap.xml
├── ads.txt                        # Google AdSense
├── CNAME                          # Dominio personalizado en GitHub Pages
├── scripts/
│   └── actualizar_datos.py        # Descarga, clasifica, geolocaliza y escribe el JSON
├── data/
│   ├── incidencias.json           # Salida que consume la web (generada)
│   ├── geocache_v2.json           # Caché de geolocalización (generada)
│   └── geocache.json              # Caché antigua; el script actual no la usa
└── .github/workflows/
    ├── actualizar.yml             # Actualiza datos y publica en GitHub Pages
    └── ci-git-governance.yml      # Comprueba el formato de los commits
```

> El workflow solo publica `*.html`, `CNAME`, `ads.txt`, `robots.txt`, `sitemap.xml` y `data/`. Si añades un archivo de otro tipo a la web (imágenes, CSS, JS externo…), inclúyelo en el paso «Preparar sitio». El archivo `.nojekyll` se crea al desplegar.

## Formato de `data/incidencias.json`

```json
{
  "actualizado": "2026-10-23T08:15+02:00",
  "fuentes": { "ayuntamiento": { "ok": true, "n": 40 }, "dgt": { "ok": true, "n": 12 } },
  "sin_ubicar": 3,
  "incidencias": [
    {
      "id": "zgz-123",
      "fuente": "Ayuntamiento",
      "tipo": "Obras",
      "titulo": "BLANCO CORDERO (DR.), 11",
      "via": "tramo según la fuente",
      "detalle": "Motivo de la incidencia",
      "inicio": "2026-10-01",
      "fin": "2026-11-15",
      "lat": 41.6488,
      "lon": -0.8891,
      "precision": "portal",
      "trazado": [[[41.6488, -0.8891], [41.6495, -0.8880]]]
    }
  ]
}
```

`trazado` solo aparece cuando `precision` es `calle`. Las incidencias que no se pueden ubicar no se incluyen y se cuentan en `sin_ubicar`.

## Ejecutar en local

**Solo la web** (con los datos que ya hay en `data/`):

```bash
git clone https://github.com/aabadmo4/oi_zgz.git
cd oi_zgz
python3 -m http.server 8000
```

Abre http://localhost:8000. No sirve abrir `index.html` con doble clic: la página hace `fetch` de `data/incidencias.json`.

**Regenerar los datos** (Python 3.11):

```bash
pip install requests lxml pyproj google-genai
# Opcional: solo se usa para direcciones que Nominatim no localiza
export GEMINI_API_KEY="tu_clave"
python scripts/actualizar_datos.py
```

Si no se obtiene ninguna incidencia con coordenadas, el script termina con código 1 y no modifica el JSON. Nominatim limita a 1 petición por segundo, así que la primera ejecución sin caché puede tardar.

## Cómo colaborar

Toda ayuda es bienvenida. Algunas ideas basadas en el estado actual del código:

- 🏷️ **Mejorar la clasificación** de tipos (`tipo_desde_texto`) con ejemplos reales que queden como `Otros`.
- 🔤 **Ampliar la normalización de direcciones** (`TIPOS_VIA`, `HONORIFICOS`) con abreviaturas del callejero que fallen.
- 📍 **Reducir las incidencias `sin_ubicar`** o las de precisión `aprox`.
- 📡 **Añadir fuentes** (tranvía, autobús, eventos, otras administraciones).
- 🧪 **Añadir tests** para las funciones puras del script. Ahora mismo no hay.
- ♿ **Accesibilidad y rendimiento** de la web.
- 🔎 **SEO y contenidos** de la página.

### Flujo de trabajo

1. Abre un *issue* para comentar la idea o el error, sobre todo si el cambio es grande.
2. Haz un *fork* y crea una rama descriptiva: `git checkout -b fix/normalizar-calles`.
3. Cambios pequeños y centrados en una sola cosa.
4. Prueba en local (web y, si tocas el script, la generación de datos).
5. Escribe los commits con [Conventional Commits](https://www.conventionalcommits.org/es/): `feat: …`, `fix: …`, `docs: …`, `chore: …`.
6. Abre una *pull request* explicando qué cambia y por qué. Si afecta a la interfaz, adjunta una captura.

### Criterios

- **Sin build ni frameworks** en la web: HTML, CSS y JavaScript. Justifica cualquier dependencia nueva.
- **Respeta los límites de las fuentes.** Nominatim: 1 petición/segundo y `User-Agent` identificable. Usa la caché.
- **Nunca subas claves.** `GEMINI_API_KEY` solo como secreto del repositorio o variable de entorno local.
- **Escapa siempre los datos** antes de insertarlos en el HTML (función `esc()`).
- **Los datos generados** (`data/`) los actualiza el bot; no los edites a mano en una PR.
- **Privacidad y publicidad:** si cambias cookies, analítica o anuncios, actualiza `privacidad.html`.
- **Accesibilidad:** foco visible, `aria-label` en controles, buen contraste.

## Créditos

- [Ayuntamiento de Zaragoza](https://www.zaragoza.es/) y [DGT](https://www.dgt.es/) (datos públicos)
- Mapa y geocodificación: © colaboradores de [OpenStreetMap](https://www.openstreetmap.org/copyright), [Nominatim](https://nominatim.org/)
- Mapa interactivo: [Leaflet](https://leafletjs.com/)

## Licencia

El repositorio no incluye todavía un archivo de licencia. Sin él, por defecto nadie tiene permiso para reutilizar el código. Elige una (por ejemplo MIT o AGPL-3.0) y añade `LICENSE`.


## Contacto

Adán Nahir Abad Mora · TechECS_EU · techecs.eu@gmail.com

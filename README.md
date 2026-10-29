# 🚧 Obras e Incidencias Zaragoza

Mapa y listado de **obras, cortes de tráfico, accidentes y retenciones en Zaragoza**, construido a partir de datos públicos del Ayuntamiento de Zaragoza y de la DGT.

🌐 **Web:** https://obraseincidenciaszaragoza.es

> Servicio independiente y gratuito. **No es una fuente oficial**: la información es orientativa y hay que obedecer siempre la señalización.

## Cómo funciona

El sitio es una **página estática** (`index.html`) que lee `data/incidencias.json`. Ese archivo lo genera un script de Python que se ejecuta automáticamente con GitHub Actions, y el resultado se publica en GitHub Pages. Otro script genera las páginas estáticas por vía (obras de larga duración y vías principales), el sitemap y el `robots.txt`.

```
Ayuntamiento (JSON) ─┐
                     ├─> scripts/actualizar_datos.py ─> data/incidencias.json ─┐
DGT NAP (DATEX II) ──┘         │                                               ├─> scripts/generar_paginas.py ─> GitHub Pages
                               └─ geolocalización: Nominatim (OSM) + Gemini    │   (páginas de vías, sitemap, robots)
                                                      data/ + config/ ─────────┘
```

### Fuentes de datos

| Fuente | Endpoint | Notas |
|---|---|---|
| Ayuntamiento de Zaragoza | `https://www.zaragoza.es/sede/servicio/via-publica/incidencia.json` | Hasta 200 registros. Si traen geometría en UTM 30N (EPSG:25830) se convierte a WGS84 con `pyproj`. |
| DGT (Punto de Acceso Nacional) | `https://nap.dgt.es/datex2/v3/dgt/SituationPublication/datex2_v37.xml` | Formato DATEX II. Solo se conservan las incidencias dentro de la caja geográfica de Zaragoza. |

Zona cubierta (Zaragoza y entorno: rondas, A-2, Z-40…): latitud 41.55 a 41.76, longitud -1.08 a -0.78.

### Tipos de incidencia

`tipo_desde_texto()` clasifica cada registro por palabras clave: `Accidente`, `Corte`, `Suministro`, `Obras`, `Retención` u `Otros`.

`Suministro` (💧) agrupa las interrupciones programadas de agua, luz o gas (`Cortes de Agua. Desde las 8 hasta las 18 horas`). Afectan a los edificios de una calle, no al tráfico, y por eso no cuentan como `Corte`. Los cortes de calle (`se corta en el tramo…`, obras de colectores…) siguen siendo `Corte`.

### Geolocalización de direcciones (Ayuntamiento)

1. **Barrio rural.** El Ayuntamiento añade un código al final del nombre de la calle cuando esta pertenece a un barrio rural (`ENMEDIO PÑF, 2`). `separar_barrio()` lo detecta con la tabla `BARRIOS` y lo guarda en el campo `barrio`:

   | Código | Barrio | Código | Barrio | Código | Barrio |
   |---|---|---|---|---|---|
   | `ALF` | Alfocea | `MRL` | Miralbueno | `SIS` | Santa Isabel |
   | `CRT` | Cartuja Baja | `MNT` | Montañana | `TRC` | Torrecilla de Valmadrid |
   | `CSB` | Casablanca-Santa Fe | `MNZ` | Monzalbarba | `VNO` | Venta del Olivar |
   | `CST` | Casetas | `MVR` | Movera | `VLM` | Villamayor |
   | `GRP` | Garrapinillos | `PÑF` | Peñaflor | `VLR` | Villarrapa |
   | `JSL` | Juslibol | `SJN` | San Juan de Mozarrifar | `SGR` | San Gregorio |

2. **Normalización local** sin IA: `norm_local()` convierte textos como `BLANCO CORDERO (DR.), 11` en `Calle Doctor Blanco Cordero`, número `11`.
3. **Nominatim (OpenStreetMap)** devuelve hasta 10 candidatos (respetando 1 petición por segundo) y el script elige:
   - **Con código de barrio:** solo acepta resultados cuya dirección sea ese barrio o que estén a menos de 3,5 km de su centro. Para estos casos se usa una caja geográfica más ancha, porque barrios como Peñaflor quedan fuera de la caja urbana. Algunos centros están fijados en `CENTROS_BARRIO`; el resto se buscan en Nominatim.
   - **Sin código:** descarta los resultados que Nominatim sitúa en un barrio rural. Así `MONCAYO, 8` es la calle del CP 50010 y no la de Casetas. Si solo hay resultados rurales, no se ubica en lugar de ubicarla mal.
   - Si la incidencia trae geometría oficial, se usa para elegir entre candidatos.
   - Si no encuentra el portal, busca solo la calle y guarda su trazado.
   - Si un barrio rural no encuentra la calle, se marca en el centro del barrio como `aprox`.
4. **Gemini**, solo para las direcciones que no se han podido localizar: normaliza el texto de la dirección en lotes de 40. **No genera coordenadas.**
5. Los resultados se guardan en caché (`data/geocache_v2.json`). Las claves de geolocalización llevan el prefijo `v3:` e incluyen el barrio; el script descarta las entradas antiguas sin ese prefijo.

Las incidencias que no se pueden ubicar se imprimen en el log como `SIN UBICAR: …`.

Valores de `precision`: `exacta` (DGT), `portal`, `calle`, `aprox`.

### CI/CD con GitHub Actions

Hay tres workflows, identificados en la pestaña *Actions*:

| Workflow | Archivo | Cuándo se ejecuta | Qué hace |
|---|---|---|---|
| **CI** | `.github/workflows/ci.yml` | En *pull requests*, en *push* a ramas distintas de `main`, y cuando lo llama CD | Comprueba la sintaxis de los scripts, que los JSON de `config/` y `data/` sean válidos, ejecuta los tests y comprueba que el sitio se genera. |
| **CI - Git Governance** | `.github/workflows/ci-git-governance.yml` | En cada *push* a `main`, `master` o `develop` | Llama al workflow reutilizable `TechECS/org-ci-workflows` (`conventional-commits-enforcement.yml`) para comprobar que los commits sigan [Conventional Commits](https://www.conventionalcommits.org/es/). |
| **CD** | `.github/workflows/cd.yml` | *Push* a `main`, cada hora (minuto 17 UTC) y manual (`workflow_dispatch`) | Ver abajo. |

**CD** tiene tres jobs:

1. **CI previo** (solo en *push*): llama a `ci.yml`. Si falla, no se despliega.
2. **Actualizar datos (APIs)** (solo en ejecuciones programadas o manuales): ejecuta `actualizar_datos.py`, actualiza `vias_conocidas.json` e `historial_vias.json` con `generar_paginas.py` y hace *commit* de `data/` si todo fue bien. **Si el script falla**, no se guarda nada y se publica la última versión válida.
3. **Desplegar en Pages**: genera las páginas de vías, el sitemap y el `robots.txt`, y publica en GitHub Pages.

En un *push* a `main` se salta la descarga de datos y solo se vuelve a publicar la web.

> GitHub ejecuta los `cron` con el mejor esfuerzo: en horas de mucha carga una ejecución puede retrasarse o no llegar a producirse, así que no hay garantía de que se ejecute todas las horas.

Usa el secreto `GEMINI_API_KEY` del repositorio. Sin él, el script funciona igualmente pero sin el paso de apoyo de Gemini.

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
├── config/
│   ├── vias_principales.json      # Vías con página propia fija
│   └── nombres_vias.json          # Correcciones de nombres de vías
├── scripts/
│   ├── actualizar_datos.py        # Descarga, clasifica, geolocaliza y escribe el JSON
│   └── generar_paginas.py         # Páginas por vía, sitemap y robots.txt
├── tests/
│   └── test_geocodificacion.py    # Tests sin red: geolocalización y tipos
├── data/
│   ├── incidencias.json           # Salida que consume la web (generada)
│   ├── geocache_v2.json           # Caché de geolocalización (generada)
│   ├── vias_conocidas.json        # Vías con obras de larga duración (generada)
│   ├── historial_vias.json        # Incidencias finalizadas por vía (generada)
│   └── geocache.json              # Caché antigua; el script actual no la usa
└── .github/workflows/
    ├── ci.yml                     # CI: validación de código y datos
    ├── ci-git-governance.yml      # CI: formato de los commits
    └── cd.yml                     # CD: datos, CI previo y despliegue en Pages
```

> El job de despliegue solo publica `*.html`, `*.jpg`, `*.png`, `*.ico`, `CNAME`, `ads.txt`, `robots.txt`, `sitemap.xml` y `data/`. Si añades un archivo de otro tipo a la web (CSS, JS externo…), inclúyelo en el paso «Preparar sitio» de `cd.yml` y de `ci.yml`. El archivo `.nojekyll` se crea al desplegar.

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
      "barrio": "Peñaflor",
      "trazado": [[[41.6488, -0.8891], [41.6495, -0.8880]]]
    }
  ]
}
```

`barrio` solo aparece en las incidencias del Ayuntamiento cuya calle lleva código de barrio rural. `trazado` solo aparece cuando `precision` es `calle`. Las incidencias que no se pueden ubicar no se incluyen y se cuentan en `sin_ubicar`.

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

**Tests** (no necesitan red):

```bash
python -m unittest discover -s tests -v
```

**Páginas de vías** (genera la carpeta de salida; por defecto `_site`):

```bash
python scripts/generar_paginas.py _site
```

## Cómo colaborar

Toda ayuda es bienvenida. Algunas ideas basadas en el estado actual del código:

- 🏷️ **Mejorar la clasificación** de tipos (`tipo_desde_texto`) con ejemplos reales que queden como `Otros` o mal clasificados (como los cortes de agua, que antes salían como `Corte`).
- 🔤 **Ampliar la normalización de direcciones** (`TIPOS_VIA`, `HONORIFICOS`) con abreviaturas del callejero que fallen.
- 📍 **Reducir las incidencias `sin_ubicar`** o las de precisión `aprox`, y completar `CENTROS_BARRIO` con los barrios rurales que falten.
- 📡 **Añadir fuentes** (tranvía, autobús, eventos, otras administraciones).
- 🧪 **Ampliar los tests** (`tests/`): ahora cubren la geolocalización y la distinción entre `Corte` y `Suministro`; faltan `limpiar_texto` y la normalización de direcciones.
- ♿ **Accesibilidad y rendimiento** de la web.
- 🔎 **SEO y contenidos** de la página.

### Flujo de trabajo

1. Abre un *issue* para comentar la idea o el error, sobre todo si el cambio es grande.
2. Haz un *fork* y crea una rama descriptiva: `git checkout -b fix/normalizar-calles`.
3. Cambios pequeños y centrados en una sola cosa.
4. Prueba en local (web y, si tocas el script, la generación de datos y los tests). El workflow **CI** ejecuta las mismas comprobaciones en la PR.
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

Este proyecto se distribuye bajo los términos de la licencia **GNU Affero General Public License v3.0 (AGPLv3)**. Consulta el archivo [`LICENSE`](./LICENSE) para obtener más detalles.

## Contacto

Adán Nahir Abad Mora · TechECS_EU · techecs.eu@gmail.com
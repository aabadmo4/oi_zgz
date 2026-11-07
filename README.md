# 🚧 Obras e Incidencias Zaragoza

[![Tests y despliegue](https://img.shields.io/github/actions/workflow/status/aabadmo4/oi_zgz/cd.yml?branch=main&event=push&label=tests%20y%20despliegue)](https://github.com/aabadmo4/oi_zgz/actions/workflows/cd.yml)
[![Licencia: AGPL v3](https://img.shields.io/github/license/aabadmo4/oi_zgz)](LICENSE)
[![Datos actualizados](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fobraseincidenciaszaragoza.es%2Fdata%2Fincidencias.json&query=%24.actualizado&label=datos)](https://obraseincidenciaszaragoza.es/data/incidencias.json)

Mapa y listado de **obras, cortes de tráfico, accidentes y retenciones en Zaragoza**, construido a partir de datos públicos del Ayuntamiento de Zaragoza y de la DGT.

🌐 **Web:** https://obraseincidenciaszaragoza.es

> Servicio independiente y gratuito. **No es una fuente oficial**: la información es orientativa y hay que obedecer siempre la señalización.

## Cómo funciona

El sitio es una **página estática** (`index.html`) que lee `data/incidencias.json`. Ese archivo lo genera un script de Python que se ejecuta automáticamente con GitHub Actions, y el resultado se publica en GitHub Pages. Otro script genera las páginas estáticas por vía (obras de larga duración y vías principales), la página de [cortes de agua](https://obraseincidenciaszaragoza.es/cortes-de-agua-zaragoza.html), el sitemap y el `robots.txt`.

```
Ayuntamiento (JSON) ─┐
                     ├─> scripts/actualizar_datos.py ─> data/incidencias.json ─┐
DGT NAP (DATEX II) ──┘         │                                               ├─> scripts/generar_paginas.py ─> GitHub Pages
                               └─ geolocalización: Nominatim (OSM) + Gemini    │   (páginas de vías, sitemap, robots)
                                                      data/ + config/ ─────────┘
```

### Funcionalidades de la web

- **Mapa** (Leaflet + OpenStreetMap) con un marcador por incidencia, con icono y color según el tipo. Un marcador con borde discontinuo indica que afecta a toda la calle o que su ubicación es orientativa.
- **Listado** de incidencias con filtro por tipo y por fuente, buscador por calle o motivo (sin distinguir acentos) y la opción «Solo lo que se ve en el mapa».
- **Ficha** de cada incidencia: tramo, detalle, fuente, estado (`En curso`, `Quedan N días`, barra de progreso) y botón **Abrir en Maps**.
- **Compartir**: genera un texto y un enlace `https://obraseincidenciaszaragoza.es/#<id>` (por ejemplo `#dgt-29808033`). Al abrir el enlace, el mapa se centra en esa incidencia y muestra su ficha. Usa el menú de compartir del móvil o, si no existe, el portapapeles.

### Fuentes de datos

| Fuente | Endpoint | Notas |
|---|---|---|
| Ayuntamiento de Zaragoza | `https://www.zaragoza.es/sede/servicio/via-publica/incidencia.json` | Hasta 200 registros. Si traen geometría en UTM 30N (EPSG:25830) se convierte a WGS84 con `pyproj`. |
| DGT (Punto de Acceso Nacional) | `https://nap.dgt.es/datex2/v3/dgt/SituationPublication/datex2_v37.xml` | Formato DATEX II. Solo se conservan las incidencias dentro de la caja geográfica de Zaragoza. |

Zona cubierta (Zaragoza y entorno: rondas, A-2, Z-40…): latitud 41.55 a 41.76, longitud -1.08 a -0.78.

#### DGT: causa, sentido y orientación

Los registros DATEX II de la DGT llegan casi siempre sin comentario libre (`generalPublicComment`) y con `xsi:type="GenericSituationRecord"`, así que la información útil está en otros campos:

- `<cause>`: `causeType` y `detailedCauseType` (por ejemplo `vehicleObstruction` / `vehicleStuck`). `causa_dgt()` los traduce con la tabla `CAUSAS` (`Vehículo detenido`, `Vehículo averiado`, `Accidente`, `Tráfico lento`...). El texto se guarda en `causa` y se usa como `detalle` cuando no hay comentario.
- `tpegDirectionRoad` (`positive`/`negative`) da el **sentido** (creciente/decreciente) y `tpegDirection` (`eastBound`...) la **orientación** (este, oeste...). Ambos se añaden a `via`: `pk 323.986 · sentido creciente · orientación este`.
- Si llega una causa que no está en la tabla, el script lo escribe en el log (`DGT causa sin traducir: …`) para poder añadirla. Al público nunca se le muestra el código sin traducir.

El `id` de la incidencia es `dgt-<id del situationRecord>`, el mismo que usa el enlace para compartir.

### Tipos de incidencia

`tipo_desde_texto()` clasifica cada registro por palabras clave: `Accidente`, `Corte`, `Suministro`, `Obras`, `Retención` u `Otros`.

El tipo se calcula por palabras clave del texto: una incidencia DGT de `Vehículo detenido` sigue siendo `Otros`, y para distinguirla se usa el campo `causa`.

`Suministro` (💧) agrupa las interrupciones programadas de agua, luz o gas (`Cortes de Agua. Desde las 8 hasta las 18 horas`). Afectan a los edificios de una calle, no al tráfico, y por eso no cuentan como `Corte`. Los cortes de calle (`se corta en el tramo…`, obras de colectores…) siguen siendo `Corte`.

### Geolocalización de direcciones (Ayuntamiento)

1. **Barrio rural.** El Ayuntamiento añade un código al final del nombre de la calle cuando esta pertenece a un barrio rural (`ENMEDIO PÑF, 2`). `separar_barrio()` lo detecta con la tabla `BARRIOS` y lo guarda en el campo `barrio`:

   | Código | Barrio | Código | Barrio | Código | Barrio |
   |---|---|---|---|---|---|
   | `ALF` | Alfocea | `MRL` | Miralbueno | `SIS` | Santa Isabel |
   | `CRT` | Cartuja Baja | `MNT` | Montañana | `TRC` | Torrecilla de Valmadrid |
   | `CSB` | Casablanca | `MNZ` | Monzalbarba | `VNO` | Venta del Olivar |
   | `CST` | Casetas | `MVR` | Movera | `VLM` | Villamayor de Gállego |
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
5. Los resultados se guardan en caché (`data/geocache_v2.json`): `norm` guarda la normalización de Gemini por texto original y `geo` las coordenadas. Las claves de `geo` llevan el prefijo `v3:` e incluyen el barrio; el script descarta las entradas antiguas sin ese prefijo.

### Nombre legible de la calle

El Ayuntamiento envía las calles como `VALENCIA AVENIDA DE, 41` o `PUERTA DE SANCHO AV., 9`. El campo `nombre` guarda el nombre ya escrito como se lee (`Avenida de Valencia`, `Avenida Puerta de Sancho`); el número de portal se muestra aparte en la ficha. Se elige por este orden (`nombre_final()`):

1. Corrección manual en `config/nombres_vias.json` o `config/nombres_visibles.json` (clave: `clave_nombre()` del título, p. ej. `blanco-cordero-dr`).
2. Nombre de OpenStreetMap o de Gemini, solo si contiene todas las palabras significativas del nombre original (`compatible()`).
3. Reglas locales (`nombre_por_reglas()`): reordenan el apellido y el nombre de pila (`CERBUNA PEDRO` → `Pedro Cerbuna`), colocan el tipo de vía delante, expanden abreviaturas (`AV.`, `CTRA.`…) y no tocan nombres de santos. **Antes de aplicarlas se quita el portal** (`, 41`); si se queda, se confunde con una palabra del nombre y aparece repetido junto a «nº 41».

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
2. **Actualizar datos (APIs)** (solo en ejecuciones programadas o manuales): ejecuta `actualizar_datos.py`, valida el resultado con `tests/test_datos.py` (formato y valores), actualiza `vias_conocidas.json` e `historial_vias.json` con `generar_paginas.py` y hace *commit* de `data/` si todo fue bien. **Si el script o la validación fallan**, no se guarda nada y se publica la última versión válida.
3. **Desplegar en Pages**: genera las páginas de vías, el sitemap y el `robots.txt`, y publica en GitHub Pages.

En un *push* a `main` se salta la descarga de datos y solo se vuelve a publicar la web.

> GitHub ejecuta los `cron` con el mejor esfuerzo: en horas de mucha carga una ejecución puede retrasarse o no llegar a producirse, así que no hay garantía de que se ejecute todas las horas.

Usa el secreto `GEMINI_API_KEY` del repositorio. Sin él, el script funciona igualmente pero sin el paso de apoyo de Gemini.

## Estructura del repositorio

```
.
├── index.html                     # Aplicación (HTML + CSS + JS, sin build)
├── acerca.html
├── avisolegal.html
├── privacidad.html
├── robots.txt
├── sitemap.xml
├── ads.txt                        # Google AdSense
├── CNAME                          # Dominio personalizado en GitHub Pages
├── favicon.ico, icon-*.png, apple-touch-icon.png, obraseincidenciaszaragoza.jpg   # Iconos e imagen
├── config/
│   ├── vias_principales.json      # Vías con página propia fija
│   ├── nombres_vias.json          # Correcciones de nombres de vías (también para las páginas de /vias/)
│   └── nombres_visibles.json      # Correcciones solo del nombre mostrado en el mapa (no cambia URLs)
├── scripts/
│   ├── actualizar_datos.py        # Descarga, clasifica, geolocaliza y escribe el JSON
│   └── generar_paginas.py         # Páginas por vía, sitemap y robots.txt
├── tests/
│   ├── test_geocodificacion.py    # Geolocalización de direcciones y barrios rurales
│   ├── test_clasificacion.py      # Tipos: Corte, Suministro, Obras, Accidente...
│   ├── test_texto.py              # limpiar_texto, fechas, caja de Zaragoza, norm_local, UTM
│   ├── test_nombres.py            # Nombre legible de la calle: reglas, OSM y prioridades
│   ├── test_datos.py              # Contrato de data/incidencias.json y tipos de la web
│   └── test_paginas.py            # Utilidades de generar_paginas.py
├── data/
│   ├── incidencias.json           # Salida que consume la web (generada)
│   ├── geocache_v2.json           # Caché de geolocalización (generada)
│   ├── vias_conocidas.json        # Vías con obras de larga duración (generada)
│   └── historial_vias.json        # Incidencias finalizadas por vía (generada)
└── .github/workflows/
    ├── ci.yml                     # CI: validación de código y datos
    ├── ci-git-governance.yml      # CI: formato de los commits
    └── cd.yml                     # CD: datos, CI previo y despliegue en Pages
```

> El job de despliegue solo publica `*.html`, `*.jpg`, `*.png`, `*.ico`, `CNAME`, `ads.txt`, `robots.txt`, `sitemap.xml` y `data/`. Si añades un archivo de otro tipo a la web (CSS, JS externo…), inclúyelo en el paso «Preparar sitio» de `cd.yml` y de `ci.yml`. El archivo `.nojekyll` se crea al desplegar.

## Páginas de vías

`generar_paginas.py` crea una página por vía en `/vias/<slug>.html`:

- **Vías principales** (`config/vias_principales.json`): siempre existen. Cada una define `slug`, `nombre`, `tipo`, `patrones` (expresiones para reconocerla en el título) y un texto descriptivo.
- **Obras de larga duración**: si una calle no principal tiene una incidencia del Ayuntamiento de 60 días o más entre inicio y fin (`UMBRAL_DIAS`), se crea su página. Se guarda en `data/vias_conocidas.json` y sigue existiendo cuando acaba la obra.
- **Historial** (`data/historial_vias.json`): las incidencias ya finalizadas se muestran 30 días (`DIAS_HISTORIAL`). En carreteras (A-2, AP-68, Z-30, Z-40, N-232…) no se muestra historial, porque son avisos puntuales de la DGT.
- **SEO**: una página es `index,follow` si es una vía principal con incidencias (activas o recientes) o tiene una obra larga; en otro caso, `noindex,follow`. El sitemap incluye las páginas indexables.
- **Cortes de agua** (`/cortes-de-agua-zaragoza.html`): lista las incidencias de tipo `Suministro`.

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
      "nombre": "Calle Doctor Blanco Cordero",
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

`nombre` es el nombre legible de la calle (ver arriba) y solo existe en las incidencias del Ayuntamiento; `causa` solo aparece en las de la DGT (`Vehículo detenido`, `Accidente`…). `barrio` solo aparece en las incidencias del Ayuntamiento cuya calle lleva código de barrio rural. `trazado` solo aparece cuando `precision` es `calle`. Las incidencias que no se pueden ubicar no se incluyen y se cuentan en `sin_ubicar`.

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

**Tests** (no necesitan red ni `GEMINI_API_KEY`; `google-genai` es opcional para ejecutarlos y `pyproj` solo para el test de UTM, que se omite si no está):

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
- 🧪 **Ampliar los tests** (`tests/`): ahora cubren geolocalización, clasificación de tipos, limpieza de texto, normalización de calles, el formato de `incidencias.json` y utilidades de las páginas de vías; falta probar `fetch_dgt` y `fetch_ayuntamiento` con respuestas de ejemplo guardadas.
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
# 🚧 Obras e Incidencias Zaragoza

[![Tests y despliegue](https://img.shields.io/github/actions/workflow/status/aabadmo4/oi_zgz/cd.yml?branch=main&event=push&label=tests%20y%20despliegue)](https://github.com/aabadmo4/oi_zgz/actions/workflows/cd.yml)
[![Licencia: AGPL v3](https://img.shields.io/github/license/aabadmo4/oi_zgz)](LICENSE)
[![Datos actualizados](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fobraseincidenciaszaragoza.es%2Fdata%2Fincidencias.json&query=%24.actualizado&label=datos)](https://obraseincidenciaszaragoza.es/data/incidencias.json)

Mapa y listado de **obras, cortes de tráfico, accidentes y retenciones en Zaragoza**, construido a partir de datos públicos del Ayuntamiento de Zaragoza y de la DGT.

🌐 **Web:** https://obraseincidenciaszaragoza.es

> Servicio independiente y gratuito. **No es una fuente oficial**: la información es orientativa y hay que obedecer siempre la señalización.

## Cómo funciona

El sitio es una **página estática** (`index.html`) que lee `data/incidencias.json`. Ese archivo lo genera un script de Python que se ejecuta **cada hora** con GitHub Actions (lanzado por un [cron externo](#ejecución-horaria-cron-externo), porque el `cron` de GitHub no es fiable) y el resultado se publica en GitHub Pages. Otro script genera las páginas estáticas por vía (obras de larga duración y vías principales), la página de [cortes de agua](https://obraseincidenciaszaragoza.es/cortes-de-agua-zaragoza.html), la página de [datos abiertos](https://obraseincidenciaszaragoza.es/datos.html), el sitemap, el `robots.txt` y el `llms.txt`.

```
cron externo (cada hora) ─> GitHub Actions (CD, workflow_dispatch)
                                      │
Ayuntamiento (JSON) ─┐                ▼
                     ├─> scripts/actualizar_datos.py ─> data/incidencias.json ─┐
DGT NAP (DATEX II) ──┘         │                                               ├─> scripts/generar_paginas.py ─> GitHub Pages
                               └─ geolocalización: Nominatim (OSM) + Gemini    │   (vías, cortes de agua, datos.html,
                                                      data/ + config/ ─────────┘    sitemap, robots, llms.txt)
```

### Iconos del mapa y del listado

Cada incidencia se dibuja como un círculo de color con un icono. El icono y el color salen de `TIPOS` (en `index.html` y en `scripts/generar_paginas.py`, que deben coincidir: lo comprueba `tests/test_datos.py`).

| Icono | Tipo | Color | Cuándo se usa |
|---|---|---|---|
| ⛔ | `Corte` | `#ff6b5e` | Calle o calzada cerrada |
| 🚧 | `Obras` | `#ffc400` | Obras en la vía pública |
| 💥 | `Accidente` | `#ff9a3c` | Accidentes |
| 🚦 | `Retención` | `#e9d27a` | Tráfico lento (`abnormalTrafficType` de la DGT) |
| 💧 | `Suministro` | `#5ec8f2` | Cortes programados de agua, luz o gas |
| ⚠️ | `Otros` | `#c9ced3` | Cualquier otra incidencia |
| 🚗 | `Otros` (`causa` = `Vehículo detenido`) | `#c9ced3` | Aviso de la DGT de vehículo detenido |

- **Vehículo detenido (🚗):** no es un tipo nuevo. Sigue siendo `Otros` (mismo color y mismo filtro), pero se detecta por el campo `causa` y se dibuja con un coche en el mapa, el listado, la ficha, el texto de compartir y las páginas de vías (`visual()` en `generar_paginas.py`; `visual(i)` en `index.html`).
- **Cambio de icono en `Retención`:** antes usaba 🚗; ahora usa 🚦 para no confundirla con el vehículo detenido. Cambia también en el chip del filtro y en el texto de compartir.
- **Incidencia que aún no ha empezado** (`Próxima`, con `inicio` posterior a hoy): el icono se muestra con menos intensidad, desaturado y algo transparente (clases `.pin.fut` en el mapa y `.ico.fut` en el listado: `grayscale(.65) brightness(1.08)` y `opacity:.8`), y su marcador queda por debajo del resto. Al llegar la fecha de inicio recupera el color normal.
- **Borde discontinuo:** la incidencia afecta a toda la calle o su ubicación es orientativa (`precision` = `calle` o `aprox`).

### Funcionalidades de la web

- **Mapa** (Leaflet + OpenStreetMap) con un marcador por incidencia, con icono y color según el tipo. Un marcador con borde discontinuo indica que afecta a toda la calle o que su ubicación es orientativa.
- **Listado** de incidencias con filtro por tipo y por fuente, buscador por calle o motivo (sin distinguir acentos) y la opción «Solo lo que se ve en el mapa».
- **Ficha** de cada incidencia: tramo, detalle (con botón «Ver más» si es largo), fuente, barrio si lo hay, estado y botón **Abrir en Maps**. El estado se calcula en el navegador a partir de las fechas: `Próxima` (`Empieza mañana`, `Empieza en N días`), `En curso` (`Quedan N días` y barra de progreso), `Solo hoy`, `Termina hoy`, `Finalizada` o `Activa` (sin fechas). Las páginas estáticas usan los mismos estados.
- **Compartir**: genera un texto y un enlace `https://obraseincidenciaszaragoza.es/#<id>` (por ejemplo `#dgt-29808033`). Al abrir el enlace, el mapa se centra en esa incidencia y muestra su ficha. Usa el menú de compartir del móvil o, si no existe, el portapapeles.
- **Portada con contenido sin JavaScript**: `generar_paginas.py` rellena en la copia publicada de `index.html` los bloques `<!--INC-->` (incidencias actuales más relevantes), `<!--AGUA-->` (resumen de cortes de agua), `<!--VIAS-->` (enlaces a las vías), el párrafo `#resumen` y la fecha de `#estado`, para que buscadores y lectores sin JS vean datos reales. En el repositorio esos bloques están vacíos o con un texto de ejemplo.
- **Analítica y publicidad**: Google Analytics solo se activa si la persona acepta el banner de cookies provisional (consentimiento denegado por defecto en el EEE, Reino Unido y Suiza) y hay anuncios de AdSense en la portada (sin bloques de anuncio en las páginas de vías). Si cambias esto, actualiza `privacidad.html`.

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

El tipo puede ser `Accidente`, `Corte`, `Suministro`, `Obras`, `Retención` u `Otros`, y se calcula de forma distinta según la fuente:

- **Ayuntamiento:** `tipo_desde_texto()` clasifica por palabras clave del texto.
- **DGT:** `tipo_dgt()` decide por los **campos estructurados** del registro DATEX II, en este orden:
  1. `Accidente`, si `causeType` es `accident`.
  2. `Corte`, solo si `roadOrCarriagewayOrLaneManagementType` es `roadClosed` o `carriagewayClosures` (calzada completa cerrada).
  3. `Obras`, si `causeType` es `roadMaintenance`.
  4. `Retención`, si hay `abnormalTrafficType` (tráfico lento).
  5. Si nada de lo anterior aplica, se usa `tipo_desde_texto()` sobre el texto del registro **ignorando los códigos `*Closures`**. Un carril cerrado sin obras queda como `Otros`.

> **Por qué no se usa solo el texto en la DGT:** las obras llevan casi siempre `laneClosures` (cierre de *un carril*, no de la vía). Buscar «closure» como palabra clave marcaba como `Corte` obras que solo ocupan un carril (N-232, A-68…). Con una incidencia DGT de `Vehículo detenido` ocurre algo parecido: sigue siendo `Otros`, y para distinguirla (icono 🚗) se usa el campo `causa`.

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

2. **Normalización local** sin IA: `norm_local()` convierte textos como `BLANCO CORDERO (DR.), 11` en `Calle Doctor Blanco Cordero`, número `11`. `quitar_calificador()` elimina los calificadores del callejero que no forman parte del nombre real (`ASIA CONTINENTE` → `Calle Asia`; se aplica también a entradas antiguas de la caché o de Gemini).
3. **Nominatim (OpenStreetMap)** devuelve hasta 10 candidatos (respetando 1 petición por segundo) y el script elige:
   - **Con código de barrio:** solo acepta resultados cuya dirección sea ese barrio o que estén a menos de 3,5 km de su centro. Para estos casos se usa una caja geográfica más ancha, porque barrios como Peñaflor quedan fuera de la caja urbana. Algunos centros están fijados en `CENTROS_BARRIO`; el resto se buscan en Nominatim.
   - **Sin código:** descarta los resultados que Nominatim sitúa en un barrio rural. Así `MONCAYO, 8` es la calle del CP 50010 y no la de Casetas. Si solo hay resultados rurales, no se ubica en lugar de ubicarla mal.
   - Si la incidencia trae geometría oficial, se usa para elegir entre candidatos.
   - Si no encuentra el portal, busca solo la calle y guarda su trazado.
   - Si un barrio rural no encuentra la calle, se marca en el centro del barrio como `aprox`.
4. **Gemini** (modelo `gemini-3.6-flash`), solo para las direcciones que no se han podido localizar: normaliza el texto de la dirección en lotes de 40. **No genera coordenadas.** Si se agota la cuota diaria (error 429) no se reintenta, porque cada intento gasta cuota: el lote se deja para la siguiente ejecución horaria.
5. Los resultados se guardan en caché (`data/geocache_v2.json`): `norm` guarda la normalización de Gemini por texto original y `geo` las coordenadas. Las claves de `geo` llevan el prefijo `v3:` e incluyen el barrio; el script descarta las entradas antiguas sin ese prefijo.

### Nombre legible de la calle

El Ayuntamiento envía las calles como `VALENCIA AVENIDA DE, 41` o `PUERTA DE SANCHO AV., 9`. El campo `nombre` guarda el nombre ya escrito como se lee (`Avenida de Valencia`, `Avenida Puerta de Sancho`); el número de portal se muestra aparte en la ficha. Se elige por este orden (`nombre_final()`):

1. Corrección manual en `config/nombres_vias.json` o `config/nombres_visibles.json` (clave: `clave_nombre()` del título, p. ej. `blanco-cordero-dr`).
2. Nombre de OpenStreetMap o de Gemini, solo si contiene todas las palabras significativas del nombre original (`compatible()`).
3. Reglas locales (`nombre_por_reglas()`): reordenan el apellido y el nombre de pila (`CERBUNA PEDRO` → `Pedro Cerbuna`), colocan el tipo de vía delante, expanden abreviaturas (`AV.`, `CTRA.`…) y no tocan nombres de santos. **Antes de aplicarlas se quita el portal** (`, 41`); si se queda, se confunde con una palabra del nombre y aparece repetido junto a «nº 41».

El tramo (`via`) se limpia con `limpiar_tramo()`, que además de quitar HTML y entidades elimina la puntuación suelta al principio o al final (`, Entre C/ A y C/ B`).

Las incidencias que no se pueden ubicar se imprimen en el log como `SIN UBICAR: …`.

Valores de `precision`: `exacta` (DGT), `portal`, `calle`, `aprox`.

### CI/CD con GitHub Actions

Hay tres workflows, identificados en la pestaña *Actions*:

| Workflow | Archivo | Cuándo se ejecuta | Qué hace |
|---|---|---|---|
| **CI** | `.github/workflows/ci.yml` | En *pull requests*, en *push* a ramas distintas de `main`, y cuando lo llama CD | Comprueba la sintaxis de los scripts, que los JSON de `config/` y `data/` sean válidos, ejecuta los tests y comprueba que el sitio se genera. |
| **CI - Git Governance** | `.github/workflows/ci-git-governance.yml` | En cada *push* a `main`, `master` o `develop` | Llama al workflow reutilizable `TechECS/org-ci-workflows` (`conventional-commits-enforcement.yml`) para comprobar que los commits sigan [Conventional Commits](https://www.conventionalcommits.org/es/). |
| **CD** | `.github/workflows/cd.yml` | *Push* a `main`, **cron externo cada hora** (`workflow_dispatch` con `origen=cron-externo`), `cron` de GitHub (minuto 17 UTC, solo de respaldo) y ejecución manual (`workflow_dispatch`) | Ver abajo. |

**CD** tiene tres jobs:

1. **CI previo** (solo en *push*): llama a `ci.yml`. Si falla, no se despliega.
2. **Actualizar datos (APIs)** (en todas las ejecuciones que no son *push*: cron externo, cron de GitHub y manual): ejecuta `actualizar_datos.py`, valida el resultado con `tests/test_datos.py` (formato y valores), actualiza `vias_conocidas.json` e `historial_vias.json` con `generar_paginas.py` y hace *commit* de `data/` (como `TechDEV: OI_ZGZ Data Bot`, con el mensaje `chore(data): actualizar incidencias`) si todo fue bien. **Si el script o la validación fallan**, no se guarda nada y se publica la última versión válida.
3. **Desplegar en Pages**: genera las páginas de vías, los cortes de agua, `datos.html`, el sitemap, el `robots.txt` y el `llms.txt`, rellena los bloques de la portada y publica en GitHub Pages.

En un *push* a `main` se salta la descarga de datos y solo se vuelve a publicar la web.

Usa el secreto `GEMINI_API_KEY` del repositorio. Sin él, el script funciona igualmente pero sin el paso de apoyo de Gemini.

#### Ejecución horaria: cron externo

El `cron` de GitHub Actions (`schedule: '17 * * * *'`) no funciona de forma fiable: GitHub lo ejecuta con el mejor esfuerzo y en horas de mucha carga las ejecuciones se retrasan o no llegan a producirse, y no hay garantía de que se ejecute todas las horas. Por eso **la actualización horaria la dispara un cron externo** (un servicio fuera de GitHub) que cada hora lanza el workflow CD a mano a través de la API de GitHub.

- **Qué hace:** llama a `workflow_dispatch` de `cd.yml` sobre la rama `main` con la entrada `origen=cron-externo`. Es el mismo camino que el botón *Run workflow* de la pestaña *Actions*, solo que automático.
- **Cómo se reconoce:** el nombre de la ejecución (`run-name`) indica quién la lanzó: `⏱ cron externo`, `🖐 manual` (dispatch sin `origen`), `🕐 cron GitHub` (el `schedule` de respaldo) o `⬆ push`. Así se ve en *Actions* si el cron externo está funcionando.
- **Qué ejecuta:** los jobs *Actualizar datos (APIs)* y *Desplegar en Pages*, igual que cualquier ejecución programada o manual.
- **Petición** (sustituye `<TOKEN>`; hace falta un token con permiso para ejecutar workflows en este repositorio, p. ej. un *fine-grained token* con *Actions: Read and write*):

  ```bash
  curl -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer <TOKEN>" \
    https://api.github.com/repos/aabadmo4/oi_zgz/actions/workflows/cd.yml/dispatches \
    -d '{"ref":"main","inputs":{"origen":"cron-externo"}}'
  ```

  GitHub responde `204 No Content` si ha aceptado la petición.
- **Seguridad:** el token debe guardarse solo en el servicio de cron externo; **nunca** se sube al repositorio.
- **Si falla el cron externo:** el `schedule` de GitHub sigue en `cd.yml` como respaldo, así que los datos se actualizan igualmente, solo que con menos regularidad. El grupo de `concurrency` (`cd`, sin cancelar ejecuciones en curso) evita que dos lanzamientos simultáneos se pisen: la segunda ejecución espera a que termine la primera.

## Estructura del repositorio

```
.
├── index.html                     # Aplicación (HTML + CSS + JS, sin build)
├── acerca.html
├── avisolegal.html
├── privacidad.html
├── robots.txt                     # (se regenera al desplegar)
├── sitemap.xml                    # (se regenera al desplegar)
├── ads.txt                        # Google AdSense
├── CNAME                          # Dominio personalizado en GitHub Pages
├── favicon.ico, icon-*.png, apple-touch-icon.png, obraseincidenciaszaragoza.jpg   # Iconos e imagen
├── config/
│   ├── vias_principales.json      # Vías con página propia fija
│   ├── nombres_vias.json          # Correcciones de nombres de vías (también para las páginas de /vias/)
│   └── nombres_visibles.json      # Correcciones solo del nombre mostrado en el mapa (no cambia URLs)
├── scripts/
│   ├── actualizar_datos.py        # Descarga, clasifica, geolocaliza y escribe el JSON
│   └── generar_paginas.py         # Páginas por vía, cortes de agua, datos.html, sitemap, robots.txt y llms.txt
├── tests/
│   ├── test_geocodificacion.py    # Geolocalización de direcciones y barrios rurales
│   ├── test_clasificacion.py      # Tipos: Corte, Suministro, Obras, Accidente...
│   ├── test_dgt.py                # Tipo de los registros DGT por campos DATEX II (carril cerrado vs. corte)
│   ├── test_texto.py              # limpiar_texto, fechas, caja de Zaragoza, norm_local, UTM
│   ├── test_nombres.py            # Nombre legible de la calle: reglas, OSM y prioridades
│   ├── test_datos.py              # Contrato de data/incidencias.json (cabecera, licencia, campos) y tipos de la web
│   └── test_paginas.py            # generar_paginas.py: estados, robots.txt, llms.txt, datos.html, licencia
├── data/
│   ├── incidencias.json           # Salida que consume la web (generada)
│   ├── geocache_v2.json           # Caché de geolocalización (generada)
│   ├── vias_conocidas.json        # Vías con obras de larga duración (generada)
│   └── historial_vias.json        # Incidencias finalizadas por vía (generada)
└── .github/workflows/
    ├── ci.yml                     # CI: validación de código y datos
    ├── ci-git-governance.yml      # CI: formato de los commits
    └── cd.yml                     # CD: datos, CI previo y despliegue en Pages (lo lanza el cron externo cada hora)
```

> El job de despliegue solo publica `*.html`, `*.jpg`, `*.png`, `*.ico`, `CNAME`, `ads.txt`, `robots.txt`, `sitemap.xml` y `data/`. `llms.txt`, `datos.html`, `cortes-de-agua-zaragoza.html` y `vias/` no están en el repositorio: los crea `generar_paginas.py` al desplegar. Si añades un archivo de otro tipo a la web (CSS, JS externo…), inclúyelo en el paso «Preparar sitio» de `cd.yml` y de `ci.yml`. El archivo `.nojekyll` se crea al desplegar.

## Páginas de vías

`generar_paginas.py` crea una página por vía en `/vias/<slug>.html`:

- **Vías principales** (`config/vias_principales.json`): siempre existen. Cada una define `slug`, `nombre`, `tipo`, `patrones` (expresiones para reconocerla en el título) y un texto descriptivo.
- **Obras de larga duración**: si una calle no principal tiene una incidencia del Ayuntamiento de 60 días o más entre inicio y fin (`UMBRAL_DIAS`), se crea su página. Se guarda en `data/vias_conocidas.json` y sigue existiendo cuando acaba la obra.
- **Historial** (`data/historial_vias.json`): las incidencias ya finalizadas se muestran 30 días (`DIAS_HISTORIAL`). En carreteras (A-2, AP-68, Z-30, Z-40, N-232…) no se muestra historial, porque son avisos puntuales de la DGT.
- **SEO**: una página es `index,follow` si es una vía principal con incidencias (activas o recientes) o tiene una obra larga; en otro caso, `noindex,follow`. El sitemap incluye las páginas indexables.
- **Cortes de agua** (`/cortes-de-agua-zaragoza.html`): lista las incidencias de tipo `Suministro` (agua), agrupadas por día (hoy y próximos días), con mapa y preguntas frecuentes (`FAQPage`). La portada incluye un resumen con enlace a esta página.

### Datos abiertos para buscadores y agentes de IA

`generar_paginas.py` genera además, en cada despliegue:

- **`/datos.html`**: documentación de `data/incidencias.json` (frecuencia horaria, significado de cada campo de la incidencia y de la cabecera, cómo se deduce el estado de un aviso, licencia y atribución). Lleva marcado `Dataset` de schema.org. Un test comprueba que todos los campos del JSON están documentados (`CAMPOS` y `CAMPOS_RAIZ`).
- **`/llms.txt`**: resumen en Markdown para modelos de lenguaje ([llmstxt.org](https://llmstxt.org)), con enlaces a los datos y a las páginas principales.
- **`/robots.txt`**: todo permitido y con los rastreadores de IA nombrados (`GPTBot`, `ClaudeBot`, `PerplexityBot`, `Google-Extended`, `CCBot`…, lista `AGENTES_IA`). No se bloquean las páginas `noindex`, para que Google pueda ver la etiqueta y retirarlas del índice.
- **Licencia de los datos tratados: CC BY 4.0**, con un texto de atribución fijo (`ATRIBUCION`) que también viaja dentro del JSON. Los datos originales mantienen las condiciones de reutilización del Ayuntamiento y de la DGT. El texto debe ser idéntico en `actualizar_datos.py` (`LICENCIA_DATOS`) y `generar_paginas.py` (`LICENCIA`, `ATRIBUCION`); un test lo vigila.

## Formato de `data/incidencias.json`

```json
{
  "actualizado": "2026-11-10T01:01+01:00",
  "licencia": "CC BY 4.0",
  "licencia_url": "https://creativecommons.org/licenses/by/4.0/deed.es",
  "atribucion": "Origen de los datos: Ayuntamiento de Zaragoza y Dirección General de Tráfico (DGT). …",
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

`actualizado` está en hora de Madrid. `licencia`, `licencia_url` y `atribucion` son los datos de reutilización (ver «Datos abiertos»). `nombre` es el nombre legible de la calle (ver arriba) y solo existe en las incidencias del Ayuntamiento; `causa` solo aparece en las de la DGT (`Vehículo detenido`, `Accidente`…). `barrio` solo aparece en las incidencias del Ayuntamiento cuya calle lleva código de barrio rural. `trazado` solo aparece cuando `precision` es `calle`. Las incidencias que no se pueden ubicar no se incluyen y se cuentan en `sin_ubicar`.

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

**Sitio completo** (igual que hace el workflow CD al desplegar: copia los archivos estáticos y genera las páginas de vías, los cortes de agua, `datos.html`, `sitemap.xml`, `robots.txt` y `llms.txt`, además de rellenar los bloques de la portada). La carpeta de salida es `_site` por defecto:

```bash
mkdir _site
cp -r *.html *.jpg *.png *.ico CNAME ads.txt robots.txt sitemap.xml data _site/
python scripts/generar_paginas.py _site
```

Ojo: `generar_paginas.py` también actualiza `data/vias_conocidas.json` y `data/historial_vias.json` en tu copia local; no los subas a mano en una PR.

**Lanzar el workflow a mano** (como lo hace el cron externo; ver [Ejecución horaria](#ejecución-horaria-cron-externo)): pestaña *Actions* → *CD* → *Run workflow*, o con la API de GitHub.

## Cómo colaborar

Toda ayuda es bienvenida. Algunas ideas basadas en el estado actual del código:

- 🏷️ **Mejorar la clasificación** de tipos (`tipo_desde_texto` para el Ayuntamiento, `tipo_dgt` para la DGT) con ejemplos reales que queden como `Otros` o mal clasificados (como los cortes de agua, que antes salían como `Corte`).
- 🔤 **Ampliar la normalización de direcciones** (`TIPOS_VIA`, `HONORIFICOS`) con abreviaturas del callejero que fallen.
- 📍 **Reducir las incidencias `sin_ubicar`** o las de precisión `aprox`, y completar `CENTROS_BARRIO` con los barrios rurales que falten.
- 📡 **Añadir fuentes** (tranvía, autobús, eventos, otras administraciones).
- 🧪 **Ampliar los tests** (`tests/`): ahora cubren geolocalización, clasificación de tipos, limpieza de texto, normalización de calles, el formato y la licencia de `incidencias.json`, y `generar_paginas.py` (estados, `robots.txt`, `llms.txt`, `datos.html`, páginas de vías); falta probar `fetch_dgt` y `fetch_ayuntamiento` con respuestas de ejemplo guardadas.
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
- **Los datos generados** (`data/`) los actualiza el bot (`TechDEV: OI_ZGZ Data Bot`) cada hora; no los edites a mano en una PR.
- **El cron externo** que lanza el CD cada hora es parte de la infraestructura: no cambies el nombre del workflow (`cd.yml`) ni la entrada `origen` sin actualizar también el cron.
- **Privacidad y publicidad:** si cambias cookies, analítica o anuncios, actualiza `privacidad.html`.
- **Accesibilidad:** foco visible, `aria-label` en controles, buen contraste.

## Créditos

- [Ayuntamiento de Zaragoza](https://www.zaragoza.es/) y [DGT](https://www.dgt.es/) (datos públicos)
- Mapa y geocodificación: © colaboradores de [OpenStreetMap](https://www.openstreetmap.org/copyright), [Nominatim](https://nominatim.org/)
- Mapa interactivo: [Leaflet](https://leafletjs.com/)

## Licencia

El **código** se distribuye bajo los términos de la licencia **GNU Affero General Public License v3.0 (AGPLv3)**. Consulta el archivo [`LICENSE`](./LICENSE) para obtener más detalles.

Los **datos tratados** que publica la web (`data/incidencias.json`) se ofrecen bajo **CC BY 4.0** con la atribución indicada en el propio archivo y en [`/datos.html`](https://obraseincidenciaszaragoza.es/datos.html). Los datos originales mantienen las condiciones de reutilización del Ayuntamiento de Zaragoza y de la DGT.

## Contacto

Adán Nahir Abad Mora · TechECS_EU · techecs.eu@gmail.com
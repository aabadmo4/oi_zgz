# Ideas y tareas pendientes

Ideas para la web, con la numeración acordada. La **1 (filtro por estado)** y la **2 (leyenda de iconos)** ya están hechas y documentadas en el README.

## Barra de controles del mapa

El filtro por estado (🕒) y la leyenda de iconos (ℹ️) viven en una columna de botones arriba a la derecha del mapa. Esa esquina se reserva para los siguientes controles:

- 📍 **Cerca de mí** (idea 3), debajo de los actuales.

Abajo a la derecha no se coloca nada: ahí va la atribución de Leaflet y OpenStreetMap. Los botones van en una columna (`.mc-bar`) con el estilo de los de zoom de Leaflet, miden 40 px, sin borde propio, llevan `aria-label` y `aria-expanded` si despliega un panel, y se cierra con Escape o al tocar fuera.

## Pendientes

3. **Cerca de mí:** botón 📍 que pide la ubicación del navegador y ordena o filtra por distancia (por ejemplo, a menos de 1 km). Todo se calcula en el cliente; no se guarda la posición.
4. **Nueva hoy:** insignia en las incidencias vistas por primera vez hoy, a partir de `data/historial_vias.json`.
5. **Mis calles (nivel 1)**, todo guardado en el navegador (`localStorage`), sin cuenta ni servidor:
   - **5a.** ⭐ «Seguir esta calle» en la ficha y chip «⭐ Mis calles» que filtra el listado. Varias calles se muestran con «o» (cualquiera de ellas), con un tope de unas 20 y un panel para dejar de seguirlas. Seguir una calle cuenta para toda la calle, sea cual sea el número de portal (pendiente de confirmar).
   - **5b.** Banner «novedades desde tu última visita». Una sola línea con el total y las 2 o 3 primeras novedades, y un botón «Ver» que activa «Mis calles» y marca cada incidencia como «Nueva» o «Terminada». Cuenta como cambio una incidencia nueva, una que ha terminado o desaparecido, o una «Próxima» que ya está en curso. Requiere guardar una foto de los identificadores de la última visita. Sin esa foto (primera vez) no se muestra banner.

## Aplazadas

- **Canal de Telegram** con publicación automática de las incidencias nuevas y las que terminan (gratis, encaja con el cron externo). También serviría para avisos sin montar servidor.
- **Publicar la PWA** (manifest, `sw.js`, iconos, aviso de instalación), ya preparada. Con la app instalada la web funciona con mala cobertura, pero no avisa por sí sola.
- **Avisos push reales:** necesitan guardar la suscripción de cada persona (dato personal: actualizar `privacidad.html` y pedir permiso) y un servidor mínimo que envíe los avisos. En iPhone solo funcionan con la web instalada como PWA.

## Descartadas

- **Añadir incidencias a mano:** todo viene de las fuentes del Ayuntamiento y la DGT.
- **«¿Me afecta mi trayecto?» (origen y destino):** exige geocodificación y rutas, y choca con el coste cero.
- **Formulario propio para avisar al Ayuntamiento:** si se hace, será un enlace desde la ficha a su canal oficial.

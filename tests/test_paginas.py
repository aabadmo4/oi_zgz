"""Utilidades de generar_paginas.py (sin red ni dependencias externas)."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import generar_paginas as g


def _cargar_datos():
    import json
    return json.loads((Path(__file__).resolve().parent.parent / "data/incidencias.json").read_text(encoding="utf-8"))


class TestPaginas(unittest.TestCase):
    def test_es_agua_sin_la_palabra_agua_en_el_motivo(self):
        """Regresión: el motivo del Ayuntamiento (\"Para reparar toma...\") no incluye \"agua\"; seguía siendo un corte de agua."""
        base = {"tipo": "Suministro", "titulo": "LA PAZ 19"}
        for motivo in ("Para reparar toma de C/ La Paz, n.º 27. Vol: 14877", "Cambio llave de paso",
                       "Para condenar boca de riego", "Para conectar tuberías. UTE Portillo."):
            with self.subTest(motivo=motivo):
                self.assertTrue(g.es_agua({**base, "detalle": motivo}))
        self.assertFalse(g.es_agua({**base, "detalle": "Corte de luz programado"}))
        self.assertFalse(g.es_agua({**base, "detalle": "Corte de gas en el edificio"}))
        self.assertFalse(g.es_agua({"tipo": "Obras", "titulo": "X", "detalle": "Cortes de agua"}))

    def test_los_datos_actuales_muestran_los_suministros_como_cortes_de_agua(self):
        incs = _cargar_datos()["incidencias"]
        suministros = [i for i in incs if i["tipo"] == "Suministro"]
        self.assertTrue(all(g.es_agua(i) for i in suministros))





    def test_pagina_cortes_agua_tiene_buscador_y_popup_compacto(self):
        d = _cargar_datos()
        html = g.pagina_cortes_agua(d["incidencias"], "https://ejemplo.es", d["actualizado"], "2026-11-23")
        self.assertIn('role="search"', html)
        self.assertIn('<label class="lbl" for="q">', html)
        self.assertNotIn('name="filtro"', html)  # sin filtros por estado
        self.assertNotIn("Termina hoy", html)  # el estado ya lo da la etiqueta («Solo hoy», «Próxima»…)
        self.assertNotIn('class="ver"', html)  # la celda entera abre el mapa; no hay botón aparte
        self.assertEqual(html.count("data-t="), 7)  # un elemento buscable por aviso
        self.assertIn("pu-b", html)  # ficha emergente con botón «Abrir en Maps»
        self.assertNotIn("</script><", html.split("var PTS=")[1].split(",C=")[0])  # los datos no cierran el <script>
        # sin avisos no se pintan ni buscador ni mapa
        vacia = g.pagina_cortes_agua([], "https://ejemplo.es", d["actualizado"], "2026-11-23")
        self.assertNotIn('id="buscador"', vacia)
        self.assertIn("no hay cortes de agua programados", vacia)

    def test_popup_aviso_compacto_sin_duplicar_fechas(self):
        i = {"id": "zgz-1", "tipo": "Suministro", "titulo": "LA PAZ 19", "detalle": "Cambio llave de paso", "inicio": "2026-11-24", "fin": "2026-11-24",
             "lat": 41.6, "lon": -0.88, "precision": "aprox", "nombre": "Calle la Paz 19"}
        h = g.popup_aviso(i, "Calle la Paz 19", "2026-11-23")
        self.assertIn("Próxima", h)
        self.assertEqual(h.count("24 de noviembre"), 1)  # la fecha sale solo en la etiqueta de estado
        self.assertIn("Ubicación aproximada", h)
        self.assertIn('rel="noopener"', h)

    def test_busqueda_sin_tildes_en_texto_buscable(self):
        i = {"id": "zgz-1", "tipo": "Suministro", "titulo": "LA PAZ 19", "detalle": "Cambio de válvulas", "inicio": "2026-11-23", "fin": "2026-11-23",
             "lat": 41.6, "lon": -0.88, "precision": "portal", "nombre": "Calle la Paz 19"}
        html = g.pagina_cortes_agua([i], "https://ejemplo.es", "2026-11-23T09:01+01:00", "2026-11-23")
        self.assertIn("valvulas", html.split('data-t="')[1].split('"')[0])

    def test_iconos_vehiculo_detenido_y_retencion(self):
        # Vehículo detenido (DGT, tipo Otros) lleva coche; la retención ya no, para no confundirlos
        self.assertEqual(g.visual({"tipo": "Otros", "causa": "Vehículo detenido"})[0], "🚗")
        self.assertEqual(g.visual({"tipo": "Retención"})[0], "🚦")
        self.assertEqual(g.visual({"tipo": "Otros", "causa": "Vehículo averiado"})[0], "⚠️")
        self.assertEqual(g.visual({"tipo": "Otros"})[0], "⚠️")
        self.assertEqual(g.visual({"tipo": "Otros", "causa": "Vehículo detenido"})[1], g.TIPOS["Otros"][1])
        self.assertNotIn("🚗", [e for e, _ in g.TIPOS.values()])

    def test_slug(self):
        self.assertEqual(g.slug("Avenida de Valencia"), "avenida-de-valencia")
        self.assertEqual(g.slug("Calle Sádaba"), "calle-sadaba")
        self.assertEqual(g.slug("  Z-30 "), "z-30")

    def test_titulo_ficha(self):
        i = {"fuente": "Ayuntamiento", "titulo": "CERBUNA PEDRO, 39"}
        self.assertEqual(g.titulo_ficha(i, "Calle Pedro Cerbuna"), "Calle Pedro Cerbuna, 39")
        self.assertEqual(g.titulo_ficha({"fuente": "Ayuntamiento", "titulo": "COSO, 0"}, "Coso"), "Coso")
        self.assertEqual(g.titulo_ficha({"fuente": "DGT", "titulo": "Z-40"}, "x"), "Z-40")

    def test_nombre_corte_usa_nombre_corregido(self):
        # El corte de agua debe mostrar el mismo nombre que la lista general (campo "nombre" de incidencias.json)
        i = {"titulo": "OCEANIA CONTINENTE, 13", "nombre": "Calle de Oceanía"}
        self.assertEqual(g.nombre_corte(i), "Calle de Oceanía")
        self.assertEqual(g.titulo_ficha({**i, "fuente": "Ayuntamiento"}, g.nombre_corte(i)), "Calle de Oceanía, 13")
        # Sin "nombre" se mantiene el comportamiento anterior
        self.assertEqual(g.nombre_corte({"titulo": "ITALIA, 16"}), "Calle Italia")

    def test_cuando_con_estado(self):
        hoy = "2026-11-08"
        prox = {"inicio": "2026-11-09", "fin": "2026-11-09"}
        self.assertEqual(g.cuando(prox, hoy), "Próxima · Empieza mañana · 9 de noviembre de 2026")
        rango = {"inicio": "2026-11-12", "fin": "2026-12-20"}
        self.assertEqual(g.cuando(rango, hoy), "Próxima · Empieza en 4 días · Del 12 de noviembre al 20 de diciembre de 2026")
        self.assertEqual(g.cuando({"inicio": "2026-11-09", "fin": "2026-11-20"}, hoy), "Próxima · Empieza mañana · Del 9 al 20 de noviembre de 2026")
        curso = {"inicio": "2026-11-01", "fin": "2026-12-31"}
        self.assertEqual(g.cuando(curso, hoy), "En curso · Del 1 de noviembre al 31 de diciembre de 2026")
        self.assertEqual(g.cuando({"fin": "2026-12-31"}, hoy), "En curso · Hasta el 31 de diciembre de 2026")
        self.assertEqual(g.cuando({"inicio": "2026-11-08", "fin": "2026-11-08"}, hoy), "Solo hoy")
        self.assertEqual(g.cuando({"inicio": "2026-11-01", "fin": "2026-11-08"}, hoy), "Termina hoy")
        self.assertEqual(g.cuando({"inicio": "2026-10-01", "fin": "2026-11-02"}, hoy), "Finalizada · Terminó el 2 de noviembre de 2026")
        self.assertEqual(g.cuando({}, hoy), "Activa")
        # estado_html: píldora para próxima/finalizada/hoy y negrita para en curso
        self.assertIn('class="est est-prox">Próxima</span> Empieza mañana', g.estado_html(prox, hoy))
        self.assertIn('class="est est-hoy">Solo hoy</span>', g.estado_html({"inicio": hoy, "fin": hoy}, hoy))
        self.assertIn('class="est-curso">En curso</strong>', g.estado_html(curso, hoy))
        # sin fecha de referencia: formato clásico
        self.assertEqual(g.cuando(curso), "Hasta el 31 de diciembre de 2026")

    def test_robots_nombra_agentes_ia(self):
        r = g.robots_txt("https://ejemplo.es")
        for a in g.AGENTES_IA:
            self.assertIn(f"User-agent: {a}\n", r)
        self.assertNotIn("Disallow", r)  # no se bloquea nada (las páginas noindex deben poder rastrearse)
        self.assertIn("Sitemap: https://ejemplo.es/sitemap.xml", r)

    def test_llms_txt(self):
        t = g.llms_txt("https://ejemplo.es", "2026-11-09T02:01+01:00", 67)
        self.assertTrue(t.startswith("# Obras e Incidencias Zaragoza"))
        for url in ("https://ejemplo.es/data/incidencias.json", "https://ejemplo.es/datos.html", "https://ejemplo.es/cortes-de-agua-zaragoza.html"):
            self.assertIn(url, t)
        self.assertIn(g.ATRIBUCION, t)
        self.assertIn("67", t)

    def test_pagina_datos(self):
        import json as _json, re as _re
        h = g.pagina_datos("https://ejemplo.es", "2026-11-09T02:01+01:00", 67)
        ld = _json.loads(_re.search(r'<script type="application/ld\+json">(.*?)</script>', h, _re.S).group(1))
        ds = next(x for x in ld["@graph"] if x["@type"] == "Dataset")
        self.assertEqual(ds["distribution"][0]["contentUrl"], "https://ejemplo.es/data/incidencias.json")
        self.assertEqual(ds["license"], g.LICENCIA_URL)
        self.assertEqual(ds["dateModified"], "2026-11-09T02:01+01:00")
        self.assertGreaterEqual(len(ds["description"]), 50)
        # Search Console: cada Dataset (también los de isBasedOn) necesita description, license y creator
        for d in [ds] + ds["isBasedOn"]:
            self.assertEqual(d["@type"], "Dataset")
            self.assertGreaterEqual(len(d["description"]), 50, d["name"])
            self.assertTrue(d["license"].startswith("https://"), d["name"])
            self.assertTrue(d["creator"]["name"], d["name"])
        self.assertIn('rel="alternate" type="application/json"', h)
        self.assertIn(g.ATRIBUCION.replace("&", "&amp;"), h)

    def test_documentados_todos_los_campos_del_json(self):
        d = _cargar_datos()
        usados = {k for i in d["incidencias"] for k in i}
        self.assertEqual(usados - set(g.CAMPOS), set(), "campos del JSON sin documentar en CAMPOS")

    def test_licencia_igual_en_datos_y_web(self):
        import actualizar_datos as a
        self.assertEqual(a.LICENCIA_DATOS["licencia"], g.LICENCIA)
        self.assertEqual(a.LICENCIA_DATOS["licencia_url"], g.LICENCIA_URL)
        self.assertEqual(a.LICENCIA_DATOS["atribucion"], g.ATRIBUCION)

    def test_duracion_y_obras_largas(self):
        larga = {"fuente": "Ayuntamiento", "inicio": "2026-01-01", "fin": "2026-12-31"}
        corta = {"fuente": "Ayuntamiento", "inicio": "2026-11-01", "fin": "2026-11-05"}
        self.assertEqual(g.duracion(corta), 4)
        self.assertTrue(g.es_larga(larga))
        self.assertFalse(g.es_larga(corta))
        self.assertFalse(g.es_larga({**larga, "fuente": "DGT"}))
        self.assertIsNone(g.duracion({"inicio": None, "fin": "2026-01-01"}))

    def test_fechas_en_castellano(self):
        self.assertEqual(g.fecha("2026-11-06"), "6 de noviembre de 2026")
        self.assertEqual(g.fecha("basura"), "")

    def test_esc_neutraliza_html(self):
        self.assertNotIn("<script>", g.esc("<script>alert(1)</script>"))
        self.assertEqual(g.esc(None), "")


if __name__ == "__main__":
    unittest.main()

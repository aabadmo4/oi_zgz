"""Utilidades de generar_paginas.py (sin red ni dependencias externas)."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import generar_paginas as g


def _cargar_datos():
    import json
    return json.loads((Path(__file__).resolve().parent.parent / "data/incidencias.json").read_text(encoding="utf-8"))


class TestPaginas(unittest.TestCase):
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

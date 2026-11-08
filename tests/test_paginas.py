"""Utilidades de generar_paginas.py (sin red ni dependencias externas)."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import generar_paginas as g


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
        curso = {"inicio": "2026-11-01", "fin": "2026-12-31"}
        self.assertEqual(g.cuando(curso, hoy), "En curso · Del 1 de noviembre al 31 de diciembre de 2026")
        self.assertEqual(g.cuando({"fin": "2026-12-31"}, hoy), "En curso · Hasta el 31 de diciembre de 2026")
        self.assertEqual(g.cuando({"inicio": "2026-11-08", "fin": "2026-11-08"}, hoy), "Solo hoy")
        self.assertEqual(g.cuando({"inicio": "2026-11-01", "fin": "2026-11-08"}, hoy), "Termina hoy")
        self.assertEqual(g.cuando({"inicio": "2026-10-01", "fin": "2026-11-02"}, hoy), "Finalizada · Hasta el 2 de noviembre de 2026")
        self.assertEqual(g.cuando({}, hoy), "Activa")
        # sin fecha de referencia: formato clásico
        self.assertEqual(g.cuando(curso), "Hasta el 31 de diciembre de 2026")

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

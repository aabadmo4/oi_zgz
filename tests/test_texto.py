"""Limpieza de texto, fechas, caja de Zaragoza, normalización de calles y conversión UTM. Sin red."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import actualizar_datos as a


class TestTexto(unittest.TestCase):
    def test_limpiar_texto(self):
        self.assertEqual(a.limpiar_texto("<p>Obras&nbsp;en  la v&iacute;a</p>"), "Obras en la vía")
        self.assertEqual(a.limpiar_texto("&amp;oacute; y &amp;amp;"), "ó y &")  # doble codificación
        self.assertEqual(a.limpiar_texto(None), "")
        ficha = "Dirección: X, 3 Tipo: Obras Inicio: 01/01 Fin: 02/02 Observaciones: Renovar tubería"
        self.assertEqual(a.limpiar_texto(ficha), "Obras. Renovar tubería")

    def test_dia(self):
        self.assertEqual(a.dia("2026-11-06T08:00:00+01:00"), "2026-11-06")
        self.assertEqual(a.dia("2026-11-06"), "2026-11-06")
        self.assertIsNone(a.dia(None))
        self.assertIsNone(a.dia(""))

    def test_caja_de_zaragoza(self):
        self.assertTrue(a.en_zgz(41.6488, -0.8891))   # centro
        self.assertTrue(a.en_zgz("41.65", "-0.89"))   # textos numéricos
        self.assertFalse(a.en_zgz(40.4168, -3.7038))  # Madrid
        self.assertFalse(a.en_zgz(None, None))
        self.assertFalse(a.en_zgz("x", "y"))


class TestTramo(unittest.TestCase):
    def test_limpiar_tramo(self):
        self.assertEqual(a.limpiar_tramo(", Entre C/ Rodrigo Rebolledo y C/ Monasterio de Siresa"), "Entre C/ Rodrigo Rebolledo y C/ Monasterio de Siresa")
        self.assertEqual(a.limpiar_tramo("Entre C/Rioja y C/ Julián Ribera, "), "Entre C/Rioja y C/ Julián Ribera")
        self.assertEqual(a.limpiar_tramo("Números pares, entre C/ Juan Porcell y C/ Rufas"), "Números pares, entre C/ Juan Porcell y C/ Rufas")
        self.assertEqual(a.limpiar_tramo(None), "")


class TestNormLocal(unittest.TestCase):
    def test_honorifico_y_numero(self):
        self.assertEqual(a.norm_local("BLANCO CORDERO (DR.), 11"), {"via": "Calle Doctor Blanco Cordero", "numero": "11"})

    def test_tipo_de_via_entre_parentesis(self):
        r = a.norm_local("ALBARDIN (CTRA.), 6")
        self.assertEqual(r["via"], "Carretera Albardin")
        self.assertEqual(r["numero"], "6")

    def test_minusculas_y_sin_numero(self):
        r = a.norm_local("CONSEJO DE CIENTO")
        self.assertEqual(r["via"], "Calle Consejo de Ciento")
        self.assertIsNone(r["numero"])

    def test_numero_desde_el_motivo(self):
        r = a.norm_local("PAZ, 0-5", "Para reparar el vertido a la altura del n.o 3")
        self.assertEqual(r["numero"], "3")


class TestUTM(unittest.TestCase):
    @unittest.skipUnless(a.UTM, "requiere pyproj")
    def test_utm_a_wgs84(self):
        from pyproj import Transformer
        x, y = Transformer.from_crs(4326, 25830, always_xy=True).transform(-0.8773, 41.6561)  # Plaza del Pilar
        self.assertGreater(x, 1000)  # así lo detecta coords_geometria como UTM
        lat, lon = a.coords_geometria({"geometry": {"coordinates": [x, y]}})
        self.assertAlmostEqual(lat, 41.6561, places=4)
        self.assertAlmostEqual(lon, -0.8773, places=4)

    def test_geometria_ya_en_wgs84_o_fuera_de_caja(self):
        self.assertEqual(a.coords_geometria({"geometry": {"coordinates": [-0.8891, 41.6488]}}), (41.6488, -0.8891))
        self.assertIsNone(a.coords_geometria({"geometry": {"coordinates": [-3.7038, 40.4168]}}))
        self.assertIsNone(a.coords_geometria({}))


if __name__ == "__main__":
    unittest.main()

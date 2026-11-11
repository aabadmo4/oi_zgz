"""Tests sin red: Nominatim se sustituye por respuestas simuladas."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import actualizar_datos as a


def falso_buscar(params, ancha=False):
    q = params.get("q", "") + params.get("street", "")
    if "Moncayo" in q:
        return [{"lat": "41.7206", "lon": "-1.0264", "address": {"suburb": "Casetas"}},
                {"lat": "41.6499", "lon": "-0.8954", "address": {"suburb": "Delicias"}}]
    if "Enmedio" in q:
        return [{"lat": "41.7034", "lon": "-0.9679", "address": {"suburb": "Monzalbarba"}},
                {"lat": "41.7615", "lon": "-0.7983", "address": {"village": "Peñaflor de Gállego"}}]
    if "San Juan de la Pe" in q:
        return [{"lat": "41.5926", "lon": "-0.9332", "address": {"town": "Cuarte de Huerva"}},
                {"lat": "41.6700", "lon": "-0.8800", "address": {"city": "Zaragoza", "suburb": "San José"}}]
    return []


class TestGeo(unittest.TestCase):
    def setUp(self):
        self._orig, a._buscar = a._buscar, falso_buscar

    def tearDown(self):
        a._buscar = self._orig

    def test_separar_barrio(self):
        self.assertEqual(a.separar_barrio("ENMEDIO           PÑF, 2"), ("ENMEDIO, 2", "PÑF"))
        self.assertEqual(a.separar_barrio("MONCAYO, 8"), ("MONCAYO, 8", None))
        self.assertEqual(a.separar_barrio("SAN JOSE AVENIDA DE, 77"), ("SAN JOSE AVENIDA DE, 77", None))

    def test_calle_urbana_no_cae_en_barrio_rural(self):
        g = a.nominatim("Calle Moncayo", "8")
        self.assertAlmostEqual(g["lon"], -0.8954, places=3)

    def test_calle_de_barrio_rural(self):
        g = a.nominatim("Calle Enmedio", "2", "PÑF", None, {})
        self.assertAlmostEqual(g["lat"], 41.7615, places=3)

    def test_descarta_otro_municipio(self):
        g = a.nominatim("Avenida San Juan de la Peña", "35")
        self.assertAlmostEqual(g["lat"], 41.67, places=2)  # no la de Cuarte de Huerva (41.59)

    def test_barrio_rural_sin_zaragoza_no_se_rechaza(self):
        # direcciones de barrios que Nominatim da con el nombre del barrio y sin 'Zaragoza'
        for dire in ({"village": "Peñaflor"}, {"suburb": "Casetas"}, {"hamlet": "Juslibol"}, {"town": "Villamayor de Gállego"}):
            self.assertFalse(a.en_otro_municipio({"address": dire, "display_name": "Calle X, Barrio, Aragón, España"}))

    def test_municipios_vecinos_y_calle_con_nombre_de_vecino(self):
        self.assertTrue(a.en_otro_municipio({"address": {"town": "Cuarte de Huerva"}}))
        self.assertTrue(a.en_otro_municipio({"address": {}, "display_name": "Calle San Juan de la Peña, Cuarte de Huerva, Zaragoza, España"}))
        self.assertFalse(a.en_otro_municipio({"address": {"city": "Zaragoza"}, "display_name": "Calle Utebo, Delicias, Zaragoza, España"}))

    def test_tipo_de_via_al_final(self):
        self.assertEqual(a.norm_local("SAN JUAN DE LA PEÑA AV, 35"), {"via": "Avenida San Juan de la Peña", "numero": "35"})

    def test_todos_los_barrios_tienen_alias(self):
        self.assertEqual(set(a.ALIAS_ZONA), set(a.BARRIOS))


if __name__ == "__main__":
    unittest.main()

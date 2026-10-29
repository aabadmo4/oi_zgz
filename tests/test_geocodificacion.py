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

    def test_todos_los_barrios_tienen_alias(self):
        self.assertEqual(set(a.ALIAS_ZONA), set(a.BARRIOS))


if __name__ == "__main__":
    unittest.main()

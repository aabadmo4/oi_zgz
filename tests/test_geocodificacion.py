"""Tests sin red: Nominatim se sustituye por respuestas simuladas."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import actualizar_datos as a


def falso_buscar(params, ancha=False):
    q = params.get("q", "") + params.get("street", "")
    if "Calle de la Paz" in q:  # OSM la llama "de la Paz": "Calle La Paz" no casa
        return [{"lat": "41.6426", "lon": "-0.8854", "address": {"city": "Zaragoza"}, "category": "building"}]
    if "Moncayo" in q:
        return [{"lat": "41.7206", "lon": "-1.0264", "address": {"suburb": "Casetas"}},
                {"lat": "41.6499", "lon": "-0.8954", "address": {"suburb": "Delicias"}}]
    if "Enmedio" in q:
        return [{"lat": "41.7034", "lon": "-0.9679", "address": {"suburb": "Monzalbarba"}},
                {"lat": "41.7615", "lon": "-0.7983", "address": {"village": "Peñaflor de Gállego"}}]
    if "San Juan de la Pe" in q:
        return [{"lat": "41.5926", "lon": "-0.9332", "address": {"town": "Cuarte de Huerva"}},
                {"lat": "41.6700", "lon": "-0.8800", "address": {"city": "Zaragoza", "suburb": "San José"}}]
    if "Caspe" in q:
        return [{"lat": "41.5747", "lon": "-1.0762", "address": {"town": "La Muela"}},
                {"lat": "41.6499", "lon": "-0.8960", "address": {"city": "Zaragoza", "suburb": "Delicias"}}]
    if "Ribaforada" in q:  # sin municipio declarado y fuera de VECINOS: solo lo frena el radio
        return [{"lat": "41.9500", "lon": "-1.4000", "address": {}, "display_name": "Calle X, Ribaforada, Navarra, España"},
                {"lat": "41.6500", "lon": "-0.8900", "address": {"city": "Zaragoza"}}]
    if "Fueros de Arag" in q:
        return [{"lat": "41.7581", "lon": "-1.0649", "address": {"village": "Torres de Berrellén"}},
                {"lat": "41.6458", "lon": "-0.8947", "address": {"city": "Zaragoza", "suburb": "Delicias"}}]
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

    def test_parentesis_es_inicio_del_nombre(self):
        self.assertEqual(a.norm_local("ARAGON (FUEROS DE), 15"), {"via": "Calle Fueros de Aragon", "numero": "15"})
        self.assertEqual(a.norm_local("BLANCO CORDERO (DR.), 11"), {"via": "Calle Doctor Blanco Cordero", "numero": "11"})

    def test_descarta_municipios_no_listados(self):
        self.assertTrue(a.en_otro_municipio({"address": {"town": "La Muela"}}))
        self.assertTrue(a.en_otro_municipio({"address": {"village": "Torres de Berrellén"}}))

    def test_caspe_y_fueros_caen_en_delicias(self):
        self.assertAlmostEqual(a.nominatim("Calle Caspe", "5")["lat"], 41.6499, places=3)
        self.assertAlmostEqual(a.nominatim("Calle Fueros de Aragon", "15")["lat"], 41.6458, places=3)

    def test_radio_urbano_frena_pueblo_sin_municipio_declarado(self):
        self.assertTrue(a.fuera_del_radio_urbano({"lat": "41.95", "lon": "-1.40"}))
        self.assertTrue(a.fuera_del_radio_urbano({"lat": "41.5747", "lon": "-1.0762"}))  # La Muela
        self.assertFalse(a.fuera_del_radio_urbano({"lat": "41.5950", "lon": "-0.9150"}))  # Arcosur
        g = a.nominatim("Calle Ribaforada", "3")
        self.assertAlmostEqual(g["lat"], 41.65, places=2)

    def test_vecinos_incluye_los_pueblos_detectados(self):
        for v in ("la muela", "torres de berrellen"):
            self.assertIn(v, a.VECINOS)

    def test_tipo_de_via_al_final(self):
        self.assertEqual(a.norm_local("SAN JUAN DE LA PEÑA AV, 35"), {"via": "Avenida San Juan de la Peña", "numero": "35"})

    def test_todos_los_barrios_tienen_alias(self):
        self.assertEqual(set(a.ALIAS_ZONA), set(a.BARRIOS))

class TestVariantesVia(unittest.TestCase):
    def test_articulo_inicial(self):
        self.assertEqual(a.variantes_via("Calle La Paz"), ["Calle La Paz", "Calle de la Paz", "Calle Paz"])
        self.assertEqual(a.variantes_via("Calle El Pozo")[1], "Calle del Pozo")

    def test_sin_articulo_no_cambia(self):
        self.assertEqual(a.variantes_via("Calle Caspe"), ["Calle Caspe"])

    def test_la_paz_se_ubica(self):
        orig = a._buscar
        a._buscar = falso_buscar
        try:
            geo = a.nominatim("Calle La Paz", "19")
        finally:
            a._buscar = orig
        self.assertIsNotNone(geo)
        self.assertAlmostEqual(geo["lat"], 41.6426, places=3)



if __name__ == "__main__":
    unittest.main()

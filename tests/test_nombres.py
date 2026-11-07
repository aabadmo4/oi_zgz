"""Nombre legible de la calle: reglas de reordenación, validación del nombre de OSM y prioridades. Sin red."""
import json, sys, unittest
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import actualizar_datos as a

# (calle sin número ni barrio, nombre esperado por reglas)
REGLAS = [
    ("MADRID AVENIDA DE", "Avenida de Madrid"),
    ("SAN JOSE AVENIDA DE", "Avenida de San José"),
    ("COGULLADA CARRETERA", "Carretera de Cogullada"),
    ("ALFOCEA CAMINO DE", "Camino de Alfocea"),
    ("PILON CN. EL", "Camino del Pilon"),
    ("PUERTA DE SANCHO AV.", "Avenida Puerta de Sancho"),
    ("AGUSTIN PASEO MARIA", "Paseo María Agustín"),
    ("CUARTA AVENIDA", "Cuarta Avenida"),
    ("CERBUNA PEDRO", "Calle Pedro Cerbuna"),
    ("QUINTO AGUSTIN DE", "Calle Agustín de Quinto"),
    ("REBOLLEDO RODRIGO DE", "Calle Rodrigo de Rebolledo"),
    ("LORENTE JUAN JOSE", "Calle Juan José Lorente"),
    ("EDISON TOMAS A", "Calle Tomás A. Edison"),
    ("TABOADA EDUARDO JES.", "Calle Eduardo Jesús Taboada"),
    ("BURRIEL (ALCALDE)", "Calle Alcalde Burriel"),
    ("CASANOVA JOSE (FRAY)", "Calle Fray José Casanova"),
    ("CABALLERO FCO(ALCALDE", "Calle Alcalde Francisco Caballero"),  # el origen corta el texto a 24 caracteres
    ("CADENA(MARQUES DE LA)", "Calle Marqués de la Cadena"),
    ("BLANCO CORDERO (DR.)", "Calle Doctor Blanco Cordero"),
    ("MALPICA II (CALLE D)", "Malpica II (Calle D)"),
    ("VIRGEN LA", "Calle de la Virgen"),
    ("CONSEJO DE CIENTO", "Calle Consejo de Ciento"),
    ("MOLINO DE LAS ARMAS", "Calle Molino de las Armas"),
    ("ECHEGARAY Y CABALLERO", "Calle Echegaray y Caballero"),
    ("JOS\u00c9 ATAR\u00c9S", "Calle Jos\u00e9 Atar\u00e9s"),  # ya viene en orden natural
    ("COSO", "Calle Coso"),
    ("N-232", "N-232"),
]


class TestReglas(unittest.TestCase):
    def test_reglas(self):
        for calle, esperado in REGLAS:
            with self.subTest(calle=calle):
                self.assertEqual(a.nombre_por_reglas(calle), esperado)

    def test_no_invierte_nombres_de_santos(self):
        self.assertEqual(a.nombre_por_reglas("SAN JOSE"), "Calle San José")


class TestCompatibleYOsm(unittest.TestCase):
    def test_acepta_nombres_con_las_mismas_palabras(self):
        self.assertTrue(a.compatible("Paseo de María Agustín", "Paseo María Agustín"))
        self.assertTrue(a.compatible("Calle de Pedro Cerbuna", "Calle Pedro Cerbuna"))
        self.assertTrue(a.compatible("Avenida de Madrid", "Avenida de Madrid"))

    def test_rechaza_otra_calle(self):
        self.assertFalse(a.compatible("Calle de Alcalá", "Calle Pedro Cerbuna"))
        self.assertFalse(a.compatible("Calle de Blanco Cordero", "Calle Doctor Blanco Cordero"))  # falta 'doctor'
        self.assertFalse(a.compatible(None, "Calle Coso"))

    def test_nombre_osm(self):
        self.assertEqual(a.nombre_osm({"address": {"road": " Avenida de Madrid "}}), "Avenida de Madrid")
        self.assertEqual(a.nombre_osm({"category": "highway", "name": "Calle Coso", "address": {}}), "Calle Coso")
        self.assertIsNone(a.nombre_osm({"category": "building", "name": "Edificio", "address": {}}))


class TestPrioridad(unittest.TestCase):
    def test_manual_gana_a_todo(self):
        n = a.nombre_final("AGUSTIN PASEO MARIA, 13", "AGUSTIN PASEO MARIA", osm="Paseo de María Agustín",
                           manual={"agustin-paseo-maria": "Nombre manual"})
        self.assertEqual(n, "Nombre manual")

    def test_osm_compatible_gana_a_las_reglas(self):
        n = a.nombre_final("AGUSTIN PASEO MARIA, 13", "AGUSTIN PASEO MARIA", osm="Paseo de María Agustín")
        self.assertEqual(n, "Paseo de María Agustín")

    def test_osm_incompatible_se_ignora(self):
        n = a.nombre_final("CERBUNA PEDRO, 5", "CERBUNA PEDRO", osm="Calle de Alcalá")
        self.assertEqual(n, "Calle Pedro Cerbuna")

    def test_sin_osm_ni_gemini_usa_reglas(self):
        self.assertEqual(a.nombre_final("MADRID AVENIDA DE, 154", "MADRID AVENIDA DE"), "Avenida de Madrid")

    def test_siglas_de_barrio_no_son_tipos_de_via(self):
        """'ALBARDIN CRT': CRT es Cartuja Baja (ver BARRIOS), no 'carretera'. La calle ya llega sin la sigla."""
        sb, barrio = a.separar_barrio("ALBARDIN CRT")
        self.assertEqual(barrio, "CRT")
        self.assertEqual(a.nombre_final("ALBARDIN CRT, 6", sb), "Calle Albardin")
        corr = json.loads((RAIZ / "config/nombres_vias.json").read_text(encoding="utf-8"))
        self.assertEqual(corr["albardin-crt"], "Calle Albardín")

    def test_clave_coincide_con_la_de_nombres_vias(self):
        self.assertEqual(a.clave_nombre("BLANCO CORDERO (DR.), 11"), "blanco-cordero-dr")
        self.assertEqual(a.clave_nombre("ENMEDIO P\u00d1F, 2"), "enmedio-pnf")


if __name__ == "__main__":
    unittest.main()

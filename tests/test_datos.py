"""Contrato de data/incidencias.json: lo que la web (index.html) da por hecho. Sin red."""
import json, re, sys, unittest, datetime
from pathlib import Path
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))
import actualizar_datos as a

TIPOS = {"Corte", "Obras", "Accidente", "Retención", "Suministro", "Otros"}
PRECISIONES = {"exacta", "portal", "calle", "aprox"}
FUENTES = {"Ayuntamiento", "DGT"}


class TestContratoDatos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads((RAIZ / "data/incidencias.json").read_text(encoding="utf-8"))
        cls.inc = cls.d["incidencias"]

    @staticmethod
    def dentro(i):
        """Los barrios rurales (Peñaflor, Casetas...) usan la caja ancha; el resto, la urbana."""
        if i.get("barrio"):
            la0, la1, lo0, lo1 = a.CAJA_ANCHA
            return la0 <= i["lat"] <= la1 and lo0 <= i["lon"] <= lo1
        return a.en_zgz(i["lat"], i["lon"])

    def test_cabecera(self):
        datetime.datetime.fromisoformat(self.d["actualizado"])
        self.assertIsInstance(self.d["sin_ubicar"], int)
        self.assertTrue(self.inc, "no hay incidencias")

    def test_ids_unicos(self):
        ids = [i["id"] for i in self.inc]
        self.assertEqual(len(ids), len(set(ids)))

    def test_campos_y_valores(self):
        for i in self.inc:
            with self.subTest(id=i.get("id")):
                self.assertIn(i["tipo"], TIPOS)
                self.assertIn(i["precision"], PRECISIONES)
                self.assertIn(i["fuente"], FUENTES)
                self.assertTrue(i["titulo"])
                if "nombre" in i:  # lo añade actualizar_datos.py a las incidencias del Ayuntamiento
                    self.assertIsInstance(i["nombre"], str)
                    self.assertTrue(i["nombre"].strip())
                    self.assertFalse(len(i["nombre"]) > 5 and i["nombre"].isupper(), "nombre sin normalizar")
                self.assertTrue(self.dentro(i), "fuera de la zona cubierta")
                for k in ("inicio", "fin"):
                    if i.get(k):
                        datetime.date.fromisoformat(i[k])  # solo formato; el orden depende de la fuente

    def test_trazado_solo_con_precision_calle(self):
        for i in self.inc:
            if "trazado" in i:
                with self.subTest(id=i["id"]):
                    self.assertEqual(i["precision"], "calle")

    def test_tipos_coinciden_con_la_web(self):
        """Todo tipo que pueda producir tipo_desde_texto debe tener icono en TIPOS de index.html."""
        html = (RAIZ / "index.html").read_text(encoding="utf-8")
        bloque = re.search(r"const TIPOS=\{(.*?)\};", html, re.S).group(1)
        en_web = set(re.findall(r"(?:^|,)\s*'?([A-Za-zñÑóÓ]+)'?\s*:\s*\[", bloque))
        self.assertEqual(en_web, TIPOS)


if __name__ == "__main__":
    unittest.main()

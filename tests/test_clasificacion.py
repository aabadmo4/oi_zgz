"""Clasificación de tipos: protege los casos que ya dieron problemas (p. ej. cortes de agua)."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import actualizar_datos as a

CASOS = [
    ("Cortes de Agua. Desde las 8 hasta las 18 horas", "Suministro"),
    ("Corte de luz programado en el edificio", "Suministro"),
    # El Ayuntamiento manda un campo "tipo" y el script lo antepone al motivo (ver fetch_ayuntamiento)
    ("Corte Para la reforma de las calles es necesario el corte de las calles", "Corte"),
    ("Obras Continuando con las obras de la Avenida de Valencia", "Obras"),
    ("Calle cerrada al tráfico por obras", "Corte"),
    ("Accidente de tráfico en la Z-30", "Accidente"),
    ("Accidente con corte de un carril", "Accidente"),  # accidente tiene prioridad sobre corte
    ("Trabajos de mantenimiento del firme", "Obras"),
    ("Obras de renovación de servicios", "Obras"),
    ("Retención en la A-2 sentido Madrid", "Retención"),
    ("Instalación de balizas luminosas en pasos de peatones", "Otros"),
    ("", "Otros"),
]


class TestTipos(unittest.TestCase):
    def test_casos(self):
        for texto, esperado in CASOS:
            with self.subTest(texto=texto):
                self.assertEqual(a.tipo_desde_texto(texto), esperado)


if __name__ == "__main__":
    unittest.main()

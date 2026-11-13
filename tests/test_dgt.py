import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from lxml import etree
import actualizar_datos as a

NS = ('xmlns:sit="http://levelC/schema/3/situation" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
      'xmlns:com="http://levelC/schema/3/common"')


def rec(causa, gestion=None, xsi="sit:RoadOrCarriagewayOrLaneManagement"):
    g = f"<sit:roadOrCarriagewayOrLaneManagementType>{gestion}</sit:roadOrCarriagewayOrLaneManagementType>" if gestion else ""
    x = (f'<sit:situationRecord {NS} xsi:type="{xsi}" id="1"><sit:cause><sit:causeType>{causa}</sit:causeType></sit:cause>{g}</sit:situationRecord>')
    r = etree.fromstring(x)
    xp = lambda rec_, q: [t.strip() for t in rec_.xpath(q) if t.strip()]
    crudo = (r.get(a.XSI) or "") + " " + " ".join(xp(r, ".//text()"))
    return a.tipo_dgt(r, xp, crudo)


class TestTipoDGT(unittest.TestCase):
    def test_obras_con_carril_cerrado_son_obras(self):
        self.assertEqual(rec("roadMaintenance", "laneClosures"), "Obras")

    def test_calzada_cerrada_es_corte(self):
        self.assertEqual(rec("roadMaintenance", "carriagewayClosures"), "Corte")
        self.assertEqual(rec("obstruction", "roadClosed"), "Corte")

    def test_carril_cerrado_sin_obras_no_es_corte(self):
        self.assertEqual(rec("vehicleObstruction", "laneClosures"), "Otros")

    def test_accidente(self):
        self.assertEqual(rec("accident", "laneClosures"), "Accidente")

    def test_trafico_lento(self):
        self.assertEqual(rec("abnormalTraffic"), "Retención")


if __name__ == "__main__":
    unittest.main()

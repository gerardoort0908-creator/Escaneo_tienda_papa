import asyncio

from app.escaneos import Escaneo, Pantallas, RegistroEscaneos


def _e(i):
    return Escaneo(id=f"id-{i:06d}", codigo="7501055363056", formato="ean_13", t_detectado=0, t_recibido=0)


def test_reintento_no_cuenta_dos_veces():
    r = RegistroEscaneos()
    assert r.agregar(_e(1))
    assert not r.agregar(_e(1))
    assert r.duplicados_evitados == 1
    assert len(r) == 1


def test_mismo_codigo_con_otro_id_si_cuenta():
    r = RegistroEscaneos()
    assert r.agregar(_e(1)) and r.agregar(_e(2))


def test_memoria_limitada():
    r = RegistroEscaneos(capacidad=3)
    for i in range(5):
        r.agregar(_e(i))
    assert len(r) == 3
    assert r.agregar(_e(0))  # el más viejo ya se olvidó


class _Pantalla:
    def __init__(self, falla=False):
        self.recibido, self.falla = [], falla

    async def send_text(self, data):
        if self.falla:
            raise ConnectionError("cerrada")
        self.recibido.append(data)


def test_avisar_quita_pantallas_caidas():
    p = Pantallas()
    buena, caida = _Pantalla(), _Pantalla(falla=True)
    p.conectar(buena)
    p.conectar(caida)
    asyncio.run(p.avisar({"tipo": "escaneo"}))
    assert buena.recibido == ['{"tipo": "escaneo"}']
    assert p.cuantas == 1

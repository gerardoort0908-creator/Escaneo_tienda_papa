"""Las tablas de la tienda y qué módulo es dueño de cada una.

Regla: cada módulo solo escribe en sus propias tablas. Si Ventas necesita
descontar inventario, se lo pide al módulo de Productos (no toca su tabla).
Las pruebas revisan que esta regla se cumpla.

Nada se borra: las ventas se cancelan, los productos y clientes se desactivan,
y los movimientos no se pueden modificar. La base de datos misma lo impide.
"""

from __future__ import annotations

DUENOS: dict[str, set[str]] = {
    "productos": {"productos", "historial_precios", "movimientos_inventario"},
    "ventas": {"ventas", "venta_lineas"},
    "fiado": {"clientes", "fiado_movimientos"},
    "caja": {"cortes", "caja_retiros"},
    "reportes": set(),  # solo lee
}

_V1 = """
CREATE TABLE productos (
    id              INTEGER PRIMARY KEY,
    codigo          TEXT UNIQUE,
    nombre          TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    unidad          TEXT NOT NULL CHECK (unidad IN ('pieza', 'kg')),
    precio_venta    INTEGER NOT NULL CHECK (precio_venta > 0 AND precio_venta % 100 = 0),
    costo_promedio  INTEGER NOT NULL DEFAULT 0 CHECK (costo_promedio >= 0),
    minimo          INTEGER NOT NULL DEFAULT 0 CHECK (minimo >= 0),
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado          TEXT NOT NULL,
    actualizado     TEXT NOT NULL
);
CREATE INDEX productos_nombre ON productos (nombre COLLATE NOCASE);

CREATE TABLE historial_precios (
    id           INTEGER PRIMARY KEY,
    producto_id  INTEGER NOT NULL REFERENCES productos (id),
    precio_venta INTEGER NOT NULL,
    costo        INTEGER NOT NULL,
    motivo       TEXT NOT NULL,
    cuando       TEXT NOT NULL
);
CREATE INDEX historial_producto ON historial_precios (producto_id);

-- La existencia de un producto es la suma de sus movimientos (piezas o gramos).
CREATE TABLE movimientos_inventario (
    id             INTEGER PRIMARY KEY,
    producto_id    INTEGER NOT NULL REFERENCES productos (id),
    cantidad       INTEGER NOT NULL CHECK (cantidad <> 0),
    tipo           TEXT NOT NULL CHECK (tipo IN ('llegada', 'venta', 'cancelacion', 'ajuste')),
    costo_unitario INTEGER,
    venta_id       INTEGER,
    nota           TEXT,
    cuando         TEXT NOT NULL
);
CREATE INDEX movimientos_producto ON movimientos_inventario (producto_id);
CREATE VIEW existencias AS
    SELECT p.id AS producto_id, COALESCE(SUM(m.cantidad), 0) AS existencia
    FROM productos p LEFT JOIN movimientos_inventario m ON m.producto_id = p.id
    GROUP BY p.id;

CREATE TABLE clientes (
    id        INTEGER PRIMARY KEY,
    nombre    TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    telefono  TEXT,
    nota      TEXT,
    activo    INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado    TEXT NOT NULL
);

CREATE TABLE ventas (
    id            INTEGER PRIMARY KEY,
    cuando        TEXT NOT NULL,
    forma_pago    TEXT NOT NULL CHECK (forma_pago IN ('efectivo', 'fiado')),
    total         INTEGER NOT NULL CHECK (total > 0),
    costo_total   INTEGER NOT NULL CHECK (costo_total >= 0),
    recibido      INTEGER,
    cambio        INTEGER,
    cliente_id    INTEGER REFERENCES clientes (id),
    estado        TEXT NOT NULL DEFAULT 'hecha' CHECK (estado IN ('hecha', 'cancelada')),
    cancelada     TEXT,
    motivo_cancel TEXT,
    CHECK (forma_pago = 'fiado' OR (recibido >= total AND cambio = recibido - total)),
    CHECK (forma_pago = 'efectivo' OR cliente_id IS NOT NULL)
);
CREATE INDEX ventas_cuando ON ventas (cuando);

-- Cada renglón guarda nombre, precio y costo del momento: si mañana cambia el
-- precio, la venta de hoy sigue diciendo lo que de verdad se cobró.
CREATE TABLE venta_lineas (
    id              INTEGER PRIMARY KEY,
    venta_id        INTEGER NOT NULL REFERENCES ventas (id),
    producto_id     INTEGER NOT NULL REFERENCES productos (id),
    nombre          TEXT NOT NULL,
    unidad          TEXT NOT NULL,
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario INTEGER NOT NULL,
    subtotal        INTEGER NOT NULL CHECK (subtotal > 0),
    costo           INTEGER NOT NULL CHECK (costo >= 0)
);
CREATE INDEX lineas_venta ON venta_lineas (venta_id);
CREATE INDEX lineas_producto ON venta_lineas (producto_id);

-- Saldo de un cliente = suma de sus movimientos (cargos positivos, abonos negativos).
CREATE TABLE fiado_movimientos (
    id          INTEGER PRIMARY KEY,
    cliente_id  INTEGER NOT NULL REFERENCES clientes (id),
    tipo        TEXT NOT NULL CHECK (tipo IN ('cargo', 'abono', 'cancelacion')),
    monto       INTEGER NOT NULL CHECK (monto <> 0),
    venta_id    INTEGER,
    nota        TEXT,
    cuando      TEXT NOT NULL,
    CHECK ((tipo = 'cargo') = (monto > 0))
);
CREATE INDEX fiado_cliente ON fiado_movimientos (cliente_id);

CREATE TABLE cortes (
    id         INTEGER PRIMARY KEY,
    abierto    TEXT NOT NULL,
    fondo      INTEGER NOT NULL CHECK (fondo >= 0),
    cerrado    TEXT,
    esperado   INTEGER,
    contado    INTEGER,
    diferencia INTEGER,
    nota       TEXT
);
CREATE UNIQUE INDEX un_corte_abierto ON cortes ((cerrado IS NULL)) WHERE cerrado IS NULL;

CREATE TABLE caja_retiros (
    id        INTEGER PRIMARY KEY,
    corte_id  INTEGER NOT NULL REFERENCES cortes (id),
    monto     INTEGER NOT NULL CHECK (monto > 0),
    nota      TEXT,
    cuando    TEXT NOT NULL
);
"""


def _no_borrar(tabla: str, que: str) -> str:
    return (
        f"CREATE TRIGGER no_borrar_{tabla} BEFORE DELETE ON {tabla} "
        f"BEGIN SELECT RAISE(ABORT, '{que}'); END;\n"
    )


def _no_cambiar(tabla: str) -> str:
    return (
        f"CREATE TRIGGER no_cambiar_{tabla} BEFORE UPDATE ON {tabla} "
        f"BEGIN SELECT RAISE(ABORT, 'Los movimientos guardados no se modifican'); END;\n"
    )


_PROTECCION = (
    _no_borrar("productos", "Los productos no se borran: se desactivan")
    + _no_borrar("clientes", "Los clientes no se borran: se desactivan")
    + _no_borrar("ventas", "Las ventas no se borran: se cancelan")
    + "".join(
        _no_borrar(t, "Los movimientos guardados no se borran") + _no_cambiar(t)
        for t in ("venta_lineas", "movimientos_inventario", "fiado_movimientos",
                  "historial_precios", "caja_retiros")
    )
    + _no_borrar("cortes", "Los cortes de caja no se borran")
    # Una venta solo puede pasar de hecha a cancelada; sus cifras no se tocan.
    + """
CREATE TRIGGER venta_solo_se_cancela BEFORE UPDATE ON ventas
WHEN OLD.estado = 'cancelada'
  OR NEW.estado <> 'cancelada'
  OR NEW.total IS NOT OLD.total OR NEW.costo_total IS NOT OLD.costo_total
  OR NEW.recibido IS NOT OLD.recibido OR NEW.cambio IS NOT OLD.cambio
  OR NEW.cuando IS NOT OLD.cuando OR NEW.forma_pago IS NOT OLD.forma_pago
  OR NEW.cliente_id IS NOT OLD.cliente_id
BEGIN SELECT RAISE(ABORT, 'Una venta solo se puede cancelar una vez y sus cifras no cambian'); END;
CREATE TRIGGER corte_cerrado_fijo BEFORE UPDATE ON cortes
WHEN OLD.cerrado IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'Un corte de caja cerrado ya no se modifica'); END;
"""
)

# Cada versión nueva se agrega al final; nunca se cambia una que ya se usó.
MIGRACIONES: list[str] = [_V1 + _PROTECCION]

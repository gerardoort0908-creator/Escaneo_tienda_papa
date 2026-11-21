# Punto de venta de la tienda

| Carpeta | Qué es |
|---|---|
| `tienda/` | Cimientos (Fase 1): base de datos, dinero, inventario, ventas, fiado, caja, reportes, respaldos |
| `app/` | Servidor y pantallas: Vender y cobrar, escáner del celular |

## Vender y cobrar

| Para | Mac | Windows |
|---|---|---|
| Usar la tienda de verdad | `iniciar.command` | `iniciar.bat` |
| Practicar con productos de ejemplo | `probar-ejemplo.command` | `probar-ejemplo.bat` |

Lo de práctica se guarda aparte (`datos/ejemplo/`) y no se mezcla con lo real.

1. **Escanear**: el producto aparece arriba de la lista y se ilumina; se oye un bip. Si se
   escanea otra vez, se suma en el mismo renglón. También se puede buscar por nombre o
   teclear el código (F2, o simplemente empezar a escribir).
2. **Ajustar**: − y + en cada renglón. El huevo y lo de granel van de medio kilo en medio kilo.
3. **Cobrar** (Enter): se tocan los billetes y monedas que dio el cliente, o se escribe otra
   cantidad. Muestra cuánto falta o el cambio. "Pagó exacto" cobra de una vez.
4. **Cambio**: el número grande y con qué billetes y monedas darlo. Enter o cualquier
   escaneo empieza la siguiente venta.

- **Cancelar venta** (antes de cobrar) borra la cuenta sin guardar nada. Pide tocar dos veces.
- **Cancelar esta venta** (ya cobrada) pide el motivo, regresa la mercancía al inventario y la
  venta queda guardada como cancelada.
- **Código no registrado**: sale una ventanita para darlo de alta con nombre y precio y se
  agrega a la venta.
- Antes de guardar, el servidor revisa que el total sea el mismo que se vio en pantalla (si
  alguien cambió un precio, avisa) y un doble Enter nunca cobra dos veces.
## Productos

- Lista con barra de existencias: verde **Bien**, ámbar **Se está acabando** (llegó al mínimo),
  rojo **Se acabó**. Filtros para ver solo los que se acaban o los desactivados.
- Al tocar uno: nombre, código, **Te cuesta** (con centavos) y **Lo vendes en** (pesos cerrados),
  cuánto ganas por pieza y el mínimo ("Avísame cuando queden"). Los cambios de precio y costo
  quedan en su historial; las ventas pasadas no cambian.
- **Contar lo que hay**: si en el anaquel hay otra cantidad, se corrige (conteo, merma, caducado…).
- **Ya no lo vendo**: deja de salir para vender pero su historia se queda.
- Escanear un código desconocido abre el alta con ese código; si el producto a la vista no
  tiene código, se lo pone.

## Llegó mercancía

Se escanea lo que llegó; cada escaneo suma una pieza (o un kilo). Se ajusta cuántos son y
cuánto costó cada uno. Al guardar se suma al inventario y el costo se vuelve el **costo
promedio** (si había 10 a $10 y llegan 10 a $12, cada uno cuesta $11).

- Computadora lenta: `http://localhost:8000/vender?ligero=1` quita los efectos de vidrio.
  Se activa solo en computadoras de 2 núcleos o menos.

## Préstamos (fiado)

En Vender, al cobrar, el botón **No pagó: es préstamo** abre la lista de clientes. Se elige
uno (o se escribe un nombre nuevo y se da de alta ahí mismo) y la venta se le carga.
La mercancía sale del inventario igual que en una venta normal.

La pantalla **Préstamos** muestra quién debe y cuánto, qué se llevó cada vez y lo que ha
pagado. Para registrar un pago: botones rápidos ($20, $50...), escribir otra cantidad o
**Pagó todo**. Un cliente solo se puede quitar de la lista cuando ya no debe nada.

## Corte de caja

1. **Abrir la caja** con el dinero con que se empieza (el fondo).
2. Durante el día, **Sacar dinero** (pagar a un proveedor, un gasto) y anotar para qué.
3. Al final, contar los billetes y monedas; la pantalla dice si **cuadra**, **sobra** o
   **falta**. Debe haber = fondo + ventas en efectivo + pagos de fiado − lo que se sacó.

Lo fiado no entra a la caja (no es dinero todavía); entra cuando el cliente paga.

## Reportes

Se elige el periodo (Hoy, Ayer, Esta semana, Este mes, Mes pasado o fechas a mano) y se ve:

- Cuánto se vendió, cuánto se ganó, cuánto entró en efectivo y cuánto deben.
- Gráfica de ventas y ganancia por día (o por hora, si es un solo día).
- Lo que más se vende, por dinero o por ganancia.
- Lo que hay que comprar, lo que no se vendió nada (dinero parado) y quién debe.

**Imprimir o PDF** abre la ventana de imprimir en hoja blanca (ahí mismo se puede
"Guardar como PDF"). **Excel** descarga un archivo con hojas de resumen, por día,
más vendidos, cada venta, lo que se está acabando, préstamos y cortes de caja.

La primera vez que se abre esta versión instala `openpyxl` (para el Excel); necesita internet.

## Cimientos (Fase 1)

Todavía sin pantallas: es la parte de adentro que guarda y cuida los datos.

- **Un solo archivo** `datos/tienda.sqlite` con todo. Respaldo automático cada día en
  `datos/respaldos/diarios/` (se guardan los últimos 30) y cada mes en
  `datos/respaldos/tienda-AAAA-MM.sqlite` (esos no se borran). Se revisa que cada copia esté sana.
- **Dinero en centavos enteros**: $22 se guarda como 2200; nunca se pierde un centavo.
  Precio de venta en pesos cerrados; el costo sí lleva centavos.
- **Inventario = suma de movimientos** (llegadas, ventas, cancelaciones, ajustes por conteo).
  El huevo se cuenta en gramos y se vende de medio kilo en medio kilo.
- **Todo o nada**: una venta guarda venta, renglones, salida de inventario y cargo de fiado
  juntos, o nada.
- **Nada se borra**: las ventas se cancelan, productos y clientes se desactivan. La propia
  base de datos lo impide aunque alguien lo intente por fuera.
- **Módulos independientes**: cada uno escribe solo en sus tablas (`tienda/nucleo/esquema.py`);
  una prueba lo revisa. Un registro por módulo en `datos/registros/ventas.log`, `fiado.log`, etc.

# Prueba del escáner (Fase 0)

Experimento para comprobar que **cualquier celular** (Android o iPhone) puede leer
códigos de barras con su cámara y mandarlos por el WiFi a la computadora, que los
muestra al instante. Todavía no es la app de la tienda: solo el escáner.

## Cómo arrancarlo

| Computadora | Qué hacer |
|---|---|
| Mac | Doble clic en `iniciar.command` |
| Windows | Doble clic en `iniciar.bat` |

La primera vez tarda un minuto porque descarga lo necesario (necesita internet y Python 3.10 o más nuevo).
Después se abre sola la pantalla en el navegador: `http://localhost:8000/pantalla`.

Si la computadora pregunta si deja que Python reciba conexiones, di **Permitir**
(en Windows marca **Redes privadas**). Sin eso el celular no la encuentra.

## Cómo probar con el celular

1. El celular debe estar en el **mismo WiFi** que la computadora.
2. Apunta la cámara del celular al QR que aparece en la pantalla.
3. Sale un aviso de "conexión no privada" la primera vez: toca *Configuración avanzada → Continuar*
   (iPhone: *Mostrar detalles → visitar este sitio web*). Es normal: el certificado lo hizo
   esta misma computadora, no una empresa de internet.
4. Toca **Empezar a escanear**, permite la cámara y pasa productos por el recuadro dorado.

Cada escaneo aparece en la computadora con el tiempo que tardó. La meta es **menos de 250 ms**.

### Quitar el aviso para siempre (opcional)

En la pantalla toca **Quitar el aviso**, escanea ese QR con el celular y sigue los pasos.
Se instala el "sello de la tienda" una sola vez y el aviso ya no vuelve a salir.

## Cómo funciona (resumen)

- `app/certificados.py`: crea un sello propio (10 años) y con él firma el certificado del
  servidor para la IP de la compu. Si cambia la IP, se rehace solo; el sello no cambia.
- `app/codigos.py`: revisa el dígito verificador (descarta lecturas equivocadas) y guarda
  los UPC-A de 12 dígitos como EAN-13 para que el mismo producto siempre coincida.
- `app/escaneos.py`: cada escaneo trae un id único; si el celular reintenta por falla de
  red, no se cuenta dos veces.
- `app/static/celular.js`: usa el lector del propio celular si existe (Android) y si no,
  ZXing (iPhone). Un código se acepta solo si sale igual en dos lecturas seguidas
  (el dígito verificador solo no basta). El mismo código a la vista no se repite
  hasta que se retira 1.5 s.
- El celular saluda a la compu cada 2 s para que su WiFi no se duerma y la conexión
  segura siga abierta; así cada escaneo no tiene que reconectarse.
- La latencia se mide sincronizando el reloj del celular con el de la compu.
- La pantalla y sus datos solo se ven desde la propia computadora; el celular necesita la
  llave que viene en el QR (`datos/llave.txt`).
- Registro en `datos/escaner.log`.

## Resultados (21 nov 2026, Mac + WiFi de casa)

| Celular | Antes de la mejora | Después |
|---|---|---|
| iPhone | 208–240 ms | — |
| Huawei | 302–346 ms | 58–120 ms (normal 64 ms) |

## Pruebas

```
python -m pip install -r requirements-dev.txt
python -m pytest
node --test tests/*.test.js
```

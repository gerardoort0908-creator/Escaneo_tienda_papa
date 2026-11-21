# Punto de venta de la tienda

| Carpeta | Qué es |
|---|---|
| `tienda/` | Cimientos (Fase 1): base de datos, dinero, inventario, ventas, fiado, caja, reportes, respaldos |
| `app/` | Escáner del celular (Fase 0) |

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
node --test tests/logica.test.js
```

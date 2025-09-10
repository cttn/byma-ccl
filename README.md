# BYMAcclBot · Bot de Telegram para rendimientos en USD vía CCL

Bot público: **[@BYMAcclBot](https://t.me/bymacclBot)**  
> Calcula y grafica rendimientos **en USD (vía CCL)** de acciones argentinas (BYMA) entre dos fechas, y la curva de un ticker puntual.  
> Colorea Top/Bottom con gradientes (azules = subas, rojos = bajas) y permite **normalizar** curvas a **base 100**.

---

## Tabla de contenidos
- [¿Qué hace?](#qué-hace)
- [Probar ahora](#probar-ahora)
- [Comandos](#comandos)
- [Cómo funciona](#cómo-funciona)
- [Instalación y ejecución local](#instalación-y-ejecución-local)
- [Configuración](#configuración)
- [Estructura sugerida del repo](#estructura-sugerida-del-repo)
- [Personalización](#personalización)
- [Despliegue opcional](#despliegue-opcional)
- [Limitaciones](#limitaciones)
- [Solución de problemas](#solución-de-problemas)
- [Licencia](#licencia)

---

## ¿Qué hace?
- Convierte precios en ARS a USD mediante **CCL = Close(YPFD.BA) / Close(YPF)** (con `auto_adjust=True`).
- Mide **variaciones porcentuales** entre una fecha inicial y una final para un set amplio de **tickers BYMA**.
- Devuelve:
  - **Top/Bottom**: ranking de ganadores y perdedores (barras coloreadas por intensidad).
  - **/cclplot**: curva de un ticker en USD; opción de **normalizar a 100** en la fecha inicial.
- Guarda **estado por chat** (fechas y `normalize`) en almacenamiento local (`state.json`) cuando se auto-hostea.

---

## Probar ahora
- Abrí Telegram y escribí a: **[@BYMAcclBot](https://t.me/bymacclBot)**  
- Flujo mínimo:
  ```text
  /start
  /ini 2023-11-17
  /fin 2025-09-06
  /cclvars 15 20
  /cclplot BBAR
  /normalize
  /cclplot BBAR
  ```

> **Nota:** El bot público puede rate-limitar respuestas si hay mucha demanda o si Yahoo Finance limita requests.

---

## Comandos

- **/start**  
  Muestra ayuda y el estado actual (fechas y flag `normalize`).

- **/ini YYYY-MM-DD**  
  Define o actualiza la **fecha inicial** del rango de análisis.

- **/fin YYYY-MM-DD**  
  Define o actualiza la **fecha final** del rango de análisis.

- **/cclvars N M**  
  Grafica **Top N / Bottom M** de rendimientos en **USD (vía CCL)** para el rango guardado.  
  Ejemplo: `/cclvars 15 20`.

- **/cclplot TICKER1 [TICKER2 ...]**
  Grafica la serie en **USD (vía CCL)** de uno o varios tickers `TICKER.BA` para el rango guardado.
  Respeta el flag de normalización para todos.
  Ejemplo: `/cclplot BBAR GGAL`.

- **/normalize**  
  Alterna el flag `normalize` entre **True/False** (persistente por chat) y explica el efecto:  
  - **True** → curvas normalizadas a **100** en la fecha inicial.  
  - **False** → curvas en USD absolutas.  
  En **/cclvars** el cálculo siempre es %; el flag sólo ajusta el etiquetado para claridad.

---

## Cómo funciona

- **Datos**: `yfinance` (Yahoo Finance).  
- **Tipo de cambio CCL**: `CCL = YPFD.BA / YPF` (close; frecuencia diaria; `ffill`).  
- **Top/Bottom**: para cada ticker `ret% = (USD_end / USD_ini - 1) * 100`; se ordenan extremos.  
- **Colores**: `Blues` para subas | `Reds` para bajas, intensidad según magnitud.  
- **Persistencia** (self-host): `state.json` con `{chat_id: {start, end, normalize}}`.

---

## Instalación y ejecución local

Requisitos: **Python 3.9+**.

```bash
git clone <tu_repo>.git
cd <tu_repo>
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="123456789:XXXXXXXXXXXX"
python bot_ccl.py
```

`requirements.txt` recomendado:
```text
python-telegram-bot==20.6
yfinance
pandas
matplotlib
numpy
```

---

## Configuración

- **Token**: variable de entorno `TELEGRAM_BOT_TOKEN` (otorgado por BotFather).  
- **Persistencia**: archivo `state.json` en la raíz (se crea automáticamente).  
- **Logs**: nivel `INFO` por defecto.

> **Seguridad**: no publiques tu token en repos/commits. Usá variables de entorno, `.env` o secrets del proveedor.

---

## Estructura sugerida del repo

```
.
├── bot_ccl.py            # bot principal
├── color_dif.py          # utilidades/experimentos de coloreo (opcional)
├── README.md
├── requirements.txt
└── .gitignore
```

`.gitignore` mínimo:
```
.venv/
__pycache__/
state.json
*.png
```

---

## Personalización

- **Lista de tickers**: editar la constante `TICKERS` en `bot_ccl.py`.  
  Usar símbolos **Yahoo .BA** (p. ej., `GGAL.BA`, `TGSU2.BA`).  
  Series D/C de BYMA suelen mapear a ordinarias en Yahoo: `GGALD → GGAL.BA`, `LOMAD → LOMA.BA`, etc.
- **CCL proxy**: por defecto `YPFD.BA / YPF`. Podés alternar a otra proxy (p. ej., `GGAL.BA/GGAL`).
- **Colores**: cambiar `cmap_pos="Blues"` y `cmap_neg="Reds"` en `plot_top_bottom(...)`.

---

## Despliegue opcional

### systemd (Linux)

`/etc/systemd/system/bymacclbot.service`:
```ini
[Unit]
Description=BYMAcclBot (Telegram)
After=network-online.target

[Service]
WorkingDirectory=/opt/bymacclbot
Environment=TELEGRAM_BOT_TOKEN=123456789:XXXXXXXXX
ExecStart=/opt/bymacclbot/.venv/bin/python /opt/bymacclbot/bot_ccl.py
Restart=on-failure
User=bymaccl
Group=bymaccl

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bymacclbot
sudo systemctl status bymacclbot
```

### Docker

`Dockerfile` mínimo:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot_ccl.py color_dif.py ./
ENV TELEGRAM_BOT_TOKEN=""
VOLUME ["/app/state.json"]
CMD ["python", "bot_ccl.py"]
```

Build & run:
```bash
docker build -t bymacclbot .
docker run --rm -e TELEGRAM_BOT_TOKEN="123:XYZ"   -v $(pwd)/state.json:/app/state.json bymacclbot
```

---

## Limitaciones

- **Yahoo Finance** no es un feed institucional: puede tener huecos, splits mal cargados, feriados desalineados.
- **Proxy CCL** con YPF es una **aproximación**; puede diferir de mediciones alternativas (bonos AL/GD, MEP/CCL oficiales, etc.).
- Si un papel **listó luego** de la fecha inicial, su serie puede quedar vacía.
- Descargar **muchos tickers** puede ser lento y/o golpear límites de rate de Yahoo.

---

## Solución de problemas

- *“Definí TELEGRAM_BOT_TOKEN…”*: faltó exportar la variable o está vacía.
- *“No se pudieron descargar precios.”*: caída de red, símbolos inválidos o rate limit. Probá con menos tickers o otro rango.
- Gráfico vacío en `/cclplot`: el ticker no tiene datos en el rango.
- Valores extraños: revisar splits; el bot usa `auto_adjust=True`, pero hay historiales defectuosos.

---

## Licencia

**MIT** — Usalo, modificalo y compartilo. Si te sirvió, una ⭐ al repo y un feedback en Telegram siempre suman.

---

**Contacto**  
Consultas, sugerencias o issues: abrí un *Issue* en el repo o escribí al bot **[@BYMAcclBot](https://t.me/bymacclBot)**.

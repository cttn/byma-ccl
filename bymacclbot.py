#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, logging, io
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
import requests

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colormaps
from matplotlib.colors import Normalize

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------------- CONFIG ----------------------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "REEMPLAZA_CON_TU_TOKEN")
STATE_FILE = Path("state.json")  # persistencia por chat_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ccl-bot")

# ------------------ UTIL / PERSISTENCIA -------------
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def get_chat_state(chat_id: int) -> dict:
    st = load_state().get(str(chat_id), {})
    # defaults
    if "normalize" not in st:
        st["normalize"] = False
    return st

def set_chat_state(chat_id: int, **kwargs):
    state = load_state()
    st = state.get(str(chat_id), {})
    st.update(kwargs)
    state[str(chat_id)] = st
    save_state(state)

def set_date(chat_id: int, key: str, value: str):
    set_chat_state(chat_id, **{key: value})

def get_dates(chat_id: int):
    st = get_chat_state(chat_id)
    return st.get("start"), st.get("end")

def get_normalize(chat_id: int) -> bool:
    return bool(get_chat_state(chat_id).get("normalize", False))

def toggle_normalize(chat_id: int) -> bool:
    current = get_normalize(chat_id)
    set_chat_state(chat_id, normalize=not current)
    return not current

def parse_date(s: str) -> str:
    return datetime.strptime(s, "%Y-%m-%d").date().isoformat()

def norm_ticker_ba(t: str) -> str:
    t = t.strip().upper()
    if not t.endswith(".BA"):
        t += ".BA"
    return t

def prettify_symbol(s: str) -> str:
    return s.replace(".BA", "")

# ------------------ NÚCLEO FINANCIERO ----------------
TICKERS = [norm_ticker_ba(x) for x in [
    'ALUA','BMA','BYMA','CEPU','COME','CRES','CVH','EDN','GGAL','MIRG',
    'PAMP','SUPV','TECO2','TGNO4','TGSU2','TRAN','TXAR','VALO','YPFD',
    'DOME','AGRO','AUSO','BBAR','BHIP','BPAT','CADO','CAPX','CARC',
    'CELU','CGPA2','CTIO','DGCU2','DYCA','FERR','FIPL','BOLT','A3',
    'GARO','GBAN','GCLA','GRIM','HARG','HAVA','INTR','INVJ','IRSA',
    'LEDE','LOMA','LONG','METR','MOLA','MOLI','MORI','OEST','PATA',
    'POLL','RICH','RIGO','ROSE','SAMI','SEMI'
]]

def download_ccl(start: str, end: str) -> pd.Series:
    """CCL = YPFD.BA / YPF (Close)."""
    df_ars = yf.download(["YPFD.BA"], start=start, end=end, auto_adjust=True, progress=False)
    df_us  = yf.download(["YPF"],     start=start, end=end, auto_adjust=True, progress=False)
    # Normalizar índices para evitar problemas de zona horaria
    for df in (df_ars, df_us):
        if isinstance(df.index, pd.DatetimeIndex):
            df.index = (df.index.tz_convert('UTC').tz_localize(None)
                        if df.index.tz is not None else df.index.tz_localize(None))
    ypf_ars = df_ars["Close"]["YPFD.BA"] if isinstance(df_ars["Close"], pd.DataFrame) else df_ars["Close"]
    ypf_usd = df_us["Close"]["YPF"]     if isinstance(df_us["Close"],  pd.DataFrame) else df_us["Close"]
    ccl = (ypf_ars / ypf_usd).to_frame("CCL").asfreq("D").ffill()["CCL"]
    if isinstance(ccl.index, pd.DatetimeIndex):
        ccl.index = (ccl.index.tz_convert('UTC').tz_localize(None)
                     if ccl.index.tz is not None else ccl.index.tz_localize(None))
    return ccl

def get_var(start: str, end: str) -> tuple[pd.Series, str]:
    """Retornos en USD (vía CCL) entre start y end, ordenados ascendente (%)."""
    data = {}
    failed = []

    for t in TICKERS:
        try:
            df = yf.download([t], start=start, end=end, auto_adjust=True, progress=False)
        except (TimeoutError, requests.exceptions.RequestException, Exception) as ex:
            log.warning(f"Fallo descargando {t}: {ex}")
            failed.append(t)
            continue

        if "Close" not in df:
            failed.append(t)
            continue

        ser = df["Close"][t] if isinstance(df["Close"], pd.DataFrame) else df["Close"]
        if isinstance(ser.index, pd.DatetimeIndex):
            ser.index = (ser.index.tz_convert('UTC').tz_localize(None)
                         if ser.index.tz is not None else ser.index.tz_localize(None))
        if ser.dropna().empty:
            failed.append(t)
            continue
        data[t] = ser

    if failed:
        retry_fail = []
        for t in failed:
            try:
                df = yf.download([t], start=start, end=end, auto_adjust=True, progress=False, timeout=30)
            except (TimeoutError, requests.exceptions.RequestException, Exception) as ex:
                log.warning(f"Reintento fallido para {t}: {ex}")
                retry_fail.append(t)
                continue

            if "Close" not in df:
                retry_fail.append(t)
                continue

            ser = df["Close"][t] if isinstance(df["Close"], pd.DataFrame) else df["Close"]
            if isinstance(ser.index, pd.DatetimeIndex):
                ser.index = (ser.index.tz_convert('UTC').tz_localize(None)
                             if ser.index.tz is not None else ser.index.tz_localize(None))
            if ser.dropna().empty:
                retry_fail.append(t)
                continue
            data[t] = ser
        failed = retry_fail

    if not data:
        raise RuntimeError("No se pudieron descargar precios.")

    close = pd.DataFrame(data)
    if isinstance(close.index, pd.DatetimeIndex):
        close.index = (close.index.tz_convert('UTC').tz_localize(None)
                       if close.index.tz is not None else close.index.tz_localize(None))

    ccl = download_ccl(start, end).to_frame().ffill()
    if isinstance(ccl.index, pd.DatetimeIndex):
        ccl.index = (ccl.index.tz_convert('UTC').tz_localize(None)
                     if ccl.index.tz is not None else ccl.index.tz_localize(None))
    close_usd = close.div(ccl["CCL"], axis=0)

    var = (close_usd.iloc[-1] / close_usd.iloc[0] - 1.0) * 100.0
    msg = ""
    if failed:
        msg = "Tickers omitidos por error de descarga: " + ", ".join(prettify_symbol(t) for t in failed)
    return var.dropna().sort_values(), msg

def plot_top_bottom(real_returns: pd.Series, top_n: int, bottom_n: int,
                    start_label: str, end_label: str, normalize_flag: bool,
                    cmap_pos: str = "Blues", cmap_neg: str = "Reds") -> io.BytesIO:
    """Colorea con gradiente. Si normalize_flag=True, aclara 'Base 100=ini' en títulos."""
    rr = real_returns.dropna()
    if rr.empty:
        raise RuntimeError("No hay datos para el rango seleccionado.")
    best = rr.nlargest(top_n)
    worst = rr.nsmallest(bottom_n)

    norm_pos = Normalize(vmin=float(best.min()), vmax=float(best.max()))
    colors_pos = colormaps.get_cmap(cmap_pos)(norm_pos(best.values))

    norm_neg = Normalize(vmin=float(np.abs(worst).min()), vmax=float(np.abs(worst).max()))
    colors_neg = colormaps.get_cmap(cmap_neg)(norm_neg(np.abs(worst.values)))

    fig = plt.figure(figsize=(11.5, 8.5), dpi=150, constrained_layout=True)
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.32)

    tag = " (Base 100=ini, USD vía CCL)" if normalize_flag else " (USD vía CCL)"

    ax1 = fig.add_subplot(gs[0, 0])
    x1 = [prettify_symbol(t) for t in best.index]
    ax1.bar(x1, best.values, color=colors_pos, edgecolor="none")
    ax1.set_title("Best Performing Tickers" + tag)
    ax1.set_ylabel("Return (%)")
    ax1.set_xticks(range(len(x1)))
    ax1.set_xticklabels(x1, rotation=45, ha="right")

    ax2 = fig.add_subplot(gs[1, 0])
    x2 = [prettify_symbol(t) for t in worst.index]
    ax2.bar(x2, worst.values, color=colors_neg, edgecolor="none")
    ax2.set_title("Worst Performing Tickers" + tag)
    ax2.set_ylabel("Return (%)")
    ax2.set_xticks(range(len(x2)))
    ax2.set_xticklabels(x2, rotation=45, ha="right")

    if start_label or end_label:
        fig.suptitle(f"Período: {start_label} → {end_label}", fontsize=10)
    bio = io.BytesIO()
    fig.savefig(bio, format="png", bbox_inches="tight")
    plt.close(fig)
    bio.seek(0)
    return bio

def plot_ticker_usd(ticker_ba: str, start: str, end: str, normalize_flag: bool) -> io.BytesIO:
    """Línea de precio en USD (vía CCL). Normaliza a 100 en la fecha inicial si normalize_flag=True."""
    ticker_ba = norm_ticker_ba(ticker_ba)
    px = yf.download([ticker_ba], start=start, end=end, auto_adjust=True, progress=False)["Close"]
    ser = px[ticker_ba] if isinstance(px, pd.DataFrame) else px
    if isinstance(ser.index, pd.DatetimeIndex):
        ser.index = (ser.index.tz_convert('UTC').tz_localize(None)
                     if ser.index.tz is not None else ser.index.tz_localize(None))

    ccl = download_ccl(start, end)
    if isinstance(ccl.index, pd.DatetimeIndex):
        ccl.index = (ccl.index.tz_convert('UTC').tz_localize(None)
                     if ccl.index.tz is not None else ccl.index.tz_localize(None))
    usd = (ser / ccl).dropna()

    if usd.empty:
        raise RuntimeError("Sin datos para ese rango.")

    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)

    if normalize_flag:
        idx = usd / usd.iloc[0] * 100.0
        ax.plot(idx.index, idx.values)
        ax.set_ylabel("Índice (100=ini)")
        title_tag = " – Normalizado (100=ini)"
    else:
        ax.plot(usd.index, usd.values)
        ax.set_ylabel("USD")
        title_tag = " – USD"

    ax.set_title(f"{prettify_symbol(ticker_ba)}{title_tag} vía CCL")
    ax.set_xlabel("Fecha")
    ax.grid(True, alpha=0.25)

    bio = io.BytesIO()
    fig.savefig(bio, format="png", bbox_inches="tight")
    plt.close(fig)
    bio.seek(0)
    return bio

# ----------------------- HANDLERS --------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s, e = get_dates(update.effective_chat.id)
    norm = get_normalize(update.effective_chat.id)
    msg = "Comandos: /ini YYYY-MM-DD | /fin YYYY-MM-DD | /cclvars N M | /cclplot TICKER | /normalize\n"
    msg += f"Rango actual: inicio={s or '⟂'} | fin={e or '⟂'} | normalize={norm}"
    await update.message.reply_text(msg)

async def cmd_ini(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Formato: /ini YYYY-MM-DD")
        return
    try:
        d = parse_date(context.args[0])
        set_date(update.effective_chat.id, "start", d)
        await update.message.reply_text(f"Fecha inicial guardada: {d}")
    except Exception:
        await update.message.reply_text("Fecha inválida. Formato: YYYY-MM-DD")

async def cmd_fin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Formato: /fin YYYY-MM-DD")
        return
    try:
        d = parse_date(context.args[0])
        set_date(update.effective_chat.id, "end", d)
        await update.message.reply_text(f"Fecha final guardada: {d}")
    except Exception:
        await update.message.reply_text("Fecha inválida. Formato: YYYY-MM-DD")

async def cmd_normalize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_val = toggle_normalize(update.effective_chat.id)
    if new_val:
        txt = ("Normalización: ON\n"
               "Desde ahora TODOS los gráficos se devuelven normalizados con base **100** en la fecha inicial.\n"
               "- /cclplot: línea índice (100=ini).\n"
               "- /cclvars: rendimientos relativos; el gráfico aclara Base 100=ini.")
    else:
        txt = ("Normalización: OFF\n"
               "Desde ahora los gráficos NO se normalizan.\n"
               "- /cclplot: precio en USD (vía CCL) absoluto.\n"
               "- /cclvars: rendimientos relativos en % (sin base 100 en el título).")
    await update.message.reply_text(txt, disable_web_page_preview=True)

async def cmd_cclvars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Uso: /cclvars <top_n> <bottom_n> (ej: /cclvars 15 20)")
        return
    try:
        top_n = int(context.args[0])
        bot_n = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Los dos parámetros deben ser enteros.")
        return

    s, e = get_dates(update.effective_chat.id)
    if not s or not e:
        await update.message.reply_text("Definí primero el rango con /ini y /fin.")
        return

    normalize_flag = get_normalize(update.effective_chat.id)
    await update.message.reply_text(f"Calculando Top {top_n} / Bottom {bot_n} para {s} → {e} …")
    try:
        series, msg = get_var(s, e)
        if series.dropna().empty:
            await update.message.reply_text("Sin datos para ese rango.")
            if msg:
                await update.message.reply_text(msg)
            return
        img = plot_top_bottom(series, top_n, bot_n, s, e, normalize_flag)
        await update.message.reply_photo(img, caption=f"Top/Bottom {s} → {e}")
        if msg:
            await update.message.reply_text(msg)
    except RuntimeError as ex:
        await update.message.reply_text(str(ex))
    except Exception as ex:
        log.exception(ex)
        await update.message.reply_text(f"Error al generar gráfico: {ex}")

async def cmd_cclplot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Uso: /cclplot <TICKER> (ej: /cclplot BBAR)")
        return

    s, e = get_dates(update.effective_chat.id)
    if not s or not e:
        await update.message.reply_text("Definí primero el rango con /ini y /fin.")
        return

    ticker = context.args[0]
    normalize_flag = get_normalize(update.effective_chat.id)
    await update.message.reply_text(f"Graficando {ticker}.BA para {s} → {e} …")
    try:
        img = plot_ticker_usd(ticker, s, e, normalize_flag)
        await update.message.reply_photo(img, caption=f"{ticker.upper()}.BA – {s} → {e}")
    except Exception as ex:
        log.exception(ex)
        await update.message.reply_text(f"Error al graficar {ticker}: {ex}")

# ------------------------- MAIN ---------------------
def main():
    if not TOKEN or TOKEN.startswith("REEMPLAZA_"):
        raise SystemExit("Definí TELEGRAM_BOT_TOKEN en el entorno o en TOKEN.")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("ini",       cmd_ini))
    app.add_handler(CommandHandler("fin",       cmd_fin))
    app.add_handler(CommandHandler("normalize", cmd_normalize))
    app.add_handler(CommandHandler("cclvars",   cmd_cclvars))
    app.add_handler(CommandHandler("cclplot",   cmd_cclplot))

    log.info("Bot listo.")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()


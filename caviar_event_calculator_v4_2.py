
# Caviar Event Calculator — v4.2 (compatibility fix)
# - Fixes pandas Styler compatibility: use hide_index() if available, else hide(axis='index'), else no-hide fallback.
# - Keeps v4.1 features: rounded-up "Total cost ($)" in Top Mixes, bold Optimal mix row, label & help text updates.

import math
import urllib.parse
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
from io import BytesIO

# PDF generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# ---------------- Brand Config ----------------
APP_TITLE = "Caviar Event Calculator"
BRAND_NAME = "La Pearle' Caviar"
PALETTE = {
    "gold": "#C8A465",
    "navy": "#0E1A3A",
    "ink": "#0B0F1C",
    "pearl": "#F6F2EA",
    "pearl_blush": "#E8D8CF"
}

LOCAL_LOGO_PATHS = ["assets/la-pearle-logo.png", "la-pearle-logo.png", "assets/logo.png"]
FOUND_LOCAL_LOGO = None
for p in LOCAL_LOGO_PATHS:
    if Path(p).exists():
        FOUND_LOCAL_LOGO = p
        break

st.set_page_config(page_title=APP_TITLE, page_icon="🥂", layout="centered")

# ---------------- Sidebar: Brand + Strategy ----------------
st.sidebar.header("Brand Settings")
st.sidebar.caption("Tip: Put your logo at ./assets/la-pearle-logo.png in the repo to load automatically.")
logo_url = st.sidebar.text_input("Logo URL (used if a local file isn't found)", "")
brand_name = st.sidebar.text_input("Brand Name", BRAND_NAME)

primary_hex = st.sidebar.color_picker("Primary (Gold)", PALETTE["gold"])
accent_hex  = st.sidebar.color_picker("Accent (Navy)",  PALETTE["navy"])
bg_hex      = st.sidebar.color_picker("Background",     "#FFFFFF")
panel_hex   = st.sidebar.color_picker("Panel Background", PALETTE["pearl"])

st.sidebar.markdown("---")
st.sidebar.subheader("Mix Strategy")

objective = st.sidebar.selectbox(
    "Objective Mode",
    ["Fewest tins (recommended)", "Balanced mix (cost + per-tin penalty)", "Cheapest only"],
    help="Choose how the optimizer ranks mixes."
)

service_penalty = st.sidebar.number_input(
    "Per‑tin service penalty ($) — used only in Balanced mix",
    min_value=0.0, value=8.0, step=1.0
)
st.sidebar.caption(
    "❓ **What is the per‑tin service penalty?** "
    "It's a small artificial cost added **per tin** *only* in **Balanced mix** mode to reflect real‑world setup/serving effort. "
    "A higher penalty gently pushes the optimizer toward **fewer/larger tins**. "
    "It is **ignored** in 'Fewest tins' and 'Cheapest only' modes."
)

cap_125_share_on = st.sidebar.checkbox("Limit 125 g share of total grams", value=True)
cap_125_share_pct = st.sidebar.slider("Max % of grams from 125 g", 20, 100, 60)

st.sidebar.markdown("---")
st.sidebar.subheader("Advanced Caps (Optional)")
cap_250 = st.sidebar.number_input("Max 250 g tins", min_value=0, value=0, step=1, help="0 = no cap")
cap_8   = st.sidebar.number_input("Max 8 oz tins",  min_value=0, value=0, step=1, help="0 = no cap")
cap_125 = st.sidebar.number_input("Max 125 g tins", min_value=0, value=0, step=1, help="0 = no cap")

top_k = st.sidebar.number_input("Only Show Top ___ Mixes", min_value=1, value=10, step=1)

# ---------------- CSS ----------------
st.markdown(f"""
<style>
:root {{
  --primary: {primary_hex};
  --accent:  {accent_hex};
  --bg:      {bg_hex};
  --panel:   {panel_hex};
  --ink:     {PALETTE['ink']};
}}
[data-testid="stAppViewContainer"] > .main {{ background: var(--bg); }}
.lp-banner {{
  display:flex; align-items:center; gap:16px;
  background: linear-gradient(90deg, var(--panel), #ffffff 70%);
  padding: 14px 16px; border-radius: 16px; border: 1px solid #eee;
  box-shadow: 0 1px 6px rgba(0,0,0,0.06);
}}
.lp-brand {{ font-size: 20px; font-weight: 700; color: var(--accent); }}
.lp-chip  {{ display:inline-block; padding: 2px 8px; border-radius: 999px; background: var(--primary); color: white; font-size: 12px; }}
.stButton>button {{ background: var(--primary); color:white; border:none; }}
</style>
""", unsafe_allow_html=True)

# ---------------- Header ----------------
col_logo, col_text = st.columns([1, 3])
with col_logo:
    if FOUND_LOCAL_LOGO:
        st.image(FOUND_LOCAL_LOGO, use_container_width=True)
    elif logo_url.strip():
        st.image(logo_url, use_container_width=True)
    else:
        st.markdown("<div class='lp-chip'>Add your logo via sidebar</div>", unsafe_allow_html=True)
with col_text:
    st.markdown(f"""
    <div class="lp-banner">
      <div class="lp-brand">{brand_name}</div>
      <div class="lp-chip">{APP_TITLE}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("Compute the lowest‑tin‑count **mix** that meets your required grams for **one‑hour**, **two‑hour**, and **three‑hour** events (while balancing cost and overage).")

# ---------------- Inputs ----------------
st.markdown("### Event Inputs")
col1, col2, col3 = st.columns(3)
with col1:
    guests = st.number_input("Guests", min_value=1, value=90, step=1)
with col2:
    grams_per_tasting = st.number_input("Grams per Tasting", min_value=1.0, value=3.0, step=0.5)
with col3:
    tastings_per_guest_1h = st.number_input("Tastings per Guest (1 hour)", min_value=0.5, value=2.0, step=0.25)

c4, c5 = st.columns(2)
with c4:
    tastings_per_guest_2h = st.number_input("Tastings per Guest (2 hours)", min_value=0.5, value=2.75, step=0.25)
with c5:
    tastings_per_guest_3h = st.number_input("Tastings per Guest (3 hours)", min_value=0.5, value=3.5, step=0.25)

st.markdown("### Tin Sizes & Prices")
c1, c2, c3, c4 = st.columns(4)
with c1:
    grams_250 = st.number_input("250 g - grams", min_value=1, value=250, step=1)
    price_250 = st.number_input("250 g - price ($)", min_value=0.0, value=345.0, step=0.01, format="%.2f")
with c2:
    grams_8 = st.number_input("8 oz - grams", min_value=1, value=227, step=1)
    price_8 = st.number_input("8 oz - price ($)", min_value=0.0, value=312.0, step=0.01, format="%.2f")
with c3:
    grams_7 = st.number_input("7 oz - grams", min_value=1, value=198, step=1)
    price_7 = st.number_input("7 oz - price ($)", min_value=0.0, value=273.0, step=0.01, format="%.2f")
with c4:
    grams_125 = st.number_input("125 g - grams", min_value=1, value=125, step=1)
    price_125 = st.number_input("125 g - price ($)", min_value=0.0, value=127.57, step=0.01, format="%.2f")

# ---------------- Core logic ----------------
def grams_required(guests, tastings, g_per_taste):
    return math.ceil(guests * tastings * g_per_taste)

def optimize_and_rank(req_g,
                      grams_250, price_250,
                      grams_8, price_8,
                      grams_7, price_7,
                      grams_125, price_125,
                      objective="Fewest tins (recommended)",
                      service_penalty=8.0,
                      cap_125_share_on=True, cap_125_share_pct=60,
                      cap_250=0, cap_8=0, cap_125=0,
                      top_k=10):
    # bounds
    max_250 = (cap_250 if cap_250 > 0 else math.ceil(req_g / grams_250) + 8)
    max_8   = (cap_8   if cap_8   > 0 else math.ceil(req_g / grams_8) + 8)
    max_125 = (cap_125 if cap_125 > 0 else math.ceil(req_g / grams_125) + 8)

    combos = []
    for x250 in range(max_250 + 1):
        g250 = x250 * grams_250
        for x8 in range(max_8 + 1):
            g8 = x8 * grams_8
            for x125 in range(max_125 + 1):
                g125 = x125 * grams_125
                grams_so_far = g250 + g8 + g125
                if grams_so_far >= req_g:
                    x7 = 0
                    purchased = grams_so_far
                else:
                    need = req_g - grams_so_far
                    x7 = math.ceil(need / grams_7)
                    purchased = grams_so_far + x7 * grams_7

                # share cap
                if cap_125_share_on and purchased > 0:
                    if (g125 / purchased) * 100.0 > cap_125_share_pct:
                        continue

                total_tins = x250 + x8 + x7 + x125
                cost = x250*price_250 + x8*price_8 + x7*price_7 + x125*price_125
                over = purchased - req_g

                # Score by objective
                if objective == "Cheapest only":
                    score = (cost, over, total_tins)
                elif objective == "Balanced mix (cost + per-tin penalty)":
                    score = (cost + service_penalty * total_tins, over, total_tins)
                else:  # Fewest tins (recommended)
                    score = (total_tins, cost, over)

                combos.append((score, total_tins, cost, over, x250, x8, x7, x125, purchased))

    if not combos:
        return {"error": "No feasible mix under current caps/limits."}, []

    # best by objective
    combos.sort(key=lambda t: t[0])
    best = combos[0]
    res_best = {
        "required_g": req_g,
        "x250": best[4], "x8": best[5], "x7": best[6], "x125": best[7],
        "purchased_g": best[8],
        "overage_g": best[3],
        "total_cost": best[2],
        "total_tins": best[1],
    }

    # alternatives: top N by FEWEST TINS, cost, overage
    alt_sorted = sorted(combos, key=lambda t: (t[1], t[2], t[3]))
    alts = []
    seen = set()
    for t in alt_sorted:
        mix_tuple = (t[4], t[5], t[6], t[7])  # unique by tin counts
        if mix_tuple in seen:
            continue
        seen.add(mix_tuple)
        alts.append({
            "250 g": t[4], "8 oz": t[5], "7 oz": t[6], "125 g": t[7],
            "Total grams": t[8], "Overage (g)": t[3],
            "Total tins": t[1], "Total cost ($)": int(math.ceil(float(t[2])))
        })
        if len(alts) >= top_k:
            break

    return res_best, alts

def render_block(title, best):
    st.markdown(f"#### {title}")
    if "error" in best:
        st.error(best["error"])
        return
    df = pd.DataFrame({
        "Metric": [
            "Required grams",
            "Optimal mix",
            "Total grams purchased",
            "Overage (g)",
            "Total tins",
            "Total cost",
            "Cost per guest"
        ],
        "Value": [
            f"{best['required_g']:,}",
            f"{best['x250']} × 250 g, {best['x8']} × 8 oz, {best['x7']} × 7 oz, {best['x125']} × 125 g",
            f"{best['purchased_g']:,}",
            f"{best['overage_g']:,}",
            f"{best['total_tins']}",
            f"${best['total_cost']:,.2f}",
            f"${best['total_cost']/max(1,guests):,.2f}",
        ]
    })
    # Bold the "Optimal mix" row via Styler with cross-version hide index
    def _bold_optimal(row):
        return ['font-weight: bold' if row['Metric'] == 'Optimal mix' else '' for _ in row]
    styler = df.style.apply(_bold_optimal, axis=1)
    # hide index for older/newer pandas
    try:
        styler = styler.hide_index()
    except Exception:
        try:
            styler = styler.hide(axis='index')
        except Exception:
            pass
    st.dataframe(styler, use_container_width=True)

def render_alternatives(title, alts, label="Top mixes (fewest tins first)"):
    if alts:
        st.markdown(f"**{label}**")
        df2 = pd.DataFrame(alts)
        st.dataframe(df2, use_container_width=True, hide_index=True)

# Required grams
req_1h = grams_required(guests, tastings_per_guest_1h, grams_per_tasting)
req_2h = grams_required(guests, tastings_per_guest_2h, grams_per_tasting)
req_3h = grams_required(guests, tastings_per_guest_3h, grams_per_tasting)

# Run optimizer
best_1h, alt_1h = optimize_and_rank(
    req_1h, grams_250, price_250, grams_8, price_8, grams_7, price_7, grams_125, price_125,
    objective=objective, service_penalty=service_penalty,
    cap_125_share_on=cap_125_share_on, cap_125_share_pct=cap_125_share_pct,
    cap_250=cap_250, cap_8=cap_8, cap_125=cap_125, top_k=top_k
)
best_2h, alt_2h = optimize_and_rank(
    req_2h, grams_250, price_250, grams_8, price_8, grams_7, price_7, grams_125, price_125,
    objective=objective, service_penalty=service_penalty,
    cap_125_share_on=cap_125_share_on, cap_125_share_pct=cap_125_share_pct,
    cap_250=cap_250, cap_8=cap_8, cap_125=cap_125, top_k=top_k
)
best_3h, alt_3h = optimize_and_rank(
    req_3h, grams_250, price_250, grams_8, price_8, grams_7, price_7, grams_125, price_125,
    objective=objective, service_penalty=service_penalty,
    cap_125_share_on=cap_125_share_on, cap_125_share_pct=cap_125_share_pct,
    cap_250=cap_250, cap_8=cap_8, cap_125=cap_125, top_k=top_k
)

# ---------------- Results ----------------
st.markdown("### Results")
render_block("One-Hour Event", best_1h)
render_alternatives("One-Hour Event", alt_1h)

render_block("Two-Hour Event", best_2h)
render_alternatives("Two-Hour Event", alt_2h)

render_block("Three-Hour Event", best_3h)
render_alternatives("Three-Hour Event", alt_3h)

# ---------------- PDF Summary Sheet ----------------
st.markdown("### Summary Sheet (PDF)")

def _hex_to_rgb01(hex_str):
    hex_str = hex_str.strip().lstrip("#")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return r, g, b

def generate_pdf(brand_name, logo_path_or_url, bg_hex, ink_hex, gold_hex,
                 guests, gpt, t1, t2, t3,
                 best1, best2, best3):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    ink  = colors.Color(*_hex_to_rgb01(ink_hex))
    gold = colors.Color(*_hex_to_rgb01(gold_hex))
    bg   = colors.Color(*_hex_to_rgb01(bg_hex))
    c.setFillColor(bg); c.rect(0, 0, width, height, stroke=0, fill=1)
    y = height - 72
    if logo_path_or_url:
        try:
            img = ImageReader(logo_path_or_url)
            logo_w = 2.5 * inch
            c.drawImage(img, (width - logo_w)/2, y - 1.0*inch, width=logo_w, preserveAspectRatio=True, mask='auto')
            y -= 1.1*inch
        except Exception:
            pass
    today = datetime.now().strftime("%B %d, %Y")
    c.setFont("Helvetica-Bold", 18); c.setFillColor(gold)
    c.drawCentredString(width/2, y, "Caviar Event Summary"); y -= 24
    c.setFont("Helvetica", 10); c.setFillColor(ink)
    c.drawCentredString(width/2, y, f"{today}"); y -= 18
    c.setFont("Helvetica", 9)
    c.drawCentredString(width/2, y, f"Prepared by {brand_name}"); y -= 18
    c.setStrokeColor(gold); c.setLineWidth(1.2); c.line(72, y, width-72, y); y -= 18

    c.setFont("Helvetica-Bold", 11); c.setFillColor(ink)
    c.drawString(72, y, "Event Inputs"); y -= 14
    c.setFont("Helvetica", 10)
    c.drawString(72, y, f"Guests: {guests}"); y -= 12
    c.drawString(72, y, f"Grams per tasting: {gpt}"); y -= 12
    c.drawString(72, y, f"Tastings per guest (1h/2h/3h): {t1} / {t2} / {t3}"); y -= 18

    def block(title, best):
        nonlocal y
        c.setFont("Helvetica-Bold", 11); c.setFillColor(ink)
        c.drawString(72, y, title); y -= 12
        rows = [
            ("Required grams", f"{best['required_g']:,}"),
            ("Optimal mix", f"{best['x250']}×250 g, {best['x8']}×8 oz, {best['x7']}×7 oz, {best['x125']}×125 g"),
            ("Total grams purchased", f"{best['purchased_g']:,}"),
            ("Overage (g)", f"{best['overage_g']:,}"),
            ("Total tins", f"{best['total_tins']}"),
            ("Total cost", f"${best['total_cost']:,.2f}"),
            ("Cost per guest", f"${best['total_cost']/max(guests,1):,.2f}")
        ]
        c.setFillColor(bg); c.setStrokeColor(colors.Color(0,0,0,0.05))
        c.roundRect(72, y-6-7*14, width-144, 7*14+8, 6, stroke=1, fill=1)
        c.setFillColor(ink); c.setFont("Helvetica", 10)
        yy = y - 6
        for label, val in rows:
            c.drawString(84, yy, f"{label}:")
            c.drawRightString(width-84, yy, val)
            yy -= 14
        y = yy - 8

    block("One-Hour Event", best1)
    block("Two-Hour Event", best2)
    block("Three-Hour Event", best3)

    c.setStrokeColor(gold); c.line(72, 72, width-72, 72)
    c.setFillColor(ink); c.setFont("Helvetica", 8)
    c.drawCentredString(width/2, 58, "© " + str(datetime.now().year) + f" {brand_name}. All rights reserved.")
    c.showPage(); c.save()
    pdf = buf.getvalue(); buf.close(); return pdf

if not REPORTLAB_AVAILABLE:
    st.info("To enable PDF export, add **reportlab** to your requirements.txt and redeploy.")
else:
    pdf_logo = FOUND_LOCAL_LOGO if FOUND_LOCAL_LOGO else (logo_url if logo_url.strip() else None)
    if st.button("📄 Generate Summary Sheet"):
        pdf_bytes = generate_pdf(
            brand_name=brand_name, logo_path_or_url=pdf_logo,
            bg_hex=panel_hex, ink_hex=PALETTE["ink"], gold_hex=primary_hex,
            guests=guests, gpt=grams_per_tasting,
            t1=tastings_per_guest_1h, t2=tastings_per_guest_2h, t3=tastings_per_guest_3h,
            best1=best_1h, best2=best_2h, best3=best_3h
        )
        st.session_state["summary_pdf"] = pdf_bytes
    if "summary_pdf" in st.session_state:
        fname = f"Caviar_Event_Summary_{datetime.now().strftime('%Y-%m-%d')}.pdf"
        st.download_button("⬇️ Download PDF", data=st.session_state["summary_pdf"], file_name=fname, mime="application/pdf")

# ---------------- Actions ----------------
st.markdown("### Actions")
st.components.v1.html("""
<script>function doPrint(){ window.print(); }</script>
<button onclick="doPrint()" style="padding:8px 12px;border-radius:8px;border:1px solid #ccc;cursor:pointer;">🖨️ Print Results</button>
""", height=60)

def mailto_link(brand, guests, gpt, best1, best2, best3):
    subject = f"{brand} • Caviar Event Calculator Results"
    body = f"""Caviar Event Calculator Results

Guests: {guests}
Grams per tasting: {gpt}

[One-Hour]
Required grams: {best1['required_g']}
Optimal mix: {best1['x250']} x 250 g, {best1['x8']} x 8 oz, {best1['x7']} x 7 oz, {best1['x125']} x 125 g
Total grams purchased: {best1['purchased_g']}
Overage (g): {best1['overage_g']}
Total tins: {best1['total_tins']}
Total cost: ${best1['total_cost']:.2f}

[Two-Hour]
Required grams: {best2['required_g']}
Optimal mix: {best2['x250']} x 250 g, {best2['x8']} x 8 oz, {best2['x7']} x 7 oz, {best2['x125']} x 125 g
Total grams purchased: {best2['purchased_g']}
Overage (g): {best2['overage_g']}
Total tins: {best2['total_tins']}
Total cost: ${best2['total_cost']:.2f}

[Three-Hour]
Required grams: {best3['required_g']}
Optimal mix: {best3['x250']} x 250 g, {best3['x8']} x 8 oz, {best3['x7']} x 7 oz, {best3['x125']} x 125 g
Total grams purchased: {best3['purchased_g']}
Overage (g): {best3['overage_g']}
Total tins: {best3['total_tins']}
Total cost: ${best3['total_cost']:.2f}
"""
    return "mailto:?subject=" + urllib.parse.quote(subject) + "&body=" + urllib.parse.quote(body)

st.markdown(f"[📧 Email Results]({mailto_link(brand_name, guests, grams_per_tasting, best_1h, best_2h, best_3h)})")

st.caption("v4.2: Fixes Styler.hide_index compatibility; keeps bold Optimal mix and whole‑dollar Top Mixes.")

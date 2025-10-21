
import math
import urllib.parse
import streamlit as st
import pandas as pd
from pathlib import Path

# ---------------- Brand Config ----------------
BRAND_NAME = "La Pearle’ Caviar"
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

st.set_page_config(page_title=f"{BRAND_NAME} • Caviar Tin Mix Optimizer", page_icon="🥂", layout="centered")

st.sidebar.header("Brand Settings")
st.sidebar.caption("Tip: Put your logo at ./assets/la-pearle-logo.png in the repo to load automatically.")
logo_url = st.sidebar.text_input("Logo URL (used if a local file isn't found)", "")
brand_name = st.sidebar.text_input("Brand Name", BRAND_NAME)

primary_hex = st.sidebar.color_picker("Primary (Gold)", PALETTE["gold"])
accent_hex = st.sidebar.color_picker("Accent (Navy)", PALETTE["navy"])
bg_hex = st.sidebar.color_picker("Background", "#FFFFFF")
panel_hex = st.sidebar.color_picker("Panel Background", PALETTE["pearl"])

st.markdown(f"""
<style>
:root {{
  --primary: {primary_hex};
  --accent: {accent_hex};
  --bg: {bg_hex};
  --panel: {panel_hex};
  --ink: {PALETTE['ink']};
}}
[data-testid="stAppViewContainer"] > .main {{ background: var(--bg); }}
.lp-banner {{
  display:flex; align-items:center; gap:16px;
  background: linear-gradient(90deg, var(--panel), #ffffff 70%);
  padding: 14px 16px; border-radius: 16px; border: 1px solid #eee;
  box-shadow: 0 1px 6px rgba(0,0,0,0.06);
}}
.lp-brand {{ font-size: 20px; font-weight: 700; color: var(--accent); }}
.lp-chip {{
  display:inline-block; padding: 2px 8px; border-radius: 999px; background: var(--primary); color: white; font-size: 12px;
}}
.stButton>button {{ background: var(--primary); color:white; border:none; }}
</style>
""", unsafe_allow_html=True)

col_logo, col_text = st.columns([1, 3])
with col_logo:
    if FOUND_LOCAL_LOGO:
        st.image(FOUND_LOCAL_LOGO, use_column_width=True)
    elif logo_url.strip():
        st.image(logo_url, use_column_width=True)
    else:
        st.markdown("<div class='lp-chip'>Add your logo via sidebar</div>", unsafe_allow_html=True)
with col_text:
    st.markdown(f"""
    <div class="lp-banner">
      <div class="lp-brand">{brand_name}</div>
      <div class="lp-chip">Caviar Tin Mix Optimizer</div>
    </div>
    """, unsafe_allow_html=True)

st.write("Use this tool to compute the lowest-cost mix of tin sizes that meets your required grams for one-hour and two-hour events.")

st.markdown("### Event Inputs")
col1, col2, col3 = st.columns(3)
with col1:
    guests = st.number_input("Guests", min_value=1, value=90, step=1)
with col2:
    grams_per_tasting = st.number_input("Grams per Tasting", min_value=1.0, value=3.0, step=0.5)
with col3:
    tastings_per_guest_1h = st.number_input("Tastings per Guest (1 hour)", min_value=0.5, value=2.0, step=0.25)

tastings_per_guest_2h = st.number_input("Tastings per Guest (2 hours)", min_value=0.5, value=2.75, step=0.25)

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

def grams_required(guests, tastings, g_per_taste):
    return math.ceil(guests * tastings * g_per_taste)

def optimize_mix(req_g,
                 grams_250, price_250,
                 grams_8, price_8,
                 grams_7, price_7,
                 grams_125, price_125):
    max_250 = math.ceil(req_g / grams_250) + 6
    max_8   = math.ceil(req_g / grams_8) + 6
    max_125 = math.ceil(req_g / grams_125) + 6
    best = None  # (cost, overage, total_tins, x250, x8, x7, x125, purchased_g)
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
                cost = x250*price_250 + x8*price_8 + x7*price_7 + x125*price_125
                over = purchased - req_g
                total_tins = x250 + x8 + x7 + x125
                key = (cost, over, total_tins)
                if (best is None) or (key < best[:3]):
                    best = (cost, over, total_tins, x250, x8, x7, x125, purchased)
    return {
        "required_g": req_g,
        "x250": best[3], "x8": best[4], "x7": best[5], "x125": best[6],
        "purchased_g": best[7],
        "overage_g": best[1],
        "total_cost": best[0],
        "total_tins": best[2],
    }

req_1h = grams_required(guests, tastings_per_guest_1h, grams_per_tasting)
req_2h = grams_required(guests, tastings_per_guest_2h, grams_per_tasting)

res_1h = optimize_mix(req_1h, grams_250, price_250, grams_8, price_8, grams_7, price_7, grams_125, price_125)
res_2h = optimize_mix(req_2h, grams_250, price_250, grams_8, price_8, grams_7, price_7, grams_125, price_125)

def result_table(title, res):
    st.markdown(f"#### {title}")
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
            f"{res['required_g']:,}",
            f"{res['x250']} × 250 g, {res['x8']} × 8 oz, {res['x7']} × 7 oz, {res['x125']} × 125 g",
            f"{res['purchased_g']:,}",
            f"{res['overage_g']:,}",
            f"{res['total_tins']}",
            f"${res['total_cost']:,.2f}",
            f"${res['total_cost']/guests:,.2f}",
        ]
    })
    st.dataframe(df, use_container_width=True, hide_index=True)

result_table("One-Hour Event", res_1h)
result_table("Two-Hour Event", res_2h)

st.markdown("### Actions")
st.components.v1.html("""
<script>function doPrint(){ window.print(); }</script>
<button onclick="doPrint()" style="padding:8px 12px;border-radius:8px;border:1px solid #ccc;cursor:pointer;">🖨️ Print Results</button>
""", height=60)

def mailto_link(brand, guests, gpt, res1, res2):
    subject = f"{brand} • Caviar Mix Results"
    body = f"""Caviar Mix Results

Guests: {guests}
Grams per tasting: {gpt}

[One-Hour]
Required grams: {res1['required_g']}
Optimal mix: {res1['x250']} x 250 g, {res1['x8']} x 8 oz, {res1['x7']} x 7 oz, {res1['x125']} x 125 g
Total grams purchased: {res1['purchased_g']}
Overage (g): {res1['overage_g']}
Total tins: {res1['total_tins']}
Total cost: ${res1['total_cost']:.2f}

[Two-Hour]
Required grams: {res2['required_g']}
Optimal mix: {res2['x250']} x 250 g, {res2['x8']} x 8 oz, {res2['x7']} x 7 oz, {res2['x125']} x 125 g
Total grams purchased: {res2['purchased_g']}
Overage (g): {res2['overage_g']}
Total tins: {res2['total_tins']}
Total cost: ${res2['total_cost']:.2f}
"""
    return "mailto:?subject=" + urllib.parse.quote(subject) + "&body=" + urllib.parse.quote(body)

st.markdown(f"[📧 Email Results]({mailto_link(brand_name, guests, grams_per_tasting, res_1h, res_2h)})")

st.caption("Brand colors derived from your logo. Adjust them in the sidebar or in .streamlit/config.toml.")

from typing import Optional

import streamlit as st
import streamlit.components.v1 as components


def render_prev_close_move_calculator(
    previous_close: Optional[float],
    key_suffix: str = "",
    compact: bool = True,
):
    """Render a compact calculator from yesterday close and a target percent move."""
    st.caption("📈 昨收漲跌幅快算")

    suffix = f"-{key_suffix}" if key_suffix else ""

    input_width = "100px" if compact else "160px"
    padding = "6px 8px" if compact else "8px 10px"
    label_font = "13px" if compact else "14px"
    border_radius = "6px" if compact else "8px"
    min_width_result = "120px" if compact else "160px"
    gap = "8px" if compact else "12px"
    height = 132 if compact else 164
    top_margin = "-4px" if compact else "-2px"

    prev_close_js = "null" if previous_close is None else f"{float(previous_close):.6f}"
    prev_close_text = "-" if previous_close is None else f"{float(previous_close):.2f}"

    components.html(
        f"""
        <div style="font-family: ui-sans-serif, system-ui; line-height:1.4; margin-top:{top_margin};">
          <div style="display:flex; gap:{gap}; align-items:end; flex-wrap:nowrap;">
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:{label_font}; color:#6b7280; margin-bottom:2px;">昨日收盤價</label>
              <input id="prev-close{suffix}" type="text" value="{prev_close_text}" readonly
                     style="padding:{padding}; width:{input_width}; border:1px solid #d1d5db; border-radius:{border_radius}; outline:none; background:#f9fafb; color:#374151;">
            </div>

            <div style="display:flex; flex-direction:column;">
              <label style="font-size:{label_font}; color:#6b7280; margin-bottom:2px;">漲跌幅 %</label>
              <input id="pct-input{suffix}" type="text" inputmode="decimal" placeholder="例如 7 或 -7"
                     style="padding:{padding}; width:{input_width}; border:1px solid #d1d5db; border-radius:{border_radius}; outline:none;">
            </div>

            <div style="display:flex; flex-direction:column;">
              <label style="font-size:{label_font}; color:#6b7280; margin-bottom:2px;">計算後價格</label>
              <div id="pct-result{suffix}"
                   style="min-width:{min_width_result}; padding:{padding}; border:1px solid #f3f4f6; border-radius:{border_radius}; background:#f9fafb; font-weight:600; text-align:right;">
                -
              </div>
            </div>
          </div>

                <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:8px;">
                  <button type="button" class="pct-shortcut{suffix}" data-pct="6"
                    style="padding:4px 8px; border:1px solid #fecaca; border-radius:{border_radius}; background:#fef2f2; color:#b91c1c; cursor:pointer;">+6%</button>
                  <button type="button" class="pct-shortcut{suffix}" data-pct="7"
                    style="padding:4px 8px; border:1px solid #fecaca; border-radius:{border_radius}; background:#fef2f2; color:#b91c1c; cursor:pointer;">+7%</button>
                  <button type="button" class="pct-shortcut{suffix}" data-pct="8"
                    style="padding:4px 8px; border:1px solid #fecaca; border-radius:{border_radius}; background:#fef2f2; color:#b91c1c; cursor:pointer;">+8%</button>
                  <button type="button" class="pct-shortcut{suffix}" data-pct="9"
                    style="padding:4px 8px; border:1px solid #fecaca; border-radius:{border_radius}; background:#fef2f2; color:#b91c1c; cursor:pointer;">+9%</button>
                  <button type="button" class="pct-shortcut{suffix}" data-pct="-6"
                    style="padding:4px 8px; border:1px solid #bbf7d0; border-radius:{border_radius}; background:#f0fdf4; color:#15803d; cursor:pointer;">-6%</button>
                  <button type="button" class="pct-shortcut{suffix}" data-pct="-7"
                    style="padding:4px 8px; border:1px solid #bbf7d0; border-radius:{border_radius}; background:#f0fdf4; color:#15803d; cursor:pointer;">-7%</button>
                </div>

          <div id="pct-note{suffix}" style="margin-top:6px; font-size:12px; color:#6b7280;">
            以昨收為基準，輸入範圍 -10 ~ 10。
          </div>
        </div>

        <script>
        (function() {{
          const basePrice = {prev_close_js};
          const pctEl = document.getElementById("pct-input{suffix}");
          const resultEl = document.getElementById("pct-result{suffix}");
          const noteEl = document.getElementById("pct-note{suffix}");
          const shortcutEls = document.querySelectorAll(".pct-shortcut{suffix}");

          const toNum = (s) => {{
            if (!s) return NaN;
            return Number(String(s).replace(/,/g, "").trim());
          }};

          function resetResult() {{
            resultEl.textContent = "-";
            resultEl.style.color = "#111827";
          }}

          function compute() {{
            if (!isFinite(basePrice) || basePrice <= 0) {{
              resetResult();
              noteEl.textContent = "抓不到昨日收盤價，暫時無法計算。";
              noteEl.style.color = "#ef4444";
              return;
            }}

            const pct = toNum(pctEl.value);
            if (!isFinite(pct)) {{
              resetResult();
              noteEl.textContent = "以昨收為基準，輸入範圍 -10 ~ 10。";
              noteEl.style.color = "#6b7280";
              return;
            }}

            if (pct < -10 || pct > 10) {{
              resetResult();
              noteEl.textContent = "漲跌幅必須介於 -10 到 10。";
              noteEl.style.color = "#ef4444";
              pctEl.focus();
              return;
            }}

            const value = basePrice * (1 + pct / 100);
            resultEl.textContent = value.toFixed(2);
            resultEl.style.color = pct > 0 ? "#ef4444" : (pct < 0 ? "#16a34a" : "#111827");
            noteEl.textContent = "昨收 " + basePrice.toFixed(2) + " " + (pct >= 0 ? "上漲" : "下跌") + " " + Math.abs(pct).toFixed(2) + "% 後價格";
            noteEl.style.color = "#6b7280";
          }}

          pctEl.addEventListener("input", compute);
          pctEl.addEventListener("keydown", (e) => {{
            if (e.key === "Enter") {{
              e.preventDefault();
              compute();
            }}
          }});

          shortcutEls.forEach((button) => {{
            button.addEventListener("click", () => {{
              pctEl.value = button.dataset.pct || "";
              compute();
              pctEl.focus();
            }});
          }});

          compute();
        }})();
        </script>
        """,
        height=height,
    )
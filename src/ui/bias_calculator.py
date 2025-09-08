# src/ui/bias_calculator.py
import streamlit as st
import streamlit.components.v1 as components

def render_bias_calculator(key_suffix: str = "", compact: bool = False):
    st.caption("✏️ 乖離率快算 (A→B)")

    suffix = f"-{key_suffix}" if key_suffix else ""

    # 🔹依 compact 模式決定寬度 & 樣式
    input_width = "100px" if compact else "160px"
    padding = "6px 8px" if compact else "8px 10px"
    label_font = "13px" if compact else "14px"
    border_radius = "6px" if compact else "8px"
    min_width_result = "80px" if compact else "120px"
    gap = "8px" if compact else "12px"
    height = 120 if compact else 160

    components.html(
        f"""
        <div style="font-family: ui-sans-serif, system-ui; line-height:1.4;">
          <div style="display:flex; gap:{gap}; align-items:end; flex-wrap:nowrap;">
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:{label_font}; color:#6b7280; margin-bottom:2px;">起點價</label>
              <input id="bias-a{suffix}" type="text" inputmode="decimal" placeholder="A"
                     style="padding:{padding}; width:{input_width}; border:1px solid #d1d5db; border-radius:{border_radius}; outline:none;">
            </div>
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:{label_font}; color:#6b7280; margin-bottom:2px;">終點價</label>
              <input id="bias-b{suffix}" type="text" inputmode="decimal" placeholder="B"
                     style="padding:{padding}; width:{input_width}; border:1px solid #d1d5db; border-radius:{border_radius}; outline:none;">
            </div>
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:{label_font}; color:#6b7280; margin-bottom:2px;">乖離率</label>
              <div id="bias-result{suffix}"
                   style="min-width:{min_width_result}; padding:{padding}; border:1px solid #f3f4f6; border-radius:{border_radius}; background:#f9fafb; font-weight:600; text-align:right;">
                -
              </div>
            </div>
          </div>
        </div>

        <script>
        (function() {{
          const S = "{suffix}";
          const aEl = document.getElementById("bias-a" + S);
          const bEl = document.getElementById("bias-b" + S);
          const res = document.getElementById("bias-result" + S);

          const toNum = (s) => {{
            if (!s) return NaN;
            s = (""+s).replace(/,/g, "").trim();
            return Number(s);
          }};

          function compute() {{
            const a = toNum(aEl.value);
            const b = toNum(bEl.value);
            if (!isFinite(a) || !isFinite(b)) return;
            if (a === 0) {{
              res.textContent = "A 不能為 0";
              res.style.color = "#ef4444";
              aEl.value = ""; bEl.value = "";
              setTimeout(() => aEl.focus(), 0);
              return;
            }}
            const bias = ((b - a) / a) * 100;
            res.textContent = bias.toFixed(2) + "%";
            res.style.color = bias >= 0 ? "#16a34a" : "#ef4444";
            aEl.value = "";
            bEl.value = "";
            setTimeout(() => aEl.focus(), 0);
          }}

          aEl.addEventListener("keydown", (e) => {{
            if (e.key === "Enter") {{
              e.preventDefault();
              bEl.focus();
            }}
          }});

          // B 點：Enter 或 Tab 都計算
          bEl.addEventListener("keydown", (e) => {{
            if (e.key === "Enter" || e.key === "Tab") {{
              e.preventDefault();
              compute();
            }}
          }});

          setTimeout(() => aEl.focus(), 0);
        }})();
        </script>
        """,
        height=height,
    )

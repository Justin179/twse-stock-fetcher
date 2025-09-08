# src/ui/volume_avg_calculator.py
import streamlit as st
import streamlit.components.v1 as components

def render_volume_avg_calculator(
    key_suffix: str = "",
    compact: bool = True,
    default_days: int = 5,
):
    """
    成交量快算：輸入「成交量」與「交易日數」，顯示「日均量」(四捨五入到小數點後第二位)

    現在的快捷鍵：
    - 在「總成交量」欄位按 Enter -> 直接計算、顯示結果，並清空成交量欄位（保留交易日數）
    - 在「交易日數」欄位按 Enter 或 Tab -> 計算
    """
    st.caption("🧮 成交量快算（估日均量）")

    suffix = f"-{key_suffix}" if key_suffix else ""

    # 尺寸與樣式（比照 bias_calculator）
    input_width = "100px" if compact else "160px"
    padding = "6px 8px" if compact else "8px 10px"
    label_font = "13px" if compact else "14px"
    border_radius = "6px" if compact else "8px"
    min_width_result = "100px" if compact else "140px"
    gap = "8px" if compact else "12px"

    # 輕微上移（縮減與上個元件的垂直留白）
    # 並把高度略縮短
    height = 108 if compact else 150
    top_margin = "-8px" if compact else "-6px"

    components.html(
        f"""
        <div style="font-family: ui-sans-serif, system-ui; line-height:1.4; margin-top:{top_margin};">
          <div style="display:flex; gap:{gap}; align-items:end; flex-wrap:nowrap;">
            <!-- 成交量 -->
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:{label_font}; color:#6b7280; margin-bottom:2px;">總成交量</label>
              <input id="vol-total{suffix}" type="text" inputmode="decimal" placeholder="例如 800"
                     style="padding:{padding}; width:{input_width}; border:1px solid #d1d5db; border-radius:{border_radius}; outline:none;">
            </div>

            <!-- 交易日數 -->
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:{label_font}; color:#6b7280; margin-bottom:2px;">交易日數</label>
              <input id="vol-days{suffix}" type="text" inputmode="numeric" placeholder="天數"
                     value="{default_days}"
                     style="padding:{padding}; width:{input_width}; border:1px solid #d1d5db; border-radius:{border_radius}; outline:none;">
            </div>

            <!-- 日均量（結果） -->
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:{label_font}; color:#6b7280; margin-bottom:2px;">日均量</label>
              <div id="vol-result{suffix}"
                   style="min-width:{min_width_result}; padding:{padding}; border:1px solid #f3f4f6; border-radius:{border_radius}; background:#f9fafb; font-weight:600; text-align:right;">
                -
              </div>
            </div>
          </div>
        </div>

        <script>
        (function() {{
          const S = "{suffix}";
          const totalEl = document.getElementById("vol-total" + S);
          const daysEl  = document.getElementById("vol-days" + S);
          const resEl   = document.getElementById("vol-result" + S);

          const toNum = (s) => {{
            if (!s) return NaN;
            s = (""+s).replace(/,/g, "").trim();
            return Number(s);
          }};

          function compute() {{
            const total = toNum(totalEl.value);
            const days  = toNum(daysEl.value);
            if (!isFinite(total) || !isFinite(days)) return;

            if (days <= 0) {{
              resEl.textContent = "天數需 > 0";
              resEl.style.color = "#ef4444";
              daysEl.focus();
              return;
            }}
            if (total < 0) {{
              resEl.textContent = "成交量不可 < 0";
              resEl.style.color = "#ef4444";
              totalEl.focus();
              return;
            }}

            const avg = total / days;
            resEl.textContent = avg.toFixed(2); // 四捨五入至小數第二位
            resEl.style.color = "#111827";
          }}

          // 成交量：Enter -> 直接計算並清空成交量欄位
          totalEl.addEventListener("keydown", (e) => {{
            if (e.key === "Enter") {{
              e.preventDefault();
              compute();
              totalEl.value = "";
              setTimeout(() => totalEl.focus(), 0);
            }}
          }});

          // 交易日數：Enter 或 Tab -> 計算
          daysEl.addEventListener("keydown", (e) => {{
            if (e.key === "Enter" || e.key === "Tab") {{
              e.preventDefault();
              compute();
            }}
          }});
        }})();
        </script>
        """,
        height=height,
    )

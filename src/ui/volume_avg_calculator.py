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
    - Enter 在「成交量」欄位 -> 跳到「交易日數」
    - Enter 或 Tab 在「交易日數」欄位 -> 計算
    - 預設交易日數為 5，可自行改
    """
    st.caption("🧮 成交量快算（估日均量）")

    suffix = f"-{key_suffix}" if key_suffix else ""

    # 依 compact 模式控制尺寸，與 bias_calculator 風格一致
    input_width = "100px" if compact else "160px"
    padding = "6px 8px" if compact else "8px 10px"
    label_font = "13px" if compact else "14px"
    border_radius = "6px" if compact else "8px"
    min_width_result = "100px" if compact else "140px"
    gap = "8px" if compact else "12px"
    height = 120 if compact else 160

    components.html(
        f"""
        <div style="font-family: ui-sans-serif, system-ui; line-height:1.4;">
          <div style="display:flex; gap:{gap}; align-items:end; flex-wrap:nowrap;">
            <!-- 成交量 -->
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:{label_font}; color:#6b7280; margin-bottom:2px;">成交量</label>
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
            // 四捨五入到小數點後第二位
            resEl.textContent = avg.toFixed(2);
            resEl.style.color = "#111827";
          }}

          // 成交量：Enter -> 跳到交易日數
          totalEl.addEventListener("keydown", (e) => {{
            if (e.key === "Enter") {{
              e.preventDefault();
              daysEl.focus();
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

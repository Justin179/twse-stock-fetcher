# src/ui/bias_calculator.py
import streamlit as st
import streamlit.components.v1 as components

def render_bias_calculator():
    """
    乖離率快算 (A→B) — 純前端版
    - 輸入 A 後可按 Tab 跳到 B（不會 rerun）
    - 只有在 B 按 Enter 才計算乖離率
    - 計算後清空並把焦點帶回 A
    - 不使用 Streamlit widget，避免任何輸入造成 rerun
    """
    st.caption("✏️ 乖離率快算 (A→B)")

    components.html(
        """
        <div style="font-family: ui-sans-serif, system-ui; line-height:1.4;">
          <div style="display:flex; gap:12px; align-items:end; flex-wrap:wrap;">
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:12px; color:#6b7280; margin-bottom:4px;">A 點 (起始價)</label>
              <input id="bias-a" type="text" inputmode="decimal" placeholder="A 點"
                     style="padding:8px 10px; width:160px; border:1px solid #d1d5db; border-radius:8px; outline:none;">
            </div>
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:12px; color:#6b7280; margin-bottom:4px;">B 點 (最終價)</label>
              <input id="bias-b" type="text" inputmode="decimal" placeholder="B 點"
                     style="padding:8px 10px; width:160px; border:1px solid #d1d5db; border-radius:8px; outline:none;">
            </div>
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:12px; color:#6b7280; margin-bottom:4px;">乖離率</label>
              <div id="bias-result"
                   style="min-width:120px; padding:8px 10px; border:1px solid #f3f4f6; border-radius:8px; background:#f9fafb; font-weight:600;">
                -
              </div>
            </div>
          </div>
        </div>

        <script>
          (function(){
            const aEl = document.getElementById("bias-a");
            const bEl = document.getElementById("bias-b");
            const res = document.getElementById("bias-result");

            const toNum = (s) => {
              if (!s) return NaN;
              s = (""+s).replace(/,/g, "").trim();
              return Number(s);
            };

            function compute() {
              const a = toNum(aEl.value);
              const b = toNum(bEl.value);

              if (!isFinite(a) || !isFinite(b)) return; 
              if (a === 0) {
                res.textContent = "A 不能為 0";
                res.style.color = "#ef4444"; 
                aEl.value = ""; bEl.value = "";
                setTimeout(()=>aEl.focus(), 0);
                return;
              }
              const bias = ((b - a) / a) * 100;
              const text = bias.toFixed(2) + "%";
              res.textContent = text;
              res.style.color = bias >= 0 ? "#16a34a" : "#ef4444"; 

              aEl.value = "";
              bEl.value = "";
              setTimeout(()=>aEl.focus(), 0);
            }

            aEl.addEventListener("keydown", (e)=>{
              if (e.key === "Enter") {
                e.preventDefault();
                bEl.focus();
              }
            });

            // 只有在 B 按 Enter 時才計算
            bEl.addEventListener("keydown", (e)=>{
              if (e.key === "Enter") {
                e.preventDefault();
                compute();
              }
            });

            // 初始聚焦 A
            setTimeout(()=>aEl.focus(), 0);
          })();
        </script>
        """,
        height=120,
    )

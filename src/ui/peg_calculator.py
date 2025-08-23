# src/ui/peg_calculator.py
import sqlite3
import pandas as pd
from datetime import datetime
import streamlit as st
import streamlit.components.v1 as components

'''
若只有「今年預估 EPS」：
    成長率 = (今年 ÷ 去年 − 1) × 100（%）
    PE = 現價 ÷ 今年預估EPS（Forward PE）

若同時有「今年、明年預估 EPS」：
    成長率1 = (今年 ÷ 去年 − 1) × 100（%）
    成長率2 = (明年 ÷ 今年 − 1) × 100（%）
    平均成長率 = (成長率1 + 成長率2) / 2（%）
    PE = 現價 ÷ 明年預估EPS（Forward PE）

特例：去年EPS ≤ 0 或無資料，但「今年、明年預估EPS」皆有且 >0：
    成長率 = (明年 ÷ 今年 − 1) × 100（%）
    PE = 現價 ÷ 明年預估EPS（Forward PE）
    PEG = PE ÷ 成長率（%）

最終：PEG = PE ÷ 成長率（百分比）
'''
# --- 取去年 EPS（同 plot_eps_with_close_price 的邏輯） ---
def _get_last_year_eps(stock_id: str, db_path: str = "data/institution.db"):
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(
            "SELECT season, eps FROM profitability_ratios WHERE stock_id = ?",
            conn, params=(stock_id,)
        )
        conn.close()
        if df.empty:
            return None

        # 今年/去年
        current_year = datetime.now().year
        last_year = current_year - 1

        # season 格式：YYYYQn（例如 2024Q1）
        df["year"] = df["season"].str.slice(0, 4).astype(int)
        df["quarter"] = df["season"].str.slice(5, 6).astype(int)

        eps_last_year = df[(df["year"] == last_year) & (df["quarter"].isin([1, 2, 3, 4]))]["eps"].sum()
        return float(eps_last_year) if pd.notna(eps_last_year) else None
    except Exception:
        return None

# --- 取現價 c1（同 price_break_display_module 的取得方式） ---
def _get_current_price(stock_id: str, sdk=None):
    try:
        # 延遲匯入避免循環依賴
        from analyze.analyze_price_break_conditions_dataloader import get_today_prices
        today = get_today_prices(stock_id, sdk)
        return float(today["c1"]) if today and "c1" in today else None
    except Exception:
        return None

def render_peg_calculator(stock_id: str, sdk=None, key_suffix: str = ""):
    """
    在畫面上渲染：今年預估 EPS、明年預估 EPS、三段式結果（PE / 成長率 = PEG）
    """
    last_eps = _get_last_year_eps(stock_id)
    price = _get_current_price(stock_id, sdk)

    st.caption("✏️ PEG 快算")

    suffix = f"-{key_suffix}" if key_suffix else ""

    last_eps_js = "null" if last_eps is None else f"{last_eps:.6f}"
    price_js = "null" if price is None else f"{price:.6f}"

    components.html(
        f"""
        <div style="font-family: ui-sans-serif, system-ui; line-height:1.4;">
          <div style="display:flex; gap:12px; align-items:end; flex-wrap:wrap;">
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:14px; color:#6b7280; margin-bottom:4px;">今年預估 EPS</label>
              <input id="peg-this{suffix}" type="text" inputmode="decimal" placeholder="今年 EPS"
                     style="padding:8px 10px; width:160px; border:1px solid #d1d5db; border-radius:8px; outline:none;">
            </div>
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:14px; color:#6b7280; margin-bottom:4px;">明年預估 EPS（可留白）</label>
              <input id="peg-next{suffix}" type="text" inputmode="decimal" placeholder="明年 EPS"
                     style="padding:8px 10px; width:180px; border:1px solid #d1d5db; border-radius:8px; outline:none;">
            </div>
            <div style="display:flex; flex-direction:column;">
              <label style="font-size:14px; color:#6b7280; margin-bottom:4px;">PEG = Forward PE / EPS成長率</label>
              <div id="peg-wrap{suffix}"
                   style="min-width:260px; padding:8px 10px; border:1px solid #f3f4f6; border-radius:8px; background:#f9fafb; font-weight:600; display:flex; align-items:center;">
                <span id="peg{suffix}">-</span>
                <span style="margin:0 6px; opacity:.8;">=</span>
                <span id="pe{suffix}">-</span>
                <span style="margin:0 6px; opacity:.8;">/</span>
                <span id="growth{suffix}">-%</span>
              </div>
              <!-- 特例提示（預設隱藏） -->
              <div id="peg-note{suffix}" style="margin-top:4px; font-size:12px; color:#6b7280; display:none;"></div>
            </div>
          </div>

          <div style="margin-top:6px; font-size:14px; color:#6b7280;">
            使用基礎：去年EPS = <b>{'-' if last_eps is None else f'{last_eps:.2f}'}</b>，
            現價 = <b>{'-' if price is None else f'{price:.2f}'}</b>
          </div>
        </div>

        <script>
        (function() {{
          const S = "{suffix}";
          const lastEPS = {last_eps_js};
          const price   = {price_js};

          const thisEl = document.getElementById("peg-this" + S);
          const nextEl = document.getElementById("peg-next" + S);

          // 結果元素
          const wrapEl = document.getElementById("peg-wrap" + S);
          const peEl   = document.getElementById("pe" + S);
          const grEl   = document.getElementById("growth" + S);
          const pegEl  = document.getElementById("peg" + S);

          // 特例提示元素
          const noteEl = document.getElementById("peg-note" + S);
          const showNote = (text) => {{
            if (text) {{
              noteEl.textContent = text;
              noteEl.style.display = "block";
            }} else {{
              noteEl.textContent = "";
              noteEl.style.display = "none";
            }}
          }};

          const toNum = (s) => {{
            if (!s) return NaN;
            s = (""+s).replace(/,/g, "").trim();
            return Number(s);
          }};

          // 依 PEG 區間回傳前綴符號
          function pegPrefix(peg) {{
            if (!isFinite(peg)) return "";
            if (peg >= 0 && peg <= 0.50) return "✅ ";
            if (peg > 0.50 && peg <= 1.00) return "✔️ ";
            if (peg > 1.00 && peg <= 1.20) return "⚠️ ";
            if (peg > 1.20) return "❌ ";
            return "";
          }}

          function showTriplet(pe, growthPct, peg, ok=true) {{
            if (!ok) {{
              peEl.textContent = "-";
              grEl.textContent = "-%";
              pegEl.textContent = "-";
              wrapEl.style.color = "#ef4444";
              return;
            }}
            peEl.textContent  = (isFinite(pe) ? pe.toFixed(2) : "-");
            grEl.textContent  = (isFinite(growthPct) ? growthPct.toFixed(2) + "%" : "-%");
            const prefix = pegPrefix(peg);
            pegEl.textContent = (isFinite(peg) ? prefix + peg.toFixed(2) : "-");
            wrapEl.style.color = (isFinite(peg) && peg <= 1) ? "#16a34a" : "#111827";
          }}

          function compute() {{
            const thisEPS = toNum(thisEl.value);
            const nextEPS = toNum(nextEl.value);

            // 基本檢查
            if (!isFinite(thisEPS) || thisEPS <= 0) {{
              showTriplet(NaN, NaN, NaN, false); // 今年EPS無效
              showNote("");
              return;
            }}
            if (!isFinite(price) || price <= 0) {{
              showTriplet(NaN, NaN, NaN, false); // 缺現價
              showNote("");
              return;
            }}

            // --- 特例：去年EPS <= 0 或無資料，但今年/明年皆有且 > 0 ---
            if (isFinite(nextEPS) && nextEPS > 0 && (!isFinite(lastEPS) || lastEPS <= 0)) {{
              const g = ((nextEPS - thisEPS) / thisEPS) * 100;   // 今年→明年 成長率（%）
              if (!isFinite(g) || g <= 0) {{
                showTriplet(NaN, NaN, NaN, false);
                showNote("");
                return;
              }}
              const pe = price / nextEPS;                        // Forward PE 用明年EPS
              const peg = pe / g;                                // 成長率以百分比計
              showTriplet(pe, g, peg, true);
              showNote("去年EPS為負或無資料，採用：Forward PE(明年) / 今年→明年成長率。");

              // 收尾
              thisEl.value = "";
              nextEl.value = "";
              setTimeout(() => thisEl.focus(), 0);
              return;
            }}

            // --- 既有邏輯：需要「去年EPS > 0」 ---
            if (!isFinite(lastEPS) || lastEPS <= 0) {{
              showTriplet(NaN, NaN, NaN, false); // 缺去年EPS且未符合特例
              showNote("");
              return;
            }}

            // 去年→今年
            const g1 = ((thisEPS - lastEPS) / lastEPS) * 100; // 成長率（%）
            let growthPct = g1;
            let pe = price / thisEPS;                         // 預設用今年EPS做 Forward PE

            // 若有明年：平均成長率，PE用明年
            if (isFinite(nextEPS) && nextEPS > 0) {{
              const g2 = ((nextEPS - thisEPS) / thisEPS) * 100; // 今年→明年
              growthPct = (g1 + g2) / 2.0;                      // 平均成長率（%）
              pe = price / nextEPS;                             // Forward 1Y
            }}

            if (!isFinite(growthPct) || growthPct <= 0) {{
              showTriplet(NaN, NaN, NaN, false);
              showNote("");
              return;
            }}

            const peg = pe / growthPct; // 成長率以百分比計
            showTriplet(pe, growthPct, peg, true);
            showNote("");

            // 收尾
            thisEl.value = "";
            nextEl.value = "";
            setTimeout(() => thisEl.focus(), 0);
          }}

          /* 今年 EPS 欄位
             - Enter：直接計算（視為沒有明年EPS）
             - Tab：維持預設行為，跳到 B 欄
          */
          thisEl.addEventListener("keydown", (e) => {{
            if (e.key === "Enter") {{
              e.preventDefault();
              nextEl.value = ""; // 明年EPS清空
              compute();
            }}
          }});

          // B 欄：Enter 或 Tab -> 計算
          nextEl.addEventListener("keydown", (e) => {{
            if (e.key === "Enter" || e.key === "Tab") {{
              e.preventDefault();
              compute();
            }}
          }});

          setTimeout(() => thisEl.focus(), 0);
        }})();
        </script>
        """,
        height=230,
    )

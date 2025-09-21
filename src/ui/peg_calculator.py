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
    若同時有今年與明年預估 eps，會額外顯示「單年 PEG（明年 / 今年→明年）」。
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

            <!-- 顯示區：若只有今年 EPS 顯示一個結果；若有今年與明年 EPS 顯示兩個結果（2Y avg + 1Y） -->
            <div style="display:flex; flex-direction:column; gap:6px; min-width:260px;">
              <label style="font-size:14px; color:#6b7280; margin-bottom:4px;">PEG 結果</label>
              <div style="display:flex; flex-direction:column; gap:8px; align-items:flex-start;">
                <div id="peg-wrap-2y{suffix}"
                     style="width:100%; padding:8px 10px; border:1px solid #f3f4f6; border-radius:8px; background:#f9fafb; font-weight:600; display:flex; align-items:center; justify-content:space-between;">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:12px; color:#6b7280;">2Y avg</span>
                    <span id="peg{suffix}">-</span>
                    <span style="margin:0 6px; opacity:.8;">=</span>
                    <span id="pe{suffix}">-</span>
                    <span style="margin:0 6px; opacity:.8;">/</span>
                    <span id="growth{suffix}">-%</span>
                  </div>
                </div>

                <div id="peg-wrap-1y{suffix}"
                     style="width:100%; padding:8px 10px; border:1px solid #f3f4f6; border-radius:8px; background:#fffaf0; font-weight:600; display:flex; align-items:center; justify-content:space-between;">
                  <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:12px; color:#6b7280;">1Y</span>
                    <span id="peg1y{suffix}">-</span>
                    <span style="margin:0 6px; opacity:.8;">=</span>
                    <span id="pe1y{suffix}">-</span>
                    <span style="margin:0 6px; opacity:.8;">/</span>
                    <span id="growth1y{suffix}">-%</span>
                  </div>
                </div>
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

          // 結果元素（2Y）
          const wrap2El = document.getElementById("peg-wrap-2y" + S);
          const peEl   = document.getElementById("pe" + S);
          const grEl   = document.getElementById("growth" + S);
          const pegEl  = document.getElementById("peg" + S);

          // 結果元素（1Y）
          const wrap1El = document.getElementById("peg-wrap-1y" + S);
          const pe1El   = document.getElementById("pe1y" + S);
          const gr1El   = document.getElementById("growth1y" + S);
          const peg1El  = document.getElementById("peg1y" + S);

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

          const pegPrefix = (peg) => {{
            if (!isFinite(peg)) return "";
            if (peg >= 0 && peg <= 0.50) return "✅ ";
            if (peg > 0.50 && peg <= 1.00) return "✔️ ";
            if (peg > 1.00 && peg <= 1.20) return "⚠️ ";
            if (peg > 1.20) return "❌ ";
            return "";
          }};

          function showTripletTo(peTarget, grTarget, pegTarget, wrapTarget, pe, growthPct, peg, ok=true) {{
            if (!ok) {{
              peTarget.textContent = "-";
              grTarget.textContent = "-%";
              pegTarget.textContent = "-";
              wrapTarget.style.color = "#ef4444";
              return;
            }}
            peTarget.textContent  = (isFinite(pe) ? pe.toFixed(2) : "-");
            grTarget.textContent  = (isFinite(growthPct) ? growthPct.toFixed(2) + "%" : "-%");
            const prefix = pegPrefix(peg);
            pegTarget.textContent = (isFinite(peg) ? prefix + peg.toFixed(2) : "-");
            wrapTarget.style.color = (isFinite(peg) && peg <= 1) ? "#16a34a" : "#111827";
          }}

          function compute() {{
            const thisEPS = toNum(thisEl.value);
            const nextEPS = toNum(nextEl.value);

            // 重置顯示
            showTripletTo(peEl, grEl, pegEl, wrap2El, NaN, NaN, NaN, false);
            showTripletTo(pe1El, gr1El, peg1El, wrap1El, NaN, NaN, NaN, false);
            showNote("");

            // 基本檢查
            if (!isFinite(thisEPS) || thisEPS <= 0) {{
              // 今年EPS無效
              return;
            }}
            if (!isFinite(price) || price <= 0) {{
              // 缺現價
              return;
            }}

            // 若有明年 EPS
            if (isFinite(nextEPS) && nextEPS > 0) {{
              // 特例：去年EPS <= 0 或無資料，只有單年可算（今年→明年）
              if (!isFinite(lastEPS) || lastEPS <= 0) {{
                const g = ((nextEPS - thisEPS) / thisEPS) * 100;   // 今年→明年 成長率（%）
                if (!isFinite(g) || g <= 0) {{
                  showTripletTo(pe1El, gr1El, peg1El, wrap1El, NaN, NaN, NaN, false);
                  return;
                }}
                const pe = price / nextEPS;                        // Forward PE 用明年EPS
                const peg = pe / g;                                // 成長率以百分比計
                showTripletTo(pe1El, gr1El, peg1El, wrap1El, pe, g, peg, true);
                showNote("去年EPS為負或無資料，僅顯示單年 PEG（明年 / 今年→明年）。");

                // 清空輸入並 focus
                thisEl.value = "";
                nextEl.value = "";
                setTimeout(() => thisEl.focus(), 0);
                return;
              }}

              // 正常情況（有去年EPS且有今年+明年）：同時計算 2Y 平均 與 1Y
              const g1 = ((thisEPS - lastEPS) / lastEPS) * 100; // 去年→今年（%）
              const g2 = ((nextEPS - thisEPS) / thisEPS) * 100; // 今年→明年（%）
              const growthAvg = (g1 + g2) / 2.0;
              const peForward = price / nextEPS;

              // 2Y avg （需要 growthAvg > 0）
              if (!isFinite(growthAvg) || growthAvg <= 0) {{
                showTripletTo(peEl, grEl, pegEl, wrap2El, NaN, NaN, NaN, false);
              }} else {{
                const peg2 = peForward / growthAvg;
                showTripletTo(peEl, grEl, pegEl, wrap2El, peForward, growthAvg, peg2, true);
              }}

              // 1Y 單年（今年→明年）
              if (!isFinite(g2) || g2 <= 0) {{
                showTripletTo(pe1El, gr1El, peg1El, wrap1El, NaN, NaN, NaN, false);
              }} else {{
                const peg1 = peForward / g2;
                showTripletTo(pe1El, gr1El, peg1El, wrap1El, peForward, g2, peg1, true);
              }}

              // 清空輸入並 focus
              thisEl.value = "";
              nextEl.value = "";
              setTimeout(() => thisEl.focus(), 0);
              return;
            }}

            // 若沒有明年 EPS，維持原先行為：用今年EPS 做 Forward PE，成長率為 去年→今年
            if (!isFinite(lastEPS) || lastEPS <= 0) {{
              // 缺去年EPS
              return;
            }}
            const g_last_to_this = ((thisEPS - lastEPS) / lastEPS) * 100;
            if (!isFinite(g_last_to_this) || g_last_to_this <= 0) {{
              return;
            }}
            const pe_now = price / thisEPS;
            const peg_now = pe_now / g_last_to_this;
            // 顯示在 2Y 區塊（舊的主要位置）
            showTripletTo(peEl, grEl, pegEl, wrap2El, pe_now, g_last_to_this, peg_now, true);
            // 1Y 區塊不顯示
            showTripletTo(pe1El, gr1El, peg1El, wrap1El, NaN, NaN, NaN, false);

            thisEl.value = "";
            setTimeout(() => thisEl.focus(), 0);
          }}

          // 鍵盤事件
          thisEl.addEventListener("keydown", (e) => {{
            if (e.key === "Enter") {{
              e.preventDefault();
              nextEl.value = ""; // 明年EPS清空
              compute();
            }}
          }});
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
        height=260,
    )

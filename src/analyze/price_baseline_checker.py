# src/analyze/price_baseline_checker.py

def check_price_vs_baseline_and_deduction(c1: float, baseline: float, deduction: float) -> str:
    """
    判斷現價 c1 與基準價、扣抵值的關係，回傳對應的 HTML 訊息字串。
    """
    if baseline is None or deduction is None:
        return "- **基準價 / 扣抵值**：資料不足"

    # 扣抵方向判斷與百分比計算
    if baseline < deduction:
        percentage = ((deduction - baseline) / baseline) * 100
        kd_status = f"<span style='color:blue'><b>扣抵向上 +{percentage:.2f}%</b></span>"
    elif baseline > deduction:
        percentage = ((baseline - deduction) / baseline) * 100
        kd_status = f"<span style='color:blue'><b>扣抵向下 -{percentage:.2f}%</b></span>"
    else:
        kd_status = "<span style='color:blue'><b>扣抵持平</b></span>"


    # 組共同的字串（baseline / deduction 加粗）
    ref_text = f"(基 {baseline:.2f} 扣 {deduction:.2f} {kd_status})"

    if c1 > baseline and c1 > deduction:
        return f"- ✅ **現價站上基準價與扣抵值** {ref_text}"
    elif c1 > baseline:
        return f"- ⚠️ **現價只站上基準價** {ref_text}"
    elif c1 > deduction:
        return f"- ✔️ **現價只站上扣抵值** {ref_text}"
    elif c1 < baseline and c1 < deduction:
        return f"- ❌ **現價跌破基準價與扣抵值** {ref_text}"
    else:
        return f"- ➖ **現價持平基準價或扣抵值** {ref_text}"

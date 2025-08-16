# src/analyze/price_baseline_checker.py

def check_price_vs_baseline_and_deduction(c1: float, baseline: float, deduction: float) -> str:
    """
    判斷現價 c1 與基準價、扣抵值的關係，回傳對應的 HTML 訊息字串。
    """
    if baseline is None or deduction is None:
        return "- **基準價 / 扣抵值**：資料不足"

    if c1 > baseline and c1 > deduction:
        return f"- ✅ **現價站上基準價與扣抵值** (基: {baseline:.2f} / 扣: {deduction:.2f})"
    elif c1 > baseline:
        return f"- ✔️ **現價只站上基準價** (基: {baseline:.2f} / 扣: {deduction:.2f})"
    elif c1 > deduction:
        return f"- ✔️ **現價只站上扣抵值** (基: {baseline:.2f} / 扣: {deduction:.2f})"
    else:
        return f"- ❌ **現價低於基準價與扣抵值** (基: {baseline:.2f} / 扣: {deduction:.2f})"

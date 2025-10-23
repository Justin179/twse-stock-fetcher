"""
成交量預估模組
提供兩種預估方式：
1. 每分鐘平均成交量推估法
2. 時間區間切割法（每5分鐘）
"""
from datetime import datetime, time
from typing import Optional, Tuple, Dict


def get_trading_minutes_elapsed() -> Optional[int]:
    """
    計算從開盤到現在經過了多少分鐘
    台股交易時間：09:00 ~ 13:30 (270分鐘)
    
    Returns:
        已交易的分鐘數，如果不在交易時間內則返回 None
    """
    now = datetime.now()
    current_time = now.time()
    
    # 交易時間定義
    market_open = time(9, 0)
    market_close = time(13, 30)
    
    # 判斷是否在交易時間內
    if current_time < market_open:
        return None
    elif current_time > market_close:
        # 收盤後，視為已交易完整270分鐘
        return 270
    
    # 計算經過的分鐘數
    now_datetime = datetime.combine(datetime.today(), current_time)
    open_datetime = datetime.combine(datetime.today(), market_open)
    elapsed = (now_datetime - open_datetime).total_seconds() / 60
    
    return int(elapsed)


def get_remaining_minutes() -> Optional[int]:
    """
    計算距離收盤還剩多少分鐘
    
    Returns:
        剩餘的分鐘數，如果不在交易時間內則返回 None
    """
    elapsed = get_trading_minutes_elapsed()
    if elapsed is None:
        return None
    
    remaining = 270 - elapsed
    return max(0, remaining)


def forecast_by_avg_rate(current_volume: float, yesterday_volume: float) -> Optional[Dict[str, any]]:
    """
    方式1：用目前的每分鐘平均成交量推估收盤量
    
    Args:
        current_volume: 今日目前成交量（張）
        yesterday_volume: 昨日成交量（張）
    
    Returns:
        {
            'forecast_volume': 預估收盤量（張）,
            'forecast_pct': 預估量相對昨量的百分比,
            'avg_per_minute': 目前每分鐘平均成交量
        }
        若無法計算則返回 None
    """
    elapsed = get_trading_minutes_elapsed()
    remaining = get_remaining_minutes()
    
    if elapsed is None or elapsed == 0 or yesterday_volume == 0:
        return None
    
    # 計算每分鐘平均成交量
    avg_per_minute = current_volume / elapsed
    
    # 推估收盤量 = 目前量 + (剩餘分鐘數 × 每分鐘平均量)
    forecast_volume = current_volume + (remaining * avg_per_minute)
    
    # 計算相對昨量的百分比
    forecast_pct = (forecast_volume / yesterday_volume) * 100 if yesterday_volume > 0 else None
    
    return {
        'forecast_volume': forecast_volume,
        'forecast_pct': forecast_pct,
        'avg_per_minute': avg_per_minute,
        'elapsed_minutes': elapsed,
        'remaining_minutes': remaining
    }


def forecast_by_time_segment(current_volume: float, yesterday_volume: float) -> Optional[Dict[str, any]]:
    """
    方式2：時間區間切割法（每5分鐘）判斷進度
    
    Args:
        current_volume: 今日目前成交量（張）
        yesterday_volume: 昨日成交量（張）
    
    Returns:
        {
            'status': 'ahead'/'ontrack'/'behind',  # 超前/持平/落後
            'diff_pct': 差異百分比（正數表示超前，負數表示落後）,
            'current_segment': 當前所在的時間段（第幾個5分鐘）,
            'prev_target': 前一個時間段應達成的量,
            'next_target': 後一個時間段應達成的量,
            'volume_per_segment': 每5分鐘應有的量
        }
        若無法計算則返回 None
    """
    elapsed = get_trading_minutes_elapsed()
    
    if elapsed is None or yesterday_volume == 0:
        return None
    
    # 總共54個時間段（270分鐘 / 5分鐘）
    total_segments = 54
    volume_per_segment = yesterday_volume / total_segments
    
    # 計算當前在第幾個時間段（從0開始）
    current_segment = elapsed // 5
    
    # 計算前一個和後一個時間段應達成的量
    prev_target = current_segment * volume_per_segment
    next_target = (current_segment + 1) * volume_per_segment
    
    # 判斷進度狀態
    if current_volume > next_target:
        status = 'ahead'
        # 超前百分比 = (當前量 - 後一個時間段目標) / 後一個時間段目標 * 100
        diff_pct = ((current_volume - next_target) / next_target * 100) if next_target > 0 else 0
    elif current_volume < prev_target:
        status = 'behind'
        # 落後百分比 = (前一個時間段目標 - 當前量) / 前一個時間段目標 * 100
        diff_pct = -((prev_target - current_volume) / prev_target * 100) if prev_target > 0 else 0
    else:
        status = 'ontrack'
        # 持平時計算相對於中間值的偏移
        mid_target = (prev_target + next_target) / 2
        diff_pct = ((current_volume - mid_target) / mid_target * 100) if mid_target > 0 else 0
    
    return {
        'status': status,
        'diff_pct': diff_pct,
        'current_segment': current_segment + 1,  # 轉為1-based顯示
        'prev_target': prev_target,
        'next_target': next_target,
        'volume_per_segment': volume_per_segment,
        'elapsed_minutes': elapsed
    }


def render_volume_forecast(current_volume: float, yesterday_volume: float):
    """
    在 Streamlit 中顯示兩種成交量預估結果
    
    Args:
        current_volume: 今日目前成交量（張）
        yesterday_volume: 昨日成交量（張）
    """
    import streamlit as st
    
    st.markdown("**預估量：**")
    
    # 檢查是否在交易時間內
    elapsed = get_trading_minutes_elapsed()
    if elapsed is None:
        st.markdown("- ℹ️ 非交易時間，無法預估")
        return
    
    if elapsed == 270:
        st.markdown("- ℹ️ 已收盤，無需預估")
        return
    
    # 方式1：每分鐘平均成交量推估法
    forecast1 = forecast_by_avg_rate(current_volume, yesterday_volume)
    if forecast1:
        pct = forecast1['forecast_pct']
        if pct is not None:
            if pct >= 100:
                color = "#ef4444"  # 紅色
                icon = "📈"
            else:
                color = "#16a34a"  # 綠色
                icon = "📉"
            
            st.markdown(
                f"{icon} 分均預估量: <span style='color:{color}; font-weight:bold'>{pct:.0f}%</span> "
                f"（預估收: {forecast1['forecast_volume']:.0f}張）",
                unsafe_allow_html=True
            )
    
    # 方式2：時間區間切割法
    forecast2 = forecast_by_time_segment(current_volume, yesterday_volume)
    if forecast2:
        status = forecast2['status']
        diff_pct = abs(forecast2['diff_pct'])
        
        if status == 'ahead':
            status_text = "進度超前"
            color = "#ef4444"  # 紅色
            icon = "🚀"
            pct_display = f"+{diff_pct:.0f}%"
        elif status == 'behind':
            status_text = "進度落後"
            color = "#16a34a"  # 綠色
            icon = "🐢"
            pct_display = f"-{diff_pct:.0f}%"
        else:
            status_text = "進度持平"
            color = "#f59e0b"  # 橘色
            icon = "➡️"
            pct_display = f"{forecast2['diff_pct']:+.0f}%"
        
        st.markdown(
            f"""- {icon} 5分間隔預估量: <span style='color:{color}; font-weight:bold'>{status_text}</span> <span style='color:{color}'>({pct_display})</span>
          <details style='margin-left: 20px;'>
            <summary style='cursor: pointer; font-size:12px; color:#999; list-style: none;'>📊 詳細數據</summary>
            <div style='font-size:13px; color:#666; padding: 5px 0 0 20px;'>
                已交易時間 {forecast2['elapsed_minutes']} 分鐘 → 第 {forecast2['current_segment']}/{54} 段 → 每段應達 {forecast2['volume_per_segment']:.1f} 張<br>
                前段目標 {forecast2['prev_target']:.1f} → 目前量 {current_volume:.0f} → 後段目標 {forecast2['next_target']:.1f}
            </div>
          </details>
            """,
            unsafe_allow_html=True
        )

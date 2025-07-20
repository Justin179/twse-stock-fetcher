from datetime import datetime, timedelta

def is_fubon_api_maintenance_time(now=None):
    """
    判斷是否為富邦 API 維護時間（週六早上7點～週日晚上7點）
    """
    if now is None:
        now = datetime.now()

    weekday = now.weekday()  # Monday = 0, Sunday = 6

    saturday_7am = now.replace(hour=7, minute=0, second=0, microsecond=0)
    saturday_7am -= timedelta(days=(weekday - 5) % 7)

    sunday_7pm = saturday_7am + timedelta(days=1, hours=12)

    return saturday_7am <= now <= sunday_7pm

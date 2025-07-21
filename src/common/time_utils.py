from datetime import datetime, time

def is_fubon_api_maintenance_time(now=None):
    """
    富邦 API 維護時間 為 週六早上7點 ～ 週日晚上7點，但刻意延長到 週一早上9點，因為如果週一就已經是交易日，但還沒開盤，
    所以抓到的o就是None，所以9點前仍應視為維護時間，先用db現有最新的資料頂上，9點之後會使用API，因能抓到當日最新的o就ok
    """
    if now is None:
        now = datetime.now()

    weekday = now.weekday()  # Monday = 0, Sunday = 6
    current_time = now.time()

    # 情況 1: 週六 且 時間 >= 07:00
    if weekday == 5 and current_time >= time(7, 0):
        return True
    # 情況 2: 週日整天
    elif weekday == 6:
        return True
    # 情況 3: 週一 且 時間 < 09:00
    elif weekday == 0 and current_time < time(9, 0):
        return True
    else:
        return False

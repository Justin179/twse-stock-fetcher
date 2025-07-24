# condition_selector.py
import tkinter as tk
import ctypes

# 📌 規劃 GUI 出現的位置（右下角）
def get_window_position(width, height, offset_x=400, offset_y=100):
    user32 = ctypes.windll.user32
    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)

    x = screen_width - width - offset_x
    y = screen_height - height - offset_y
    return x, y


# ✅ 主函式：取得使用者選擇的條件
def get_user_selected_conditions(use_gui=True):
    default_conditions = {
        "收盤價站上 上彎5日均 且乖離小": True,
        "5 10多頭排列 均線上彎 開口小": True,
        "10 24多頭排列 均線上彎 開口小": True,
        "24日均乖離<15%": True,
        "量價同步": True,
        "收盤價站上上彎5週均": True,
        "站上上彎72日均": False
    }

    if not use_gui:
        return default_conditions

    conditions = {}

    # ✅ 點 [開始篩選] 時收集所有勾選結果
    def submit():
        for key in checkbox_vars:
            conditions[key] = checkbox_vars[key].get()
        print("✅ 使用者勾選的條件:")
        print(conditions)
        root.destroy()

    # ✅ 點 [X] 關閉視窗時，直接退出主程式
    def on_close():
        print("❌ 使用者關閉了條件視窗，程式中止。")
        print()  # 空一行
        root.destroy()
        exit()

    # 🎯 建立 GUI 視窗並配置到右下角
    width, height = 350, 330
    x, y = get_window_position(width=400, height=250, offset_x=200, offset_y=200)


    root = tk.Tk()
    root.title("請選擇要套用的條件")
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.option_add("*Font", ("Microsoft JhengHei", 13))  # 全域預設字型
    root.protocol("WM_DELETE_WINDOW", on_close)

    checkbox_vars = {}
    for label, default in default_conditions.items():
        var = tk.BooleanVar(value=default)
        cb = tk.Checkbutton(root, text=label, variable=var)
        cb.pack(anchor="w", padx=10, pady=3)
        checkbox_vars[label] = var

    tk.Button(root, text="開始篩選", command=submit).pack(pady=10)
    # ✅ 支援按下 Enter 鍵等同點擊「開始篩選」
    root.bind("<Return>", lambda event: submit())
    # ✅ 支援按下 Esc 鍵等同關閉視窗退出
    root.bind("<Escape>", lambda event: on_close())
    root.mainloop()

    return conditions

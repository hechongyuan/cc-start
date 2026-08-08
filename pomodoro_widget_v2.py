# -*- coding: utf-8 -*-
"""意式熟番茄 · 桌面番茄钟挂件 v2

在 v1（浅紫薰衣草）基础上做的一版全新视觉设计：
- 主题「意式熟番茄」：深酒红主卡 + 黄铜金边，像老式意式酒标
- 签名元素：进度环中央一颗会「熟」的番茄 —— 专注时从青绿慢慢变红，
  熟了代表本轮专注完成；休息时再变回青绿
- 功能与 v1 完全一致：开始/暂停/重置/可调时长/到点提示音+弹窗通知/拖动/右键菜单
"""
import ctypes                                          # 导入 ctypes，用于调用 Windows 系统底层 API（设置高 DPI）
import threading                                       # 导入 threading，用于在后台线程播放提示音，避免卡界面
import time                                            # 导入 time，用于读取精确时间（倒计时用单调时钟）
import tkinter as tk                                   # 导入 tkinter 并起别名 tk，它是 Python 自带的图形界面库
import winsound                                        # 导入 winsound，用于播放 Windows 系统提示音

# Windows 高 DPI，避免文字模糊
try:                                                   # 尝试执行下面的 DPI 设置
    ctypes.windll.shcore.SetProcessDpiAwareness(1)     # 调用系统 API 让程序感知高 DPI 屏幕，文字才清晰
except Exception:                                      # 如果调用失败（例如系统不支持该 API）
    pass                                               # 直接跳过，不影响程序运行

# ---------- 配色（意式熟番茄：深酒红 + 黄铜金边） ----------
CARD        = "#361412"   # 主卡片背景：深酒红
CARD_EDGE   = "#C9A24B"   # 主卡片描边：黄铜金（像酒标烫金）
STRIP       = "#451A16"   # 设置面板背景：比主卡略亮的酒红
BTN         = "#7A2B1D"   # 按钮底色：赤陶红
BTN_HOVER   = "#9A3A26"   # 按钮悬停色：更亮的赤陶红
TEXT        = "#FFF4E2"   # 主文字：奶油白（深色底上保证可读）
TEXT_DIM    = "#D3B98F"   # 次要文字：金褐
WORK_ACC    = "#FF4D2E"   # 专注模式强调色：熟番茄红
BREAK_ACC   = "#5E8A40"   # 休息模式强调色：叶子绿
TRACK       = "#52211A"   # 进度环底轨：深棕红
TOM_GREEN   = "#5E8A40"   # 青番茄（未熟）
TOM_RED     = "#FF4D2E"   # 熟番茄
LEAF        = "#3E7A2E"   # 番茄叶子
HILITE      = "#E9A88E"   # 番茄光泽高光（左上角浅粉椭圆）
TRANSPARENT = "#010001"   # 透明色键（此颜色区域将镂空）

# ---------- 布局 ----------
W, H = 260, 372                                       # 挂件窗口的宽度和高度（单位：像素）
CARD_R    = 26                                        # 主卡片的圆角半径
RING_CX, RING_CY = 130, 116                           # 进度环圆心的 x、y 坐标
RING_R, RING_W   = 82, 12                             # 进度环的半径和线条宽度
TOM_R     = 50                                        # 中央番茄果实的半径
BTN_ROW_Y = 252                                       # 一排控制按钮所在的 y 坐标
CLOSE_X, CLOSE_Y = 242, 26                            # 关闭按钮（✕）的圆心坐标
STRIP_TOP, STRIP_BOT = 284, 366                       # 设置面板的上边界、下边界 y 坐标

FONT  = "Segoe UI"                                    # 数字/英文所用的字体
FONT_CN = "Microsoft YaHei UI"                        # 中文所用的字体（微软雅黑）

# ---------- 阶段配置表 ----------
# 把「专注 / 休息」两个阶段的所有可变信息集中在这里，方便以后增减阶段
PHASES = {                                            # 阶段字典：key 为内部名，value 为该阶段的配置
    "work":  {"label": "专注中", "acc": WORK_ACC,     # work 阶段：显示名「专注中」、进度环用番茄红
              "minutes_attr": "work_min",             #         时长存在哪个属性上
              "next": "break",                        #         结束后切换到 break
              "notify": ("工作结束", "干得漂亮！番茄熟啦，休息 {mins} 分钟吧")},  # 结束时的通知标题和内容
    "break": {"label": "休息中", "acc": BREAK_ACC,    # break 阶段：显示名「休息中」、进度环用叶子绿
              "minutes_attr": "break_min",            #         时长存在哪个属性上
              "next": "work",                         #         结束后切换回 work
              "notify": ("休息结束", "开始下一轮专注吧！")},   # 结束时的通知标题和内容
}


class PomodoroWidget:                                 # 定义番茄钟挂件的主类
    def __init__(self):                               # 构造函数：程序入口，负责初始化界面和计时状态
        self.root = tk.Tk()                           # 创建 tkinter 主窗口对象
        self.root.title("番茄钟")                     # 设置窗口标题（显示在任务栏等位置）
        self.root.overrideredirect(True)              # 去掉系统边框和标题栏，做成无边框的悬浮窗
        x = self.root.winfo_screenwidth() - W - 60    # 计算起始 x：屏幕宽度减窗口宽，再留 60 像素边距
        self.root.geometry(f"{W}x{H}+{x}+{150}")      # 设置窗口尺寸为 W×H，并放到屏幕右上区域
        self.root.attributes("-topmost", True)        # 让窗口始终置顶，盖在其他窗口上面
        self.root.attributes("-transparentcolor", TRANSPARENT)  # 把 TRANSPARENT 这种颜色设为镂空透明
        self.root.configure(bg=TRANSPARENT)           # 把窗口背景色设为那个透明色

        self.canvas = tk.Canvas(self.root, width=W, height=H, bg=TRANSPARENT,
                                highlightthickness=0, bd=0)     # 创建画布，覆盖整个窗口，无边框
        self.canvas.pack()                            # 把画布铺满窗口

        # ---- 计时状态 ----
        self.work_min, self.break_min = 25, 5         # 默认工作时长 25 分钟、休息时长 5 分钟
        self.mode = "work"          # "work" | "break"  # 当前阶段：work=专注，break=休息
        self.running = False                          # 计时器是否正在运行
        self.after_id = None                          # 保存 after() 的定时任务编号，用于取消
        self.end_time = 0.0                           # 倒计时结束的绝对时间（用单调时钟）
        self.remaining = self._phase_total()          # 剩余秒数，初始为工作阶段满时长
        self.settings_open = False                    # 设置面板是否展开
        self._settings_widgets = []                   # 保存设置面板上的控件，方便关闭时统一销毁
        self.buttons = {}                             # 画布按钮的字典（记录位置、文字、回调等）
        self.progress_arc = None                      # 进度环圆弧对象的引用
        self.tomato = None                            # 中央番茄果实对象的引用（用于原地变色）
        self._pressed = None                          # 当前按住的按钮名字；None 表示没按按钮
        self._hovered = None                          # 当前鼠标悬停的按钮名字；None 表示没悬停
        self._drag_off = (0, 0)                       # 拖动开始时，鼠标相对窗口左上角的偏移

        self._draw()                                  # 第一次绘制整个界面
        self._bind()                                  # 绑定鼠标事件（点击、拖动、悬停等）
        self.root.mainloop()                          # 进入事件循环，保持窗口一直显示并响应

    # ================= 绘图 =================
    def _rrect(self, x1, y1, x2, y2, r, **kw):        # 在画布上画一个圆角矩形
        pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
               x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]  # 用多边形近似圆角矩形的顶点
        return self.canvas.create_polygon(pts, smooth=True, **kw)       # 创建平滑多边形，形成圆角矩形

    def _btn(self, name, x, y, r, text, cmd):         # 在画布上创建一个圆形按钮
        cid = self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=BTN, outline="")  # 画按钮的圆形底色
        tid = self.canvas.create_text(x, y, text=text, fill=TEXT,
                                      font=(FONT, int(r*0.95), "bold"))  # 在圆心画按钮文字（奶油白）
        self.buttons[name] = {"x": x, "y": y, "r": r, "cmd": cmd,
                              "circle": cid, "text": tid}                # 记录按钮的所有信息供点击/悬停判断

    def _ring_arc(self, extent, color):                # 在进度环位置画一段圆弧（底轨或进度）
        return self.canvas.create_arc(
            RING_CX-RING_R, RING_CY-RING_R,           # 外接矩形左上角
            RING_CX+RING_R, RING_CY+RING_R,           # 外接矩形右下角
            start=90, extent=extent, style=tk.ARC,     # 从 90 度（12 点方向）开始画
            width=RING_W, outline=color)              # 圆弧宽度和颜色

    def _lerp(self, c1, c2, t):                       # 在两个颜色之间线性插值，得到中间色
        def ch(hexs):                                 # 把两位十六进制字符转成 0~255 的整数
            return int(hexs, 16)                      # 十六进制解析成十进制
        r = int(ch(c1[1:3]) + (ch(c2[1:3]) - ch(c1[1:3])) * t)  # 红色通道按比例 t 从 c1 走向 c2
        g = int(ch(c1[3:5]) + (ch(c2[3:5]) - ch(c1[3:5])) * t)  # 绿色通道同理
        b = int(ch(c1[5:7]) + (ch(c2[5:7]) - ch(c1[5:7])) * t)  # 蓝色通道同理
        return f"#{r:02x}{g:02x}{b:02x}"              # 拼回 #rrggbb 格式的十六进制颜色

    def _tomato_color(self, frac):                    # 根据当前进度算出番茄该是什么颜色
        t = max(0.0, min(1.0, frac))                  # 把进度限制在 0~1 之间（防越界）
        if self.mode == "work":                       # 专注阶段：青绿慢慢熟成红色
            return self._lerp(TOM_GREEN, TOM_RED, t)  # 越接近结束越红
        return self._lerp(TOM_RED, TOM_GREEN, t)      # 休息阶段：红色慢慢退回青绿

    def _tomato(self, color):                         # 画中央的番茄（果实 + 叶子 + 高光），返回果实引用
        c = self.canvas                               # 简写：c 指向画布
        cx, cy, r = RING_CX, RING_CY, TOM_R           # 番茄圆心与果实半径
        fid = c.create_oval(cx-r, cy-r, cx+r, cy+r,   # 画果实：一个圆形
                            fill=color, outline="")   # 用当前颜色填充，无描边
        # 高光：果实左上角一个浅粉色小椭圆，模拟光照，让番茄有立体感
        c.create_oval(cx-r*0.45, cy-r*0.52, cx-r*0.05, cy-r*0.20,
                      fill=HILITE, outline="")        # 半椭圆贴在果实左上
        # 叶子：三片小椭圆组成叶冠，贴在果实顶部
        top = cy - r                                  # 果实顶部边界的 y 坐标
        for dx, dy, rw, rh in ((-11, -2, 8, 4.5),     # 左片叶子
                               (0, -8, 8, 4.5),       # 中片叶子
                               (11, -2, 8, 4.5)):     # 右片叶子
            c.create_oval(cx+dx-rw, top+dy-rh,        # 每片叶子画一个小椭圆
                          cx+dx+rw, top+dy+rh,        # 椭圆的外接矩形右下角
                          fill=LEAF, outline="")      # 用叶子绿填充
        # 叶茎：从果实顶部伸到叶冠中心的一条短线，让番茄更像真的
        c.create_line(cx, top+4, cx, top-12,          # 从果顶向上画到叶冠
                      fill=LEAF, width=3)             # 用叶子绿、3 像素粗
        self.tomato = fid                             # 记住果实对象的 id，供以后变色
        return fid                                    # 返回果实 id

    def _draw(self):                                  # 重绘整个界面（每次状态变化时调用）
        c = self.canvas                               # 简写：c 指向画布对象
        c.delete("all")                               # 清空画布上所有图形
        self.progress_arc = None                      # 清掉旧圆弧的引用
        self.buttons = {}                             # 清空按钮字典，稍后重新创建
        self._hovered = None                          # 重绘后悬停状态也清空

        # 主卡片：深酒红圆角矩形，加上黄铜金描边（像烫金酒标）
        self._rrect(6, 6, 254, 286, CARD_R, fill=CARD, outline=CARD_EDGE, width=2)

        # 进度环底轨：几乎一整圈深棕红圆弧
        self._ring_arc(359.9, TRACK)

        # 中央番茄：初始为青绿（专注刚开始）
        self._tomato(TOM_GREEN)

        # 文字
        self.time_text = c.create_text(RING_CX, 112, text=self._fmt(self.remaining),
                                       fill=TEXT, font=(FONT, 30, "bold"))  # 环中心显示倒计时时间（奶油白）
        self.mode_text = c.create_text(RING_CX, 196, text=self._mode_label(),
                                       fill=TEXT_DIM, font=(FONT_CN, 11))   # 番茄下方显示「专注中/休息中」（金褐）

        # 控制按钮
        self._btn("reset", 78,  BTN_ROW_Y, 18, "↺", self._reset)          # 重置按钮（↺）
        self._btn("play",  130, BTN_ROW_Y, 24, "▶", self._toggle)         # 开始/暂停按钮（▶/⏸）
        self._btn("gear",  182, BTN_ROW_Y, 18, "⚙", self._toggle_settings)# 设置按钮（⚙）
        self._btn("close", CLOSE_X, CLOSE_Y, 12, "✕", self._quit)         # 关闭按钮（✕）

        # 设置面板
        self._destroy_settings_widgets()              # 先销毁旧的设置控件（保证重绘不残留）
        if self.settings_open:                        # 如果设置面板处于展开状态
            self._rrect(6, STRIP_TOP, 254, STRIP_BOT, 14, fill=STRIP)      # 画设置面板的圆角背景
            self._make_spin("work", 18, STRIP_TOP + 12)   # 创建「工作时长」的输入框
            self._make_spin("break", 18, STRIP_TOP + 50)  # 创建「休息时长」的输入框

        self._update_display()                        # 更新一次显示内容（时间、圆弧、番茄、按钮状态）

    def _make_spin(self, key, x, y):                  # 创建设置面板里的一行「标签 + 数字输入框」
        label = tk.Label(self.root,
                         text=PHASES[key]["label"].replace("中", "时长"),  # 从配置表取阶段名拼出标签
                         bg=STRIP, fg=TEXT, font=(FONT_CN, 9))  # 左侧的文字标签（奶油白）
        label.place(x=x, y=y + 3)                     # 用 place 定位到面板上的指定位置
        self._settings_widgets.append(label)          # 记录该控件，便于以后销毁

        sb = tk.Spinbox(self.root, from_=1, to=120, width=7, justify="center",
                        bg=CARD, fg=TEXT, buttonbackground=BTN,
                        relief=tk.FLAT, highlightthickness=0, font=(FONT_CN, 9))  # 数字输入框（1~120 分钟）
        sb.delete(0, tk.END)                          # 清空输入框默认内容
        sb.insert(0, str(getattr(self, PHASES[key]["minutes_attr"])))  # 从配置表取属性名，填入当前分钟数
        sb.place(x=x + 95, y=y)                       # 放到标签右边
        sb.bind("<KeyRelease>", lambda e, k=key: self._apply_setting(k, sb.get()))  # 松开键盘时应用新时长
        self._settings_widgets.append(sb)             # 记录该控件，便于以后销毁

    def _toggle_settings(self):                       # 展开/收起设置面板
        self.settings_open = not self.settings_open   # 翻转展开状态
        self._draw()                                  # 重绘界面以显示或隐藏面板

    def _destroy_settings_widgets(self):              # 销毁设置面板上所有控件
        for w in self._settings_widgets:              # 遍历记录下来的控件
            w.destroy()                               # 销毁该控件（每个控件只会被销毁一次）
        self._settings_widgets = []                   # 清空控件列表

    def _update_display(self):                        # 更新显示：进度环、时间、番茄、模式、播放按钮
        c = self.canvas                               # 简写：c 指向画布
        total = self._phase_total()                   # 获取当前阶段的完整时长（秒）
        frac = 1 - self.remaining / total if total else 0  # 已过去的比例：0 表示刚满，1 表示结束

        if frac > 0.005:                              # 只要走过一点点就更新进度圆弧
            acc = PHASES[self.mode]["acc"]            # 从配置表取当前阶段的强调色
            ext = -359.9 * min(frac, 1.0)             # 按已过比例换算成圆弧角度（负号=顺时针）
            if self.progress_arc:                     # 如果圆弧已经存在
                c.itemconfig(self.progress_arc, extent=ext, outline=acc)  # 原地更新，不重建
            else:                                     # 否则（第一次画）
                self.progress_arc = self._ring_arc(ext, acc)  # 新建一段圆弧并记住它
        elif self.progress_arc:                       # 如果还没开始走但圆弧已存在（被重置了）
            c.delete(self.progress_arc)               # 删掉旧圆弧
            self.progress_arc = None                  # 清空引用

        # 让番茄跟着进度变色（专注变红 / 休息变绿），原地改填充色
        c.itemconfig(self.tomato, fill=self._tomato_color(frac))

        c.itemconfig(self.time_text, text=self._fmt(self.remaining))  # 刷新倒计时文字
        c.itemconfig(self.mode_text, text=self._mode_label())         # 刷新「专注中/休息中」
        c.itemconfig(self.buttons["play"]["text"],
                     text="⏸" if self.running else "▶")  # 运行时显示暂停符，否则显示播放符

    # ================= 计时逻辑 =================
    def _phase_total(self):                           # 返回当前阶段的完整时长（秒）
        return float(getattr(self, PHASES[self.mode]["minutes_attr"]) * 60)  # 从配置表取属性名，分钟 × 60

    def _mode_label(self):                            # 返回当前模式的文字标签
        return PHASES[self.mode]["label"]             # 从配置表取当前阶段的显示名

    def _fmt(self, secs):                             # 把秒数格式化成「分:秒」
        s = max(0, int(secs))                         # 防止负数，取整
        return f"{s // 60:02d}:{s % 60:02d}"          # 两位分钟 + 两位秒，例如 25:00

    def _stop(self):                                  # 停止计时（暂停/重置/到点时共用）
        self.running = False                          # 标记为已停止
        if self.after_id:                             # 如果有待执行的定时任务
            self.root.after_cancel(self.after_id)     # 取消定时任务
            self.after_id = None                      # 清空任务编号

    def _tick(self):                                  # 定时器每次触发时执行的函数
        if not self.running:                          # 如果已经暂停/停止
            return                                    # 直接返回，不再继续
        rem = self.end_time - time.monotonic()        # 用「结束时间 - 当前时间」算剩余秒数，精确无累计误差
        if rem <= 0:                                  # 如果剩余时间已经走完
            self.remaining = 0                        # 剩余秒数归零
            self._stop()                              # 停止计时
            self._update_display()                    # 刷新界面
            self._finish_phase()                      # 进入阶段切换（工作→休息 或 休息→工作）
            return                                    # 结束本次定时
        self.remaining = rem                          # 保存新的剩余秒数
        self._update_display()                        # 刷新界面
        self.after_id = self.root.after(100, self._tick)  # 100 毫秒后再执行一次本函数

    def _toggle(self):                                # 开始/暂停 切换
        if self.running:                              # 如果正在运行（点击=暂停）
            self.remaining = max(0.0, self.end_time - time.monotonic())  # 先把剩余时间保存下来
            self._stop()                              # 停止计时
        else:                                         # 否则（当前暂停，点击=开始）
            self.end_time = time.monotonic() + self.remaining  # 计算新的结束时间
            self.running = True                       # 标记为运行中
            self.after_id = self.root.after(100, self._tick)  # 启动定时器
        self._update_display()                        # 刷新界面（播放按钮图标会变化）

    def _reset(self):                                 # 重置当前阶段的倒计时
        self._stop()                                  # 停止计时
        self.remaining = self._phase_total()          # 剩余时间恢复为完整的当前阶段时长
        self._update_display()                        # 刷新界面

    def _finish_phase(self):                          # 一个阶段走完：切换阶段并提醒
        finished = PHASES[self.mode]                  # 取出刚结束阶段的配置
        title, msg_tmpl = finished["notify"]          # 取出该阶段的通知标题和内容模板
        next_mode = finished["next"]                  # 取出下一个阶段名
        self.mode = next_mode                         # 切换到新阶段
        msg = msg_tmpl.format(mins=getattr(self, PHASES[self.mode]["minutes_attr"]))  # 把新阶段时长填进通知内容
        self.remaining = self._phase_total()          # 新阶段的剩余时间设为满时长
        self._update_display()                        # 刷新界面
        self._play_sound()                            # 播放提示音
        self._notify(title, msg)                      # 弹出通知窗口

    def _apply_setting(self, key, val):               # 应用用户在设置面板输入的新时长
        try:                                          # 尝试把输入转成整数
            v = max(1, min(120, int(val)))            # 限制在 1~120 分钟之间
        except Exception:                             # 如果输入不是数字
            return                                    # 直接忽略，不做任何改动
        was_full = not self.running and self.remaining >= self._phase_total() - 0.5  # 是否「未开始且时长是满的」
        setattr(self, PHASES[key]["minutes_attr"], v) # 从配置表取属性名，更新对应时长
        if was_full and self.mode == key:             # 如果当前阶段还没开始计时
            self.remaining = self._phase_total()      # 让倒计时直接用新时长重新开始
        self._update_display()                        # 刷新界面

    # ================= 到点提醒 =================
    def _play_sound(self):                            # 播放提示音（放在子线程，避免阻塞界面）
        def beep():                                   # 定义真正发声的函数
            try:                                      # 尝试播放三段旋律
                for freq in (880, 988, 1175):         # 依次用 880/988/1175 三个频率
                    winsound.Beep(freq, 240)          # 每个频率响 240 毫秒
            except Exception:                         # 如果 Beep 失败（如无声卡）
                try:                                  # 尝试用系统提示音代替
                    winsound.MessageBeep()            # 播放 Windows 默认提示音
                except Exception:                     # 连这个也失败的话
                    pass                              # 放弃，什么都不播
        threading.Thread(target=beep, daemon=True).start()  # 在新线程里播放，主界面不卡顿

    def _notify(self, title, msg):                    # 弹出到点通知小窗口
        win = tk.Toplevel(self.root)                  # 创建一个顶层子窗口
        win.overrideredirect(True)                    # 去掉系统边框，做成简洁卡片
        win.attributes("-topmost", True)              # 通知窗口也置顶
        win.configure(bg=CARD)                        # 背景色与主卡片一致（深酒红）
        nw, nh = 250, 128                             # 通知窗口的宽和高
        x = self.root.winfo_x() + (W - nw) // 2       # 让通知显示在主窗口水平居中附近
        y = self.root.winfo_y() + (H - nh) // 2 - 30  # 竖直方向居中并稍微上移
        win.geometry(f"{nw}x{nh}+{x}+{y}")            # 设置通知窗口的位置和大小
        tk.Label(win, text=title, bg=CARD, fg=WORK_ACC,
                 font=(FONT_CN, 15, "bold")).pack(pady=(16, 4))  # 标题文字（番茄红）
        tk.Label(win, text=msg, bg=CARD, fg=TEXT,
                 font=(FONT_CN, 10)).pack()           # 正文文字（奶油白）
        tk.Button(win, text="知道了", command=win.destroy, bg=BTN, fg=TEXT,
                  activebackground=BTN_HOVER, activeforeground=TEXT,
                  relief=tk.FLAT, width=10, font=(FONT_CN, 10)).pack(pady=(12, 0))  # 「知道了」按钮，点击关闭
        win.after(10000, lambda: win.winfo_exists() and win.destroy())  # 10 秒后自动关闭（若还没被关）

    # ================= 交互 =================
    def _bind(self):                                  # 绑定鼠标事件
        self.canvas.bind("<ButtonPress-1>", self._on_press)      # 鼠标左键按下
        self.canvas.bind("<B1-Motion>", self._on_drag)          # 按住左键移动（拖动窗口）
        self.canvas.bind("<ButtonRelease-1>", self._on_release) # 鼠标左键松开
        self.canvas.bind("<Motion>", self._on_hover)            # 鼠标移动（按钮悬停效果）
        self.root.bind("<Button-3>", self._on_right)            # 鼠标右键按下（弹菜单）

    def _hit(self, name, x, y):                       # 判断某个坐标是否落在按钮圆形内
        b = self.buttons[name]                        # 取出该按钮的信息
        dx, dy = x - b["x"], y - b["y"]               # 计算与按钮圆心的水平、垂直距离
        return dx * dx + dy * dy <= (b["r"] + 4) ** 2 # 用勾股定理判断是否在圆内（半径外扩 4 便于点击）

    def _on_press(self, e):                           # 左键按下的处理
        for name in self.buttons:                     # 遍历所有按钮
            if self._hit(name, e.x, e.y):             # 如果按在某个按钮上
                self._pressed = name                  # 记录按住了哪个按钮
                return                                # 直接返回，不进入拖拽逻辑
        self._pressed = None                          # 没按到按钮，标记为「空白区域」
        self._drag_off = (e.x_root - self.root.winfo_x(),   # 记录鼠标到窗口左上角的偏移，
                          e.y_root - self.root.winfo_y())  # 供拖动时保持相对位置

    def _on_drag(self, e):                            # 按住移动的处理（拖动窗口）
        if self._pressed is not None:                 # 如果按住的是按钮（不是空白）
            return                                    # 不拖动窗口
        self.root.geometry(f"+{e.x_root - self._drag_off[0]}"  # 新窗口 x = 鼠标位置 - 偏移
                           f"+{e.y_root - self._drag_off[1]}") # 新窗口 y = 鼠标位置 - 偏移

    def _on_release(self, e):                         # 左键松开的处理
        name, self._pressed = self._pressed, None     # 取出按住记录并立即清空（一行搞定）
        if name and self._hit(name, e.x, e.y):        # 如果之前按的是按钮，且松开时还在该按钮上
            self.buttons[name]["cmd"]()               # 执行该按钮绑定的回调函数

    def _on_hover(self, e):                           # 鼠标移动的处理（悬停高亮）
        current = None                                # 先假设没悬停任何按钮
        for name in self.buttons:                     # 遍历所有按钮
            if self._hit(name, e.x, e.y):             # 如果鼠标落在该按钮上
                current = name                        # 记录当前悬停的是它
                break                                 # 找到一个就够了，提前结束
        if current == self._hovered:                  # 如果悬停状态没变化
            return                                    # 什么都不做，避免高频重复刷新
        if self._hovered:                             # 如果之前有悬停的旧按钮
            self.canvas.itemconfig(self.buttons[self._hovered]["circle"], fill=BTN)  # 恢复原色
        if current:                                   # 如果现在有新的悬停按钮
            self.canvas.itemconfig(self.buttons[current]["circle"], fill=BTN_HOVER)  # 高亮新按钮
        self._hovered = current                       # 更新悬停记录

    def _on_right(self, e):                           # 右键弹菜单
        menu = tk.Menu(self.root, tearoff=0, bg=CARD, fg=TEXT,
                       activebackground=BTN_HOVER, activeforeground=TEXT,
                       font=(FONT_CN, 10))            # 创建右键菜单，样式与卡片一致
        menu.add_command(label="退出番茄钟", command=self._quit)  # 菜单项：退出
        try:                                          # 尝试弹出菜单
            menu.tk_popup(e.x_root, e.y_root)         # 在鼠标位置弹出菜单
        finally:                                      # 无论成功与否
            menu.grab_release()                       # 释放鼠标捕获，防止菜单不消失

    def _quit(self):                                  # 退出程序
        self.root.destroy()                           # 销毁主窗口，结束程序


if __name__ == "__main__":                            # 只有直接运行本文件时才执行下面代码
    PomodoroWidget()                                  # 创建并运行番茄钟挂件

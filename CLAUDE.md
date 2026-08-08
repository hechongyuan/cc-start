# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

一个纯 Python 标准库实现的桌面番茄钟挂件（tkinter），单文件项目，仅面向 Windows，无任何第三方依赖。

## 常用命令

- 启动挂件：双击 `启动番茄钟.bat`，或命令行 `python pomodoro_widget.py`
- 语法检查：`python -m py_compile pomodoro_widget.py`
- 本项目没有测试框架；验证方式 = `py_compile` 通过 + 手动启动看界面。

⚠️ 运行程序会打开置顶透明 GUI 窗口并进入 `mainloop()` 阻塞，无法当作后台任务做「运行验证」——启动后它会一直挂着，验证完需要手动关掉。

## 架构要点

所有逻辑都在单文件 `pomodoro_widget.py` 的 `PomodoroWidget` 类里：

- **阶段配置表 `PHASES`**：把「专注/休息」的显示名、强调色、时长属性名、下一阶段、通知文案集中在一个 dict。新增或修改阶段只改这张表，不要在代码里散落 if/else。
- **无边框透明置顶窗口**：`overrideredirect(True)` 去边框 + `-transparentcolor` 把 `TRANSPARENT`（#010001）镂空 + `-topmost` 置顶。
- **圆形进度环**：canvas `create_arc` + `style=tk.ARC`，从 12 点方向（`start=90`）顺时针画（负 extent）。更新用 `itemconfig` 原地改 extent/outline，不重建。
- **精确倒计时**：`time.monotonic()` 记录 `end_time`，100ms 一次的 `after()` 里用 `end_time - now()` 算剩余，避免累计误差。暂停时存剩余秒数，恢复时重设 end_time。
- **画布按钮**：按钮都是 canvas 上的 oval+text，登记在 `buttons` 字典（圆心/半径/回调），点击与悬停用勾股距离 `_hit()` 命中测试。加按钮 = 调 `_btn()` 并在 `_draw()` 里登记。
- **全量重画模型**：`_draw()` 每次都 `delete("all")` 清空重画；设置面板是 tk 控件 `place` 定位，重画前先 `_destroy_settings_widgets()`。改任何显示逻辑都要配合这个模型。
- **阶段切换**：倒计时结束 → `_finish_phase()` → 切 `self.mode` → `winsound.Beep` 在后台线程播提示音 → `tk.Toplevel` 弹通知。

## 约定

- 注释是全中文、逐行都有的 —— 改动时保持这个风格。
- 颜色常量集中在文件顶部（浅紫薰衣草主题，主卡 `#E8C6FF`）。
- 强依赖 Windows（`winsound`、`ctypes.windll.shcore` 高 DPI），不要改成跨平台写法。
- UI 文案一律用中文。
- 项目是 git 仓库，远程在 GitHub `hechongyuan/cc-start`，默认分支 `master`。

## 文件

- `pomodoro_widget.py` — 全部逻辑（入口 `if __name__ == "__main__"`）
- `启动番茄钟.bat` — 双击启动脚本（优先 `pythonw` 无控制台窗口）
- `README.md` — 用户使用说明
- `E8C6FF-imageonline.co-1920x1080.png` — 选色参考图（配色来源）

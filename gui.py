# gui.py - PyQt6 图形界面主程序
# 修复：编辑/刷新竞态闪退 + 表达式计算 + 延迟优化

import sys
import json
import ast
import operator
import traceback
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QPushButton, QHeaderView,
    QStatusBar, QLineEdit, QMessageBox, QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont

import config
import fetcher
import alerter
import formatter

WATCHLIST_FILE = Path(__file__).parent / "watchlist.json"


# ---- 安全算术表达式求值 ----
_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise ValueError("仅支持数字")
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError("不支持的运算符")
        return op(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError("不支持的运算符")
        return op(_eval_node(node.operand))
    raise ValueError("不支持的表达式")


def safe_eval(expr: str) -> float:
    """安全求值：500/2 → 250.0。非法表达式抛 ValueError。"""
    tree = ast.parse(expr, mode="eval")
    return float(_eval_node(tree.body))


def load_watchlist() -> list:
    if WATCHLIST_FILE.exists():
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data and isinstance(data[0], str):
                return [{"code": c, "upper": None, "lower": None,
                         "sell_qty": None, "buy_qty": None} for c in data]
            for item in data:
                item.setdefault("sell_qty", None)
                item.setdefault("buy_qty", None)
            return data
        except Exception:
            pass
    return list(config.STOCKS)


def save_watchlist(stocks: list) -> None:
    try:
        with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(stocks, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class FetchThread(QThread):
    data_ready = pyqtSignal(object, object)
    progress   = pyqtSignal(int, str)

    def __init__(self, codes: list):
        super().__init__()
        self.codes = codes

    def run(self):
        try:
            df, error_msg = fetcher.fetch_stocks_with_progress(self.codes, self.progress.emit)
        except Exception as e:
            import pandas as pd
            df, error_msg = pd.DataFrame(), f"线程异常: {e}"
            self.progress.emit(100, "出错")
        self.data_ready.emit(df, error_msg)


class StockMonitor(QMainWindow):

    COL_CODE      = 0
    COL_NAME      = 1
    COL_PRICE     = 2
    COL_PCT       = 3
    COL_AMT       = 4
    COL_VOL       = 5
    COL_TURNOVER  = 6
    COL_BUY       = 7
    COL_BUY_QTY   = 8
    COL_SELL      = 9
    COL_SELL_QTY  = 10
    COL_BUY_ALT   = 11
    COL_SELL_ALT  = 12

    EDITABLE_COLS = {COL_SELL, COL_SELL_QTY, COL_BUY, COL_BUY_QTY}
    FLASH_COLS    = {COL_CODE, COL_NAME, COL_PRICE, COL_PCT, COL_AMT,
                     COL_VOL, COL_TURNOVER, COL_SELL_ALT, COL_BUY_ALT}

    COLUMNS = ["股票代码", "名称", "最新价", "涨跌幅", "涨跌额",
               "成交量", "成交额", "买入价", "买入数量", "卖出价", "卖出数量",
               "买入状态", "卖出状态"]

    COLOR_UP        = QColor("#FF4444")
    COLOR_DOWN      = QColor("#22AA44")
    COLOR_FLAT      = QColor("#CCCCCC")
    COLOR_ALERT_A   = QColor("#7A3A00")
    COLOR_ALERT_B   = QColor("#3A1500")
    COLOR_BG        = QColor("#1E1E2E")
    COLOR_HEADER_BG = QColor("#2A2A3E")
    COLOR_ROW_ALT   = QColor("#25253A")
    COLOR_EDITABLE  = QColor("#1A2A1A")

    def __init__(self):
        super().__init__()
        self.stocks = load_watchlist()
        self.codes: list = [s["code"] for s in self.stocks]
        self._fetch_thread = None
        self._fetching = False
        self._last_rows = []
        self._last_alerts = {}
        self._fail_count = 0
        self._flash_state = False
        self._alerted_rows: dict = {}

        # 编辑保护：正在编辑时完全跳过表格重建和网络请求
        self._editing = False
        self._editing_row = -1
        self._editing_col = -1

        self._init_ui()
        self._start_auto_refresh()
        self._start_flash_timer()
        self._do_fetch()

    # ------------------------------------------------------------------ #
    #  UI 初始化
    # ------------------------------------------------------------------ #

    def _init_ui(self):
        self.setWindowTitle("A股实时行情监控")
        self.setMinimumSize(1200, 460)
        self.resize(1400, 560)
        self.setStyleSheet(self._make_stylesheet())

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 10, 14, 8)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("A股实时行情监控")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #88CCFF;")
        self.status_label = QLabel("正在加载…")
        self.status_label.setStyleSheet("color: #AAAACC; font-size: 12px;")
        self.refresh_btn = QPushButton("立即刷新")
        self.refresh_btn.setFixedWidth(90)
        self.refresh_btn.clicked.connect(self._do_fetch)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.status_label)
        top.addWidget(self.refresh_btn)
        layout.addLayout(top)

        input_row = QHBoxLayout()
        input_label = QLabel("股票代码：")
        input_label.setStyleSheet("color: #CCCCDD; font-size: 13px;")
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("输入代码后回车或点「添加」，如 000001、600036、159870")
        self.code_input.setFixedWidth(320)
        self.code_input.returnPressed.connect(self._add_stock)
        self.add_btn = QPushButton("添加")
        self.add_btn.setFixedWidth(72)
        self.add_btn.clicked.connect(self._add_stock)
        self.del_btn = QPushButton("删除选中")
        self.del_btn.setFixedWidth(90)
        self.del_btn.clicked.connect(self._delete_selected)

        hint = QLabel("💡 双击「买入价/卖出价/数量」格子可编辑；支持表达式如 500/2 或 =500/2，回车得 250")
        hint.setStyleSheet("color: #8888AA; font-size: 12px;")

        input_row.addWidget(input_label)
        input_row.addWidget(self.code_input)
        input_row.addWidget(self.add_btn)
        input_row.addWidget(self.del_btn)
        input_row.addSpacing(16)
        input_row.addWidget(hint)
        input_row.addStretch()
        layout.addLayout(input_row)

        # ---- 刷新进度条 + 倒计时标签 ----
        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("准备就绪")
        self.progress_bar.hide()

        self.countdown_label = QLabel("")
        self.countdown_label.setFixedWidth(90)
        self.countdown_label.setStyleSheet("color: #6666AA; font-size: 11px;")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        progress_row.addWidget(self.progress_bar)
        progress_row.addWidget(self.countdown_label)
        layout.addLayout(progress_row)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        col_widths = [
            (self.COL_CODE, 90), (self.COL_NAME, 110),
            (self.COL_BUY, 85), (self.COL_BUY_QTY, 85),
            (self.COL_SELL, 85), (self.COL_SELL_QTY, 85),
            (self.COL_BUY_ALT, 130), (self.COL_SELL_ALT, 130),
        ]
        for col, width in col_widths:
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(col, width)

        self.table.itemDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.itemChanged.connect(self._on_item_changed)

        layout.addWidget(self.table)
        self._update_status_bar()

    def _make_stylesheet(self) -> str:
        return f"""
            QMainWindow, QWidget {{
                background-color: {self.COLOR_BG.name()};
                color: #EEEEEE;
                font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            }}
            QTableWidget {{
                background-color: {self.COLOR_BG.name()};
                gridline-color: #3A3A5A;
                border: none;
                font-size: 13px;
            }}
            QHeaderView::section {{
                background-color: {self.COLOR_HEADER_BG.name()};
                color: #88CCFF;
                font-weight: bold;
                font-size: 13px;
                padding: 5px;
                border: none;
                border-bottom: 1px solid #3A3A5A;
            }}
            QPushButton {{
                background-color: #3A3A3E;
                color: #EEEEEE;
                border: 1px solid #5A5A8A;
                border-radius: 4px;
                padding: 5px 14px;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #4A4A7E; }}
            QPushButton:disabled {{ color: #666688; }}
            QLineEdit {{
                background-color: #2A2A3E;
                color: #EEEEEE;
                border: 1px solid #5A5A8A;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border: 1px solid #88CCFF; }}
            QStatusBar {{ font-size: 12px; color: #888899; }}
            QProgressBar {{
                background-color: #1A1A2E;
                border: 1px solid #3A3A5A;
                border-radius: 3px;
                text-align: center;
                color: #CCCCDD;
                font-size: 11px;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3366CC, stop:0.5 #66AAFF, stop:1 #3366CC);
                border-radius: 2px;
            }}
        """

    def _fmt_price(self, val) -> str:
        try:
            v = float(val)
            return f"{v:.3f}" if v < 10 else f"{v:.2f}"
        except (TypeError, ValueError):
            return ""

    # ------------------------------------------------------------------ #
    #  编辑处理（同步处理 + _editing 保护，无队列/无延迟）
    # ------------------------------------------------------------------ #

    def _on_cell_double_clicked(self, item: QTableWidgetItem):
        """双击进入编辑：设标志位，禁止刷新和表格重建"""
        try:
            if item.column() in self.EDITABLE_COLS:
                self._editing = True
                self._editing_row = item.row()
                self._editing_col = item.column()
                self.table.editItem(item)
        except Exception:
            pass

    def _on_item_changed(self, item: QTableWidgetItem):
        """
        编辑提交后同步处理（不含延迟）。

        安全前提：_editing=True 阻止了 _populate_table 和 _do_fetch，
        所以此时不会有其他代码触碰表格。用 blockSignals 防重入。
        """
        try:
            col = item.column()
            if col not in self.EDITABLE_COLS:
                return
            row = item.row()
            if row < 0 or row >= len(self.stocks):
                return

            # 先标记编辑结束，允许后续刷新
            self._editing = False
            self._editing_row = -1
            self._editing_col = -1

            text = item.text().strip()
            is_qty = col in (self.COL_SELL_QTY, self.COL_BUY_QTY)

            # 取旧值（出错了恢复）
            old_cfg = self.stocks[row]
            old_map = {
                self.COL_SELL:     old_cfg.get("upper"),
                self.COL_SELL_QTY: old_cfg.get("sell_qty"),
                self.COL_BUY:      old_cfg.get("lower"),
                self.COL_BUY_QTY:  old_cfg.get("buy_qty"),
            }
            old_value = old_map.get(col)

            value = None
            display = ""
            error_msg = None

            if text:
                try:
                    expr = text[1:] if text.startswith("=") else text
                    num = safe_eval(expr)
                    if is_qty:
                        value = int(num)
                        display = formatter.fmt_qty(value)
                    else:
                        value = float(num)
                        display = self._fmt_price(value)
                except (ValueError, TypeError, ZeroDivisionError):
                    value = old_value
                    if is_qty:
                        display = formatter.fmt_qty(value) if value is not None else ""
                    else:
                        display = self._fmt_price(value) if value is not None else ""
                    error_msg = f"⚠ 输入「{text}」无效，已恢复原值"

            # 更新内存
            if col == self.COL_SELL:
                self.stocks[row]["upper"] = value
            elif col == self.COL_SELL_QTY:
                self.stocks[row]["sell_qty"] = value
            elif col == self.COL_BUY:
                self.stocks[row]["lower"] = value
            elif col == self.COL_BUY_QTY:
                self.stocks[row]["buy_qty"] = value

            # 更新显示（防重入）
            item.blockSignals(True)
            item.setText(display)
            item.blockSignals(False)

            # 重新计算告警（基于新配置）
            alerts = alerter.check_all(self._last_rows, self.stocks)
            self._last_alerts = alerts
            self._refresh_alert_columns(alerts)

            # 异步保存文件
            QTimer.singleShot(0, lambda: save_watchlist(self.stocks))

            if error_msg:
                self.status_label.setText(error_msg)
                self.status_label.setStyleSheet("color: #FF6666; font-size: 12px;")
                QTimer.singleShot(3000, self._restore_status_text)

        except Exception:
            self._editing = False
            self._editing_row = -1
            self._editing_col = -1

    def _restore_status_text(self):
        try:
            self.status_label.setStyleSheet("color: #AAAACC; font-size: 12px;")
            self.status_label.setText("")
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  刷新与定时器
    # ------------------------------------------------------------------ #

    def _start_auto_refresh(self):
        self._timer = QTimer(self)
        self._timer.setInterval(config.REFRESH_INTERVAL * 1000)
        self._timer.timeout.connect(self._do_fetch)
        self._timer.start()

        # 倒计时刷新器（每秒更新一次标签）
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._update_countdown)
        self._countdown_timer.start()

    def _update_countdown(self):
        """每秒更新「距下次刷新 Xs」标签"""
        try:
            if self._fetching:
                self.countdown_label.setText("获取中…")
                return
            remaining = self._timer.remainingTime()
            if remaining < 0:
                self.countdown_label.setText("")
                return
            secs = max(0, (remaining + 999) // 1000)   # 向上取整
            self.countdown_label.setText(f"下次刷新 {secs}s")
        except Exception:
            pass

    def _start_flash_timer(self):
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(500)
        self._flash_timer.timeout.connect(self._do_flash)
        self._flash_timer.start()

    def _do_flash(self):
        if not self._alerted_rows:
            return
        self._flash_state = not self._flash_state
        bg = self.COLOR_ALERT_A if self._flash_state else self.COLOR_ALERT_B
        for r_idx in self._alerted_rows:
            for c in self.FLASH_COLS:
                cell = self.table.item(r_idx, c)
                if cell:
                    cell.setBackground(bg)

    def _add_stock(self):
        try:
            raw = self.code_input.text().strip()
            if not raw:
                return
            code = raw.upper().replace("SH", "").replace("SZ", "").strip().zfill(6)
            if not code.isdigit() or len(code) != 6:
                QMessageBox.warning(self, "无效代码", f"「{raw}」不是有效的股票代码")
                return
            if any(s["code"] == code for s in self.stocks):
                QMessageBox.information(self, "已存在", f"股票 {code} 已在列表中")
                self.code_input.clear()
                return
            self.stocks.append({"code": code, "upper": None, "lower": None,
                                     "sell_qty": None, "buy_qty": None})
            self.codes = [s["code"] for s in self.stocks]
            save_watchlist(self.stocks)
            self.code_input.clear()
            self._update_status_bar()
            self._do_fetch()
        except Exception:
            pass

    def _delete_selected(self):
        try:
            rows = sorted([r.row() for r in self.table.selectionModel().selectedRows()], reverse=True)
            if not rows:
                QMessageBox.information(self, "提示", "请先点击要删除的行（可多选）")
                return
            for r in rows:
                if 0 <= r < len(self.stocks):
                    self.stocks.pop(r)
                    self.table.removeRow(r)
                    if r < len(self._last_rows):
                        self._last_rows.pop(r)
            self.codes = [s["code"] for s in self.stocks]
            save_watchlist(self.stocks)
            self._update_status_bar()
            self._do_fetch()
        except Exception:
            pass

    def _update_status_bar(self):
        try:
            self.statusBar().showMessage(
                f"监控 {len(self.codes)} 只股票  |  刷新间隔 {config.REFRESH_INTERVAL} 秒  |  输入代码后回车添加"
            )
        except Exception:
            pass

    def _do_fetch(self):
        # 编辑中不发起请求（避免数据回来触发 _populate_table 冲突）
        if self._editing or self._fetching or not self.codes:
            return
        self._fetching = True
        self.refresh_btn.setEnabled(False)
        # 脉冲模式：setRange(0,0) 让进度条显示无限滚动动画
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("正在获取行情…")
        self.progress_bar.show()
        self._fetch_thread = FetchThread(self.codes)
        self._fetch_thread.progress.connect(self._on_fetch_progress)
        self._fetch_thread.data_ready.connect(self._on_data_ready)
        self._fetch_thread.start()

    def _on_fetch_progress(self, percent: int, text: str):
        """接收 FetchThread 的阶段文字，脉冲模式下只更新文字和状态标签"""
        try:
            # 脉冲模式（range=0,0）下 setValue 无意义，只更新文字
            self.progress_bar.setFormat(f"  {text}")
            self.status_label.setText(text)
        except Exception:
            pass

    def _on_data_ready(self, df, error_msg):
        try:
            self._fetching = False
            self.refresh_btn.setEnabled(True)
            # 切回确定模式，闪一下 100% 再隐藏
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("  更新完成")
            QTimer.singleShot(1200, self.progress_bar.hide)
            now = datetime.now().strftime("%H:%M:%S")

            if error_msg:
                self._fail_count += 1
                self.status_label.setStyleSheet("color: #FFAA44; font-size: 12px;")
                if self._fail_count >= 3:
                    self._timer.stop()
                    self.status_label.setText(f"⚠ 连续失败{self._fail_count}次，已暂停自动刷新，请手动刷新  {now}")
                else:
                    self.status_label.setText(f"⚠ 更新失败（第{self._fail_count}次），显示缓存  {now}")
                self._populate_table(self._last_rows, self._last_alerts)
            else:
                self._fail_count = 0
                if not self._timer.isActive():
                    self._timer.start()
                self.status_label.setText(f"更新时间：{now}")
                self.status_label.setStyleSheet("color: #88CC88; font-size: 12px;")
                rows = df.to_dict("records") if not df.empty else []
                alerts = alerter.check_all(rows, self.stocks)
                self._last_rows = rows
                self._last_alerts = alerts
                # 编辑中则跳过表格重建
                if self._editing:
                    return
                self._populate_table(rows, alerts)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  表格绘制（仅在非编辑状态调用）
    # ------------------------------------------------------------------ #

    def _populate_table(self, rows, alerts):
        try:
            # 二次检查：编辑中绝不重建表格
            if self._editing:
                return

            self.table.itemChanged.disconnect(self._on_item_changed)
            self.table.setRowCount(len(rows))
            self._alerted_rows = {}

            for r_idx, row in enumerate(rows):
                code = str(row.get("代码", ""))
                alert_info = alerts.get(code, {})
                has_sell = alert_info.get("sell_hit", False)
                has_buy  = alert_info.get("buy_hit", False)
                has_alert = has_sell or has_buy

                if has_alert:
                    self._alerted_rows[r_idx] = (
                        "both" if has_sell and has_buy
                        else "sell" if has_sell else "buy"
                    )

                bg = self.COLOR_ALERT_A if has_alert else (
                    self.COLOR_ROW_ALT if r_idx % 2 else self.COLOR_BG
                )

                try:
                    pct = float(row.get("涨跌幅", 0))
                except (TypeError, ValueError):
                    pct = 0.0
                fg = self.COLOR_UP if pct > 0 else (self.COLOR_DOWN if pct < 0 else self.COLOR_FLAT)

                right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

                price_str = self._fmt_price(row.get("最新价"))
                pct_str   = f"{pct:+.2f}%"
                try:
                    raw_amt = float(row.get("涨跌额", 0))
                    amt_str = self._fmt_price(raw_amt)
                    if raw_amt >= 0:
                        amt_str = "+" + amt_str
                except (TypeError, ValueError):
                    amt_str = str(row.get("涨跌额", ""))

                cfg = next((s for s in self.stocks if s["code"] == code), {})
                upper_str   = self._fmt_price(cfg.get("upper"))  if cfg.get("upper")  is not None else ""
                sell_qty_str = formatter.fmt_qty(cfg.get("sell_qty")) if cfg.get("sell_qty") is not None else ""
                lower_str   = self._fmt_price(cfg.get("lower"))  if cfg.get("lower")  is not None else ""
                buy_qty_str  = formatter.fmt_qty(cfg.get("buy_qty"))  if cfg.get("buy_qty")  is not None else ""

                sell_alert_str = alert_info.get("sell", "")
                buy_alert_str  = alert_info.get("buy",  "")

                # ---- 写入只读列 ----
                def make_cell(text, align=Qt.AlignmentFlag.AlignCenter, fg_color=None, bold=False):
                    it = QTableWidgetItem(str(text) if text is not None else "")
                    it.setTextAlignment(align)
                    it.setBackground(bg)
                    if fg_color:
                        it.setForeground(fg_color)
                    if bold:
                        f = it.font()
                        f.setBold(True)
                        it.setFont(f)
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    return it

                def make_editable(text):
                    it = QTableWidgetItem(str(text) if text is not None else "")
                    it.setTextAlignment(right)
                    it.setBackground(self.COLOR_EDITABLE)
                    it.setForeground(QColor("#AAFFAA"))
                    it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
                    return it

                self.table.setItem(r_idx, self.COL_CODE,     make_cell(code))
                self.table.setItem(r_idx, self.COL_NAME,     make_cell(str(row.get("名称", ""))))
                self.table.setItem(r_idx, self.COL_PRICE,    make_cell(price_str, align=right, fg_color=fg, bold=True))
                self.table.setItem(r_idx, self.COL_PCT,     make_cell(pct_str,   align=right, fg_color=fg, bold=True))
                self.table.setItem(r_idx, self.COL_AMT,     make_cell(amt_str,   align=right, fg_color=fg))
                self.table.setItem(r_idx, self.COL_VOL,     make_cell(formatter.fmt_volume(row.get("成交量")),  align=right))
                self.table.setItem(r_idx, self.COL_TURNOVER, make_cell(formatter.fmt_amount(row.get("成交额")), align=right))
                self.table.setItem(r_idx, self.COL_SELL,     make_editable(upper_str))
                self.table.setItem(r_idx, self.COL_SELL_QTY, make_editable(sell_qty_str))
                self.table.setItem(r_idx, self.COL_BUY,      make_editable(lower_str))
                self.table.setItem(r_idx, self.COL_BUY_QTY,  make_editable(buy_qty_str))

                # 告警列
                sell_it = QTableWidgetItem(sell_alert_str)
                sell_it.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                sell_it.setBackground(bg)
                sell_it.setForeground(QColor("#FF9933") if sell_alert_str else QColor("#EEEEEE"))
                sell_it.setFlags(sell_it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r_idx, self.COL_SELL_ALT, sell_it)

                buy_it = QTableWidgetItem(buy_alert_str)
                buy_it.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                buy_it.setBackground(bg)
                buy_it.setForeground(QColor("#33FF99") if buy_alert_str else QColor("#EEEEEE"))
                buy_it.setFlags(buy_it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r_idx, self.COL_BUY_ALT, buy_it)

                self.table.setRowHeight(r_idx, 34)

            self.table.itemChanged.connect(self._on_item_changed)
        except Exception:
            try:
                self.table.itemChanged.connect(self._on_item_changed)
            except Exception:
                pass

    def _refresh_alert_columns(self, alerts):
        try:
            self._alerted_rows = {}
            for r_idx in range(self.table.rowCount()):
                code_item = self.table.item(r_idx, self.COL_CODE)
                if not code_item:
                    continue
                code = code_item.text()
                alert_info = alerts.get(code, {})
                has_sell = alert_info.get("sell_hit", False)
                has_buy  = alert_info.get("buy_hit", False)
                if has_sell or has_buy:
                    self._alerted_rows[r_idx] = "both" if has_sell and has_buy else "sell" if has_sell else "buy"

                sell_alert_str = alert_info.get("sell", "")
                buy_alert_str  = alert_info.get("buy",  "")

                sell_item = self.table.item(r_idx, self.COL_SELL_ALT)
                buy_item  = self.table.item(r_idx, self.COL_BUY_ALT)
                if sell_item:
                    sell_item.setText(sell_alert_str)
                    sell_item.setForeground(QColor("#FF9933") if sell_alert_str else QColor("#EEEEEE"))
                if buy_item:
                    buy_item.setText(buy_alert_str)
                    buy_item.setForeground(QColor("#33FF99") if buy_alert_str else QColor("#EEEEEE"))
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            save_watchlist(self.stocks)
        except Exception:
            pass
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = StockMonitor()
    window.show()
    sys.exit(app.exec())
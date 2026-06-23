# display.py - 渲染模块：使用 rich 绘制彩色行情表格

import pandas as pd
from rich.table import Table
from rich.text import Text
from rich import box

import formatter


def _format_price(price) -> Text:
    try:
        return Text(f"{float(price):.2f}")
    except (TypeError, ValueError):
        return Text(str(price))


def _format_change_pct(pct) -> Text:
    """涨跌幅：A股规范 涨红跌绿"""
    try:
        val = float(pct)
        text_str = f"{val:+.2f}%"
        if val > 0:
            return Text(text_str, style="bold red")
        elif val < 0:
            return Text(text_str, style="bold green")
        else:
            return Text(text_str)
    except (TypeError, ValueError):
        return Text(str(pct))


def _format_change_amt(amt) -> Text:
    try:
        val = float(amt)
        text_str = f"{val:+.2f}"
        if val > 0:
            return Text(text_str, style="red")
        elif val < 0:
            return Text(text_str, style="green")
        else:
            return Text(text_str)
    except (TypeError, ValueError):
        return Text(str(amt))


def build_table(
    df: pd.DataFrame,
    alerts: dict[str, list[str]],
    last_update: str,
    error_msg: str | None = None,
    stocks: list[dict] | None = None,
) -> Table:
    title = f"[bold]A股实时行情监控[/bold]  更新时间：{last_update}"
    if error_msg:
        title += f"\n[yellow]⚠ {error_msg}（显示缓存数据）[/yellow]"

    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        expand=False,
        padding=(0, 1),
    )

    table.add_column("股票代码", style="dim", width=10)
    table.add_column("名称", width=10)
    table.add_column("最新价", justify="right", width=10)
    table.add_column("涨跌幅", justify="right", width=10)
    table.add_column("涨跌额", justify="right", width=10)
    table.add_column("成交量", justify="right", width=12)
    table.add_column("成交额", justify="right", width=12)
    table.add_column("卖出价", justify="right", width=10)
    table.add_column("卖出数量", justify="right", width=12)
    table.add_column("买入价", justify="right", width=10)
    table.add_column("买入数量", justify="right", width=12)
    table.add_column("告警", width=28)

    if df.empty:
        table.add_row("—", "暂无数据", "—", "—", "—", "—", "—", "—", "—", "—", "—", "")
        return table

    for _, row in df.iterrows():
        code = str(row["代码"])
        row_alerts = alerts.get(code, [])
        has_alert = len(row_alerts) > 0
        row_style = "on dark_orange3" if has_alert else ""
        alert_text = Text(" | ".join(row_alerts), style="bold yellow") if has_alert else Text("")

        # 股票配置
        cfg = (stocks or {}).get(code, {}) if isinstance(stocks, dict) else {}
        if stocks and isinstance(stocks, list):
            cfg = next((s for s in stocks if s["code"] == code), {})
        upper = f"{cfg.get('upper'):.2f}" if cfg.get("upper") is not None else "-"
        sell_qty = formatter.fmt_qty(cfg.get("sell_qty")) or "-"
        lower = f"{cfg.get('lower'):.2f}" if cfg.get("lower") is not None else "-"
        buy_qty = formatter.fmt_qty(cfg.get("buy_qty")) or "-"

        table.add_row(
            code,
            str(row["名称"]),
            _format_price(row["最新价"]),
            _format_change_pct(row["涨跌幅"]),
            _format_change_amt(row["涨跌额"]),
            formatter.fmt_volume(row["成交量"]),
            formatter.fmt_amount(row["成交额"]),
            upper,
            sell_qty,
            lower,
            buy_qty,
            alert_text,
            style=row_style,
        )

    return table

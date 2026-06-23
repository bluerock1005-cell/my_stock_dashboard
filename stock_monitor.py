# stock_monitor.py - 主程序入口

import time
import json
from pathlib import Path
from datetime import datetime

from rich.live import Live
from rich.console import Console

import config
import fetcher
import alerter
import display

WATCHLIST_FILE = Path(__file__).parent / "watchlist.json"


def load_stocks() -> list[dict]:
    if WATCHLIST_FILE.exists():
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data and isinstance(data[0], str):
                return [{"code": c, "upper": None, "lower": None, "sell_qty": None, "buy_qty": None} for c in data]
            for item in data:
                item.setdefault("sell_qty", None)
                item.setdefault("buy_qty", None)
            return data
        except Exception:
            pass
    return list(config.STOCKS)


def main():
    console = Console()
    stocks = load_stocks()
    codes = [s["code"] for s in stocks]

    console.print(
        f"\n[bold cyan]A股实时行情监控[/bold cyan]  "
        f"监控股票：{len(codes)} 只  "
        f"刷新间隔：{config.REFRESH_INTERVAL} 秒\n"
        f"按 [bold]Ctrl+C[/bold] 退出\n"
    )

    # 首次获取数据
    df, error_msg = fetcher.fetch_stocks(codes)
    rows = df.to_dict("records")
    alerts = alerter.check_all(rows, stocks)
    last_update = datetime.now().strftime("%H:%M:%S")
    table = display.build_table(df, alerts, last_update, error_msg, stocks)

    try:
        with Live(table, console=console, refresh_per_second=1, screen=False) as live:
            while True:
                time.sleep(config.REFRESH_INTERVAL)

                df, error_msg = fetcher.fetch_stocks(codes)
                rows = df.to_dict("records")
                alerts = alerter.check_all(rows, stocks)
                last_update = datetime.now().strftime("%H:%M:%S")
                table = display.build_table(df, alerts, last_update, error_msg, stocks)
                live.update(table)

    except KeyboardInterrupt:
        console.print("\n[bold green]✓ 监控已停止，再见！[/bold green]\n")


if __name__ == "__main__":
    main()

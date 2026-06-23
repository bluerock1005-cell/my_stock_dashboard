# alerter.py - 价格告警模块：检测股票价格是否触发阈值

# alerter.py

def check_all(rows, stock_configs):

    config_map = {s["code"]: s for s in stock_configs}

    result = {}

    for row in rows:

        code = str(row.get("代码", ""))

        price = row.get("最新价")

        sell_hit = False
        buy_hit = False

        sell_text = ""
        buy_text = ""

        if code in config_map and isinstance(price, (int, float)):

            cfg = config_map[code]

            upper = cfg.get("upper")

            lower = cfg.get("lower")

            # 卖出
            if upper is not None:

                if price >= upper:

                    sell_hit = True

                    sell_text = "⚠ 已达卖出价"

                else:

                    diff = (upper / price - 1) * 100

                    sell_text = f"📈 距卖出 {diff:.2f}%"

            # 买入
            if lower is not None:

                if price <= lower:

                    buy_hit = True

                    buy_text = "⚠ 已达买入价"

                else:

                    diff = (price / lower - 1) * 100

                    buy_text = f"📉 距买入 {diff:.2f}%"

        result[code] = {

            "sell": sell_text,

            "buy": buy_text,

            "sell_hit": sell_hit,

            "buy_hit": buy_hit,

        }

    return result
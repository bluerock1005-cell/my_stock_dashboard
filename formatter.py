# formatter.py - 共用格式化函数，供 gui.py 和 display.py 调用

def fmt_volume(vol) -> str:
    try:
        v = float(vol)
        return f"{v / 10000:.2f}万手" if v >= 10000 else f"{v:.0f}手"
    except (TypeError, ValueError):
        return str(vol)


def fmt_amount(amt) -> str:
    try:
        v = float(amt)
        if v >= 1e8:
            return f"{v / 1e8:.2f}亿"
        if v >= 1e4:
            return f"{v / 1e4:.2f}万"
        return f"{v:.0f}"
    except (TypeError, ValueError):
        return str(amt)


def fmt_qty(qty) -> str:
    """格式化数量：无小数点，千分位分隔"""
    try:
        v = int(float(qty))
        return f"{v:,}"
    except (TypeError, ValueError):
        return ""
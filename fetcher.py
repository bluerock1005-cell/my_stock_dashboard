# fetcher.py - 行情数据拉取模块（使用 akshare，支持个股和ETF）

import akshare as ak
import pandas as pd

# ETF 代码规律：深市 15xxxx，沪市 51xxxx、58xxxx
def _is_etf(code: str) -> bool:
    return code.startswith("15") or code.startswith("51") or code.startswith("58")


def _fetch_with_retry(fn) -> tuple[pd.DataFrame, str]:
    for attempt in range(3):
        try:
            return fn(), ""
        except Exception as e:
            if attempt == 2:
                return pd.DataFrame(), str(e)
    return pd.DataFrame(), "未知错误"


def fetch_stocks(codes: list[str]) -> tuple[pd.DataFrame, str]:
    """保留旧接口兼容"""
    return _fetch_impl(codes, progress_cb=None)


def fetch_stocks_with_progress(codes: list[str], progress_cb) -> tuple[pd.DataFrame, str]:
    """
    拉取实时行情，每完成一个 API 批次就回调 progress_cb(percent, status_text)。
    progress_cb 签名: (int, str)
    """
    return _fetch_impl(codes, progress_cb=progress_cb)


def _fetch_impl(codes: list[str], progress_cb=None) -> tuple[pd.DataFrame, str]:
    """
    拉取实时行情，自动区分个股和ETF，两类接口并发请求。
    progress_cb: 可选回调 (int percent, str text)
    """
    if not codes:
        return pd.DataFrame(), ""

    from concurrent.futures import ThreadPoolExecutor

    padded = [c.zfill(6) for c in codes]
    etf_codes   = [c for c in padded if _is_etf(c)]
    stock_codes = [c for c in padded if not _is_etf(c)]

    need_stock = bool(stock_codes)
    need_etf   = bool(etf_codes)

    if progress_cb:
        parts = []
        if need_stock:
            parts.append(f"{len(stock_codes)} 只个股")
        if need_etf:
            parts.append(f"{len(etf_codes)} 只ETF")
        progress_cb(0, "正在并发获取" + "、".join(parts) + "行情…")

    frames = []
    errors = []

    # ---------- 并发提交两个接口 ----------
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_stock = executor.submit(_fetch_with_retry, ak.stock_zh_a_spot_em) if need_stock else None
        future_etf   = executor.submit(_fetch_with_retry, ak.fund_etf_spot_em)   if need_etf   else None
    # with 块退出时两个任务已全部完成

    # ---------- 处理个股结果 ----------
    if future_stock is not None:
        df, err = future_stock.result()
        if err:
            errors.append(f"个股接口失败: {err}")
        else:
            hit = df[df["代码"].isin(stock_codes)].copy()
            missing = set(stock_codes) - set(hit["代码"])
            if missing:
                errors.append("未找到个股：" + "、".join(sorted(missing)))
            frames.append(hit)

    # ---------- 处理ETF结果 ----------
    if future_etf is not None:
        df, err = future_etf.result()
        if err:
            errors.append(f"ETF接口失败: {err}")
        else:
            hit = df[df["代码"].isin(etf_codes)].copy()
            missing = set(etf_codes) - set(hit["代码"])
            if missing:
                errors.append("未找到ETF：" + "、".join(sorted(missing)))
            frames.append(hit)

    if progress_cb:
        progress_cb(90, "正在整理数据…")

    if not frames:
        if progress_cb:
            progress_cb(100, "无数据")
        return pd.DataFrame(), "；".join(errors)

    # 只保留两个接口共有的列
    COMMON_COLS = ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "成交量", "成交额"]
    result = pd.concat(
        [f[COMMON_COLS] for f in frames if not f.empty],
        ignore_index=True
    )

    # 按输入顺序排列
    order = {c: i for i, c in enumerate(padded)}
    result = result.sort_values("代码", key=lambda s: s.map(order)).reset_index(drop=True)

    if progress_cb:
        progress_cb(100, "更新完成")

    return result, "；".join(errors)
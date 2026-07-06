# A股实时行情监控

这是一个基于 Python 的 A 股实时行情监控工具，支持命令行实时表格展示和 PyQt6 图形界面监控。

## 主要功能

- 实时拉取个股和 ETF 行情
- 支持 `watchlist.json` 自定义监控列表
- 支持价格阈值提醒：买入价、卖出价
- 支持买入/卖出数量和备注记录
- 文本终端展示和 GUI 双模式支持
- 支持 PyInstaller 打包成独立可执行文件

## 依赖

- Python 3.10+
- `akshare`
- `rich`
- `pandas`
- `PyQt6`

安装依赖：

```bash
pip install -r requirements.txt
```

## 运行方式

### 命令行模式

```bash
python stock_monitor.py
```

### 图形界面模式

```bash
python gui.py
```

## 配置说明

项目通过 `config.py` 配置刷新间隔和默认股票列表：

- `REFRESH_INTERVAL`：刷新间隔（秒）
- `STOCKS`：默认监控股票列表，当 `watchlist.json` 不存在时使用

示例：

```python
REFRESH_INTERVAL = 10
STOCKS = []
```

## watchlist.json 格式

`watchlist.json` 支持两种格式：

1. 仅股票代码数组：

```json
["000001", "510300"]
```

2. 含阈值和备注的对象数组：

```json
[
  {
    "code": "159938",
    "upper": 0.731,
    "lower": 0.55,
    "sell_qty": 18000,
    "buy_qty": 9100,
    "sort_order": 1,
    "note": null
  }
]
```

字段说明：

- `code`：股票或 ETF 代码
- `upper`：卖出价格阈值
- `lower`：买入价格阈值
- `sell_qty`：卖出数量
- `buy_qty`：买入数量
- `sort_order`：排序顺序
- `note`：备注

## 打包说明

如果需要生成独立可执行文件，可使用 PyInstaller：

```bash
pyinstaller stock_monitor_gui.spec
```

生成结果会出现在 `dist/` 或 `build/` 目录中。

## 目录说明

- `stock_monitor.py`：命令行实时监控入口
- `gui.py`：图形界面监控入口
- `fetcher.py`：行情数据拉取模块
- `display.py`：终端表格展示模块
- `alerter.py`：买卖价告警模块
- `formatter.py`：格式化展示辅助函数
- `config.py`：基本配置
- `watchlist.json`：监控股票列表和阈值配置
- `requirements.txt`：依赖列表
- `stock_monitor_gui.spec`：PyInstaller 打包配置

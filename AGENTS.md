# CLAUDE.md

项目是个人使用的 A 股实时行情监控与告警桌面工具，使用 Python + PyQt6 实现 Windows GUI。

## 运行

```bash
python gui.py              # GUI 模式（主要入口）
python stock_monitor.py    # 命令行模式（rich 终端表格）
```

## 打包

用系统 Python 3.13（`C:\Users\chong elaine\AppData\Local\Programs\Python\Python313\python.exe`），虚拟环境 `.venv` 用于 IDE 代码提示，但打包必须在系统 Python 上执行（`.venv` 的 pip 已损坏）。

```bash
python -m PyInstaller stock_monitor_gui.spec --noconfirm
```

输出到 `dist/股票监控/`，双击 `股票监控.exe` 或项目根目录的 `股票监控.lnk` 快捷方式启动。dist 目录被占用时需先关掉 exe 再打包。

## 文件职责

| 文件 | 作用 |
|------|------|
| `gui.py` | PyQt6 主界面：表格、进度条、编辑、闪动告警、线程调度 |
| `fetcher.py` | 行情拉取：akshare 并发请求个股+ETF，含超时重试 + 日志 |
| `alerter.py` | 价格告警：比对最新价与用户设定的买卖阈值 |
| `formatter.py` | 格式化：成交量/成交额/数量转中文友好显示 |
| `display.py` | 命令行模式：rich 表格渲染（GUI 不用） |
| `config.py` | 刷新间隔 + 默认股票列表 |
| `stock_monitor.py` | 命令行入口：Live 循环刷新 rich 表格 |
| `watchlist.json` | 监控列表持久化文件（exe 同目录） |
| `requirements.txt` | pip 依赖声明 |
| `stock_monitor_gui.spec` | PyInstaller 打包配置 |

## 关键架构约定

### GUI 编辑保护
`_editing` 标志位：用户双击单元格进入编辑时设 True，阻止表格重建和网络请求，编辑完成后释放。这是唯一锁机制，不用队列。

### 表达式求值
`gui.py` 内置安全 AST 解析器 `safe_eval()`，仅支持 `+-*/%**` 和数字，用户输入 `500/2` 或 `=500/2` 自动计算价格，`buy/sell_qty` 列取整。

### watchlist.json 格式
对象数组，每项含 `code`、`upper`、`lower`、`sell_qty`、`buy_qty`、`sort_order`、`note`。首次运行自动补齐缺失字段。

### 行情拉取
`fetcher._fetch_impl` 用 `ThreadPoolExecutor(max_workers=2)` 并发请求 `ak.stock_zh_a_spot_em`（个股）和 `ak.fund_etf_spot_em`（ETF），`_fetch_with_retry` 再套一层超时线程（30s），最多重试 3 次。ETF 代码规律：深市 15xxxx，沪市 51xxxx/58xxxx。

### 打包环境
- `console=False`：不显示控制台窗口
- 日志写入 exe 同目录的 `fetcher.log`
- `TQDM_DISABLE=1` 环境变量屏蔽 akshare 内部进度条
- 关键 hidden imports：`akshare`、`PyQt6`、`curl_cffi`、`lxml`、`certifi`、pandas C 扩展

## 依赖

```
akshare>=1.12.0
rich>=13.0.0
pandas>=2.0.0
PyQt6>=6.5.0
```

打包额外需要：`pyinstaller`。

## 当前状态

全 ETF 监控列表（14只），无个股。程序通过 `股票监控.lnk` 快捷方式启动，后台 10 秒轮询一次行情。14 只 ETF 全部为 AI 及港股互联网相关 ETF。

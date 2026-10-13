# 校园网自动登录 · NetworkAuth

![icon](resources/app.png)

> **⚠️ 测试阶段 / Beta Notice**
>
> 本项目**功能尚不完善，目前处于个人测试状态**，尚未经过大规模兼容验证。
> 已在本校 Dr.COM（EPortal）认证门户上实测通过，但不保证在其他校园网络环境可用。
>
> This project is **work-in-progress and under testing**. It has only been verified against the author's campus Dr.COM (EPortal) authentication portal. It is **not guaranteed** to work on other campus networks.

一款 Windows 桌面常驻工具，自动完成校园网（Dr.COM EPortal 门户）认证。连接校园 Wi-Fi / 有线网后无需再打开浏览器输入账号密码：程序在后台检测网络状态，未认证时自动登录，掉线时自动重连。

A Windows desktop resident tool that automatically completes campus network (Dr.COM EPortal portal) authentication. Once connected to the campus Wi-Fi / wired network, no more opening a browser and typing credentials: the app detects the network status in the background, logs in automatically when unauthenticated, and reconnects when dropped.

---

## 功能特性 / Features

- **首次认证，自动保存**：输入学号、密码、选择服务类型，认证成功后自动加密保存账号密码，下次免输入。
  **First login, auto-saved**: enter your student ID, password and carrier type; after a successful auth the credentials are encrypted and saved for next time.
- **按网络匹配账号**：默认一套全局账号，也可为每个 Wi-Fi SSID / 有线网络单独绑定账号，优先匹配当前网络。
  **Per-network accounts**: a global default account plus optional per-network (SSID / ethernet) bindings, resolved by the current network first.
- **后台守护**：开机自启 + 系统托盘常驻；自动检测认证状态并登录；掉线按指数退避重试；账号异常（密码错误等）时停止自动重试，防止锁号。
  **Background daemon**: auto-start on boot + system tray resident; detects and performs login automatically; exponential-backoff retry on disconnect; stops retrying on credential errors to avoid account lockout.
- **状态反馈**：Windows 通知提示登录成功 / 失败；内置日志页展示每次请求与响应（已脱敏）并支持一键复制诊断。
  **Status feedback**: Windows toast notifications for success / failure; a built-in log page with masked request/response details and one-click copy for diagnostics.
- **浅色卡片 UI**：PyQt6 卡片分层界面，图标化状态徽标、下次检测倒计时、按钮四态；支持拖拽标题栏、最小化到托盘、单实例运行、`--minimized` 静默启动。
  **Light card UI**: PyQt6 card-layered interface with iconographic status badges, next-check countdown and four-state buttons; draggable title bar, minimize-to-tray, single-instance guard and `--minimized` silent startup.
- **可诊断**：运行日志写入 `%APPDATA%\NetworkAuth\app.log`（轮转，最多 3 MB），未捕获异常不再静默；配置损坏会自动留档并从备份恢复。
  **Diagnosable**: runtime log at `%APPDATA%\NetworkAuth\app.log` (rotating, ≤3 MB); uncaught exceptions are no longer silent; a corrupt config is quarantined and restored from backup.

## 项目状态 / Project Status

| 状态 / Status | 说明 / Note |
| --- | --- |
| 认证协议 | 已适配 Dr.COM EPortal（本校正版门户），2026-10 实测通过 |
| 兼容性 | 仅在本校门户验证，其他学校/网络需自行测试或适配 |
| 已知缺口 | 注销端点尚未真机实测；未包含自动化测试与 CI |
| 定位 | 个人测试项目，功能持续打磨中 |

| State | Note |
| --- | --- |
| Auth protocol | Dr.COM EPortal (official campus portal), verified 2026-10 |
| Compatibility | Verified on the author's campus portal only |
| Known gaps | The logout endpoint is not verified on real hardware yet; no automated tests / CI |
| Position | Personal testing project, features still being polished |

## 环境要求 / Requirements

- Windows 10 / 11
- Python 3.12+（仅源码运行需要 / only needed for running from source）

## 快速开始 / Quick Start

### 方式一：直接运行打包好的 exe / Option A: run the packaged exe

打开 `dist/校园网自动登录.exe`（注：`dist/` 为本地构建产物，未提交到 git）：

1. 首次启动会最小化到系统托盘。
2. 左键点击托盘图标或选择「打开主界面」。
3. 在主界面选择当前网络，输入学号、密码、选择服务类型。
4. 点击「登录」，认证成功后自动记住该账号。
5. 以后连接该网络，程序会自动完成认证。

1. It starts minimized to the system tray.
2. Left-click the tray icon or choose "Open main window".
3. Select the current network, enter your student ID / password / carrier.
4. Click "Login"; on success the account is remembered automatically.
5. Next time you join the same network, authentication happens automatically.

### 方式二：源码运行 / Option B: run from source

```powershell
# 安装依赖 / install dependencies
pip install -r requirements.txt

# 运行 / run
python main.py

# 开机静默启动（用于注册表自启）/ silent startup (for auto-start)
python main.py --minimized
```

## 打包 / Build

```powershell
# 构建依赖（PyInstaller）单独放在 requirements-dev.txt
pip install -r requirements-dev.txt

pyinstaller NetworkAuth.spec --clean -y
```

打包后的单文件 exe 位于 `dist/校园网自动登录.exe`。
The single-file exe is output to `dist/校园网自动登录.exe`.

> 覆盖 `dist` 内的旧 exe 前请先退出正在运行的程序，否则文件被占用会写入失败。
> Quit the running app before overwriting the exe in `dist`, otherwise the file is locked.

## 设置项 / Settings

在「设置」中可开关 / Available in the Settings dialog:

- 开机自启（写入注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`，无需管理员权限）
  Auto-start on boot (registry `HKCU\...\Run`, no admin required)
- 关闭窗口时最小化到托盘 / Minimize to tray on window close
- 检测到未认证时自动登录 / Auto-login when unauthenticated
- 掉线/被踢下线时自动重连 / Auto-reconnect when dropped
- Windows 通知 / Windows notifications
- 未认证时的检测间隔（10/15/30/60 秒）/ Detection interval when unauthenticated
- 已在线时的检测间隔（30/60/120/300 秒）/ Detection interval when online
- 认证门户地址 / Portal base URL
- 删除已保存的网络账号绑定 / Delete saved network bindings

> 「关闭窗口时最小化到托盘」关闭后，点击关闭按钮或按 Alt+F4 会**直接退出程序**（而不是隐藏窗口）。
> With "minimize to tray on close" turned off, the close button / Alt+F4 **quits the app** instead of hiding it.

> 门户登录固定使用 **GET**：该门户对 POST 返回「无法获取用户认证账号」，因此不再提供请求方式选项。
> Portal login always uses **GET**: the portal rejects POST with "无法获取用户认证账号", so there is no request-method option.

## 隐私与安全 / Privacy & Security

- 密码使用 Windows DPAPI 加密后保存在 `%APPDATA%\NetworkAuth\config.json`，仅当前 Windows 用户可解密；非 Windows 平台退化为可逆混淆，仅供开发调试。
  Passwords are encrypted with Windows DPAPI and stored in `%APPDATA%\NetworkAuth\config.json`, decryptable only by the current Windows user; on non-Windows platforms it falls back to reversible obfuscation for development only.
- 日志与界面展示对学号中间四位打码，请求/响应片段已脱敏，不会泄露密码。
  Usernames are masked in logs and UI; request/response snippets are sanitized.
- 所有认证请求仅在本地与校园网门户之间进行。
  All auth requests stay local, between your machine and the campus portal.

## 认证协议 / Authentication Protocol

适配新版 EPortal（Dr.COM 门户内核，nginx + PHP 前端） / Targets the new EPortal (Dr.COM portal core, nginx + PHP front-end):

- **配置发现 / Config discovery**：启动时调用 `http://<portal>:801/eportal/portal/page/loadConfig`，获取 `program_index`、`page_index`、`login_method`、`en_md5` 等参数；失败时回退实测默认值。
- **登录接口 / Login (GET)**：`http://<portal>:801/eportal/portal/login`
  - 账号 / account：`user_account = 学号 + 服务后缀`
  - 密码 / password：`user_password`（`en_md5=0` 时明文）
  - 附带 / plus：`wlan_user_ip`、`wlan_user_mac`、`login_method`、`program_name`、`page_index`、`jsVersion`
- **返回 / Response**：JSONP `jsonpReturn({"result":..,"msg":"..","ret_code":".."})`
  - `result=1`：登录成功 / success
  - `ret_code=2` 且 msg 含「已经在线」：该 IP 已认证 / already online
- **服务后缀 / Carrier suffixes**：校园用户（空）、校园电信（`@dx`）、校园联通（`@lt`）、校园其他（空）
- 门户首页仍保留旧版配置 `authloginpath=/eportal/?c=ACSetting&a=Login`（字段 `DDDDD`/`upass`），但该地址现在只返回门户 SPA 页面，**旧 ACSetting 协议已失效**，本工具不再使用。

> 旧版 ACSetting 协议在新门户上已失效，本工具使用新版 EPortal 接口。
> The legacy ACSetting protocol is dead on the new portal; this tool uses the new EPortal endpoints.

## 项目结构 / Project Structure

```
.
├── main.py                     # 程序入口 / entry point
├── NetworkAuth.spec            # PyInstaller 打包配置 / build config
├── requirements.txt            # 运行依赖 / runtime dependencies
├── requirements-dev.txt        # 构建依赖 / build dependencies
├── README.md                   # 本文件 / this file
├── resources/
│   ├── app.png                 # 应用图标 / app icon (256×256)
│   └── app.ico                 # exe 图标 / exe icon
├── core/                       # 核心逻辑 / core logic
│   ├── portal.py               # 门户协议发现与登录/注销 / portal protocol
│   ├── network.py              # 网络识别与连通性探测（带 TTL 缓存）
│   ├── credential.py           # DPAPI 加解密 / DPAPI encryption
│   ├── config.py               # 配置持久化、备份恢复 / config persistence
│   ├── daemon.py               # 守护线程 / daemon thread
│   ├── logging_setup.py        # 文件日志与全局异常捕获 / logging & crash capture
│   └── autostart.py            # 开机自启注册表 / auto-start registry
└── app/                        # UI 层 / UI layer
    ├── theme.py                # 设计令牌 + 全局 QSS / design tokens & QSS
    ├── widgets.py              # 自定义控件 / custom widgets
    ├── icons.py                # 运行时绘制图标与状态徽标 / runtime-drawn icons
    ├── main_window.py          # 主窗口 / main window
    ├── tray.py                 # 系统托盘 / system tray
    ├── settings_dialog.py      # 设置页 / settings dialog
    └── log_dialog.py           # 日志页 / log dialog
```

## 诊断 / Diagnostics

- 运行日志：`%APPDATA%\NetworkAuth\app.log`（1 MB × 3 份轮转，出错先看这里）
- 配置与凭据：`%APPDATA%\NetworkAuth\config.json`（密码为 DPAPI 密文；同级 `.bak` 为上一份可用配置）
- 界面内诊断：「日志」页可按成功/失败筛选，选中记录后可查看脱敏的请求行与响应片段，并支持「复制诊断」。
- Runtime log: `%APPDATA%\NetworkAuth\app.log` (rotating, 1 MB × 3)
- Config & credentials: `%APPDATA%\NetworkAuth\config.json` (DPAPI-encrypted password; `.bak` is the last good copy)

## 更新记录 / Changelog

### 1.1.0 — 2026-10-13

**新增 / Added**

- 文件日志与崩溃捕获：运行日志写入 `%APPDATA%\NetworkAuth\app.log`（1 MB × 3 份轮转）；未捕获异常会落盘并通过托盘通知提示，不再静默消失。
- 配置损坏自愈：`config.json` 无法解析时自动留档为 `config.json.broken-<时间戳>`，并尝试从上一份可用备份 `config.json.bak` 恢复，避免历史记录被清空。
- 日志弹窗新增「复制诊断」按钮，可一键复制选中记录的脱敏请求与响应。
- 状态卡新增图标化状态徽标（对勾 / 时钟 / 感叹号 / 断电）与「下次检测倒计时」。
- 托盘菜单顶部显示当前状态，并按状态置灰无意义的项（已在线时禁用「立即登录」）。
- 设置项新增「已在线时的间隔」，可单独调节已认证状态的检测频率（30/60/120/300 秒）。

**修复 / Fixed**

- **单实例失效**：并发启动会出现两个实例同时驻留托盘。改为内核命名互斥体判定，并用 `QLocalSocket` 重试唤醒已有窗口。
- **日志详情错位**：日志页按「成功/失败」筛选后，点任意一行显示的都是别的记录。现在表格行与记录严格一一对应。
- **服务类型被重置**：门户配置每次刷新都会把「服务类型」改回「校园用户」，现在会保留用户选择。
- **界面卡顿**：打开窗口、点「刷新」会在界面线程同步执行 `netsh` / `ipconfig`，卡住约 0.2~0.3 秒。改为网络探测下沉到守护线程并加 5 秒 TTL 缓存，界面只读缓存（实测 0.9 ms）。
- **「关闭窗口时最小化到托盘」不生效**：关闭窗口始终只是隐藏。现在按设置决定「最小化到托盘」或「退出程序」，Alt+F4 / 任务栏关闭也走同一策略；标题栏「最小化」与「关闭」行为分离。
- **注销请求不带账号**：改为主送 `user_account` / `user_password`，并写入日志便于核对。
- **登录后固定阻塞 2.5 秒**：守护线程在这段时间无法处理注销 / 手动登录请求。改为最长 3 秒的可打断轮询，实测约 0.7 秒即可确认。
- **回车无法提交**：学号 / 密码框回车现在直接登录。
- **开机自启写入失败无感知**：设置页与托盘都按注册表实际结果显示，失败时提示原因并回滚勾选。
- **凭据解密异常**：配置被外部修改或更换 Windows 用户时不再抛异常到界面，降级为空密码处理。
- 首次显示窗口不居中、唤醒连接的 socket 未释放、自定义控件的 QSS 边框未绘制、设置页在小屏上底部按钮被挤出屏幕（改为自适应高度 + 内容滚动）。

**变更 / Changed**

- 界面视觉改版：统一为浅色卡片分层（页面底色 + 白色卡片 + 浅灰填充块），重做配色与层次、更紧凑的表单、图标化状态；按钮补齐悬停 / 按下 / 禁用 / 加载四态，开关与分段选择带 180 ms 缓动。
- 主窗口与设置页、日志页风格完全统一（无边框、同色系、同圆角、同间距）。
- 网络识别结果由守护线程通过 `networkChanged` 信号回传，界面不再自行探测。
- 托盘控制器由 `QWidget` 改为 `QObject`；依赖拆分为运行依赖与构建依赖。

**移除 / Removed**

- 移除「请求方式 GET / POST」设置项：该门户登录必须使用 GET，保留开关会误导用户。
- 移除窗体阴影与半透明背景（曾导致整窗透明且鼠标点击穿透）。
- 清理无引用的工具函数（`rounded_path` / `divider_pen` / `heading_font`）与死代码 `network.local_ip()`。

**待验证 / Pending verification**

- 注销端点 `GET /eportal/portal/logout` 尚未真机实测（实测会断开当前网络）。失败时日志会记录门户返回，请以门户页面注销结果为准。

## 免责声明 / Disclaimer

本工具仅用于简化个人校园网认证流程，请遵守所在学校/组织的网络使用规定。因错误填写账号密码导致的账号锁定、因网络策略变更导致的认证失败等情况，作者不承担责任。

This tool is provided only to simplify personal campus-network authentication. Please comply with your school's / organization's network usage policies. The author is not responsible for account lockouts caused by incorrect credentials, authentication failures caused by network policy changes, or any other consequences.

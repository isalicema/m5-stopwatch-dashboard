# M5 StopWatch：TickTick 专注 + AI Dashboard

这是 Alice 的 M5Stack StopWatch 圆屏工作台：

- TickTick 专注：A 键控制正计时，B 键控制 25 分钟倒计时。
- Codex：显示活动、等待、错误、额度窗口和 Token 用量。
- Claude：显示活动、额度窗口和 Token 用量。
- AI 热点尖叫：筛选官方 AI 新闻源，新热点到达时切页提示，并使用扬声器与振动马达提醒。
- Obsidian 掷骰子：从明确授权的 Markdown 根目录随机抽一篇笔记并在 Obsidian 中打开。
- 时钟总览：时间、日期、天气、电量、TickTick 专注进度，以及当天全部 Coding AI 的
  Token 总处理量。

公开示例默认不展示 Codex/Claude 任务标题和对话。实时对话预览必须由本人显式开启，
且只读取可见的用户/助手文本，不转发推理、工具输入或工具结果。

## 数据路径

StopWatch 默认通过物理 USB CDC 访问本机 Dashboard 桥接，也可选择带 Token 的局域网
HTTP。Dashboard
再复用已经由 Stick S3 项目验证过的 TickTick 专注服务，以及本机 Multi AI Usage Monitor：

```text
StopWatch A/B 按键
  -> M5 Dashboard bridge (:8765)
  -> TickTick focus bridge (:8787)
  -> TickTick macOS 界面

api-usage-board (:8177)
  -> M5 Dashboard bridge (:8765)
  -> StopWatch 首屏今日 AI 总处理量
```

两个桥接都只应监听可信本机或局域网，不要把端口映射到公网。

## 1. 准备 TickTick 专注服务

本项目默认连接 `http://127.0.0.1:8787`，复用同一工作区中的
`m5stick-ticktick-focus/mac-bridge/focus_bridge.py`。该服务提供：

- `GET /focus/state`、`POST /focus/click`、`POST /focus/double-click`
- `GET /pomo/state`、`POST /pomo/start|pause|resume|end`

若专注服务设置了令牌，把相同值写入 `config.json` 的 `ticktick.token`。倒计时默认
`duration_seconds: 1500`。

## 2. 启动 Dashboard 桥接

手动运行时，复制示例配置并设置一个至少 16 位的 URL-safe 随机 `server.api_token`：

```bash
cp config.example.json config.json
python3 -m bridge --config config.json
```

另开终端检查：

```bash
python3 scripts/check.py --token 'YOUR_DASHBOARD_TOKEN'
```

看到 `TickTick: connected=True` 说明专注服务已经接通。离线时先确认 8787 服务正在运行，
再检查 `ticktick.base_url` 和 `ticktick.token`。

首屏 AI 用量默认读取 `http://127.0.0.1:8177/api/token-series?days=1&metric=total`。
来源是 `api-usage-board` 已归一化的 Claude Code、Codex、Kimi Code、DeepSeek、OpenRouter
和 Grok；Cursor 与 Antigravity 目前没有 Token 序列，因此不进入总量。首屏采用
`today.total`，即 input + output + cache read + cache write 的总处理量，同时 Bridge 保留
`today.auth`（不含 cache）和各 Provider 明细。来源不完整时首屏显示 `AI--`，不会把部分
数据冒充完整总量；Grok 当天有数据时因其日志是近似口径，数值前显示 `~`。
当前跨 Provider 没有共同 request id；若同一次请求同时被客户端本地日志和 OpenRouter
analytics 记录，需要在 `api-usage-board` 侧排除重复渠道，手表端不会猜测去重。

示例配置已包含 `ai_hotspot` 与 `obsidian`。AI 热点由三路数据汇聚：Codex Resets 的确认
重置与预测、AIHOT 精选的 snapshot/changes 增量、OpenAI/Google 等官方 RSS，以及
DeepSeek/Kimi 官网、官方社交账号和官方模型组织的原文链接。DeepSeek、Kimi、Moonshot
与“多模态/视觉模型”属于永久关注词；即使本机仍使用较旧的私人配置，也会合并进入判断。
每路首次
只建立基线，不会把历史内容当成新警报；后续统一去重、检查时效并按本地透明规则分为
`scream / alert / inbox`。只有 `scream` 会触发当前固件的自动切页、声音和震动。

AIHOT 首次同步使用完整 snapshot 的 `cursor`，之后逐页应用 changes，再保存返回的新
`cursor`；遇到 `409 snapshot_required` 会重建基线。所有 HTTP 信源使用 `ETag`，限流时
遵守 `Retry-After`。Codex Reset 的 `active_watch` 是预测，不会被呈现成已经确认重置；
只有新的 `latest_reset.id` 无条件尖叫。

Obsidian 默认只扫描 `~/Smart Workspace` 下的 Markdown，并硬排除 `Alice Writing`、
隐藏目录、`.obsidian`、`.trash`、`.git` 和 `node_modules`；`lucky: true` 不能越过这些
边界。如需增加其他 Vault，必须在 `obsidian.roots` 中显式授权。

幸运笔记采用两级权重：先选“核心洞察”或“灵感探索”池，再按该池内的目录权重选目录，
最后优先从较久未出现的一半笔记中随机。核心池权重为 4，灵感池为 1；`rabbitT dream`
与 `Codex Report` 位于灵感池，目录权重分别只有 0.35 和 0.25。最近 30 次抽取会写入
`obsidian.state_path` 并跨 Bridge 重启冷却，避免反复遇到同一篇。单篇 frontmatter 可用
`lucky: false` 排除，或用 `lucky: true` 把非默认目录中的非私密笔记加入“手动精选”。
`RabbitT Creation` 默认不抽，但允许用后一种方式逐篇加入。设备只收到标题、相对文件夹、
所属池与入选原因，不传正文摘录或 Vault 绝对路径。

## 3. 安装 Codex Hook 与常驻服务

```bash
python3 scripts/install.py --hooks
python3 scripts/install.py --launch-agent
```

安装器会备份并合并现有 Hook；配置里的对话共享继续保持 opt-in。完整安装前，Typeless
需要至少启动一次并完成登录及麦克风权限：

```bash
python3 scripts/install.py --all
```

StopWatch 插着 USB 时不会长期占用系统默认输入。只有从第 5 页开始 Typeless 听写时，
Bridge 才会记住当前麦克风并临时切换到 `M5 StopWatch Mic`（兼容早期名称
`TinyUSB UAC1`）；手表结束听写或启动失败后会恢复原输入设备。通过键盘或其他方式启动
Typeless 时，仍使用 Mac 原本的默认麦克风。

首次执行 `--launch-agent` 或 `--all` 时，安装器会为缺少有效 Token 的本机配置自动生成
随机 Token，并以 `0600` 权限保存。连接 StopWatch 后，设备会通过物理 USB CDC 自动配对
并把 Token 写入 NVS；不需要手机热点，也不需要先配置 Wi-Fi。设备最多保留两台 Mac 的
Token，已有槽位不会被自动覆盖。

Wi-Fi 是可选通道：未配置时 Dashboard 直接进入并等待 USB；需要脱离 USB 使用时，再在
Dashboard 中长按 A+B 2.5 秒主动进入配网。

## 4. 固件构建与烧录

### PlatformIO

```bash
cd firmware
pio run -e m5stack-stopwatch-uac
```

真机首次刷入应遵循项目根目录 `PROJECT.md`：先确认串口与原厂硬件，再进入官方 Download
Mode，只写应用分区，不执行 `erase_flash`。

## 操作

- 开机先进入程序选择器：A 选中 Dashboard，B 选中本地 Stopwatch，轻触程序卡进入。
- 本地 Stopwatch：静止时 B 开始；运行时 A 记圈、B 暂停；暂停时 A 复位、B 继续。
- 红色电源键短按：熄屏；再次短按唤醒。熄屏时关闭显示、触控与麦克风，Wi-Fi、Bridge
  监听与提示音保持工作。
- 红色电源键双击：从任意页面进入程序选择器。
- 红色电源键长按：未连接 USB 时关机；连接 USB 时保留约 2 秒进入 Download Mode 的入口。
- 左右滑动：切换时钟、TickTick 专注、Codex、Claude、Typeless、AI 热点和 Obsidian 七页。
- A 单击：正计时开始 / 暂停 / 继续。
- A 双击：结束正计时并保留本次用时显示。
- B 单击：25 分钟倒计时开始 / 暂停 / 继续。
- B 双击：结束倒计时，回到 25:00。
- B 长按 0.8 秒：回到第 1 页时间总览，不改变任何计时状态。
- 单击会等待约 360 ms，以区分双击。
- A 长按 0.8 秒：打开网络选择。
- A+B 长按 2.5 秒：进入配网。
- 触摸左/右侧纵向滑动：调节亮度/提示音量。
- 第 6 页：`知道了` 清除当前热点，`打开` 在 Mac 上打开来源文章。
- 熄屏期间收到新的 AI 热点时仍会播放尖叫并震动；下一次短按唤醒自动进入第 6 页。
- 第 7 页：`打开文档` 在 Obsidian 中打开抽中的笔记，`再摇` 随机下一篇；在该页晃动
  StopWatch 也会触发抽签，并有 900 ms 防连触间隔。

正计时与倒计时互斥：启动或继续其中一个时，若另一个正在运行，会先暂停另一个。
任意 A/B 专注操作都会自动切换到第二页提供反馈。

原来绑定 B 键的 Typeless 麦克风入口已让位给倒计时；在第 5 页轻触中央麦克风区域，
即可开始或停止 Typeless USB 收音。页面只有在物理 USB、TinyUSB 音频链路和 USB Bridge
均在线时才显示 `READY`；未插线显示 `NO USB`，已插线但 Mac 尚未完成 Bridge 鉴权时
显示两行 `NO / BRIDGE`。两组文案均使用补齐字符的原生 80 px Noto Bold 字体，不缩放、
不回退到缺字字体。不可用状态不会向 Mac 发送 Typeless 启动动作，录音中拔线则会
主动结束当前听写会话。M5 麦克风只在这段由手表发起的会话内临时成为系统默认输入；
停止后会恢复开始前的输入设备，不影响其他语音产品和项目。

## 页面

- 第 1 页：时钟总览。时分右侧以原生抗锯齿 Noto Bold 32 px 数字和下划线显示跳动秒数，
  并靠近 `HH:MM` 组成一个整体；每秒只刷新秒数小区域，分钟变化时才完整重绘，避免整页闪动。
  薄荷绿强调底上的电池始终使用高对比深色，USB 充电状态只显示闪电切口，不会变成与底色
  混在一起的绿色。紧凑状态条显示 TickTick 当前专注进度
  与当天全部 Coding AI 的 Token 总处理量，例如 `专35 · AI518M`；Codex/Claude 额度分别
  留在第 3、4 页。
- 第 2 页：TickTick 双计时卡片。左侧 A 为正计时，右侧 B 为 25 分钟倒计时。
- 第 3 页：Codex 仪表盘与动态中心图标。
- 第 4 页：Claude 仪表盘与动态中心图标。
- 第 5 页：Typeless USB 麦克风、实时波形、峰值表；轻触中央开始/停止。
- 第 6 页：AI 热点尖叫。新文章自动成为当前热点；声音和振动提醒后可确认或打开。
- 第 7 页：Obsidian 幸运笔记。显示可抽数量、标题和来源文件夹，支持触摸或晃动再摇。

## USB 动作协议

状态请求保持兼容：

```text
M5DASH_USB_V1|GET|<token>
```

专注动作使用：

```text
M5DASH_USB_V1|POST|<token>|<action>
```

`action` 只能是 `stopwatch-click`、`stopwatch-end`、`countdown-click`、
`countdown-end`、`ai-ack`、`ai-open`、`obsidian-roll`、`obsidian-open`。TickTick HTTP
动作对应 `/api/ticktick/<action>`；新功能分别对应 `/api/ai/ack|open` 与
`/api/obsidian/roll|open`。所有接口都需要 Dashboard Token。

## 验证

```bash
python3 -m unittest discover -s tests -v
c++ -std=c++17 tests/interaction_logic_test.cpp -o /tmp/m5-interaction-test
/tmp/m5-interaction-test
cd firmware && pio run -e m5stack-stopwatch-uac
```

Python 和独立 C++ 测试可以在无设备时完成；PlatformIO 完整编译和真机 A/B 行为仍需在
设备写入后验证。当前 UAC 固件已完成 PlatformIO 编译，尚未烧录到 Alice 的 StopWatch。

## 已知边界

- TickTick 控制仍依赖 macOS 本机 UI 自动化，系统权限、窗口状态或 TickTick 更新都可能
  影响动作成功率；旧 Stick S3 项目的回退和错误状态会原样上报。
- M5 到 Mac 的接口只适合可信局域网或物理 USB。
- B 键已经专用于倒计时，Typeless 改用第 5 页触摸开关。
- 熄屏时 AI 新闻轮询继续依赖 Bridge 和可用的 USB/Wi-Fi 链路；新尖叫会播放声音并震动，
  但不会擅自点亮 AMOLED。用户下一次短按唤醒时才自动进入第 6 页。
- AI 热点依赖 Codex Resets、AIHOT 与官方 Feed 的可用性；单个来源失败不会把其他来源
  判为离线。AIHOT 热度和摘要只是判断输入，没有官方原文的第三方热点不会直接升级为尖叫。
- Obsidian 只扫描配置中明确授权的 Markdown 根目录；默认不进入 Alice Writing。
- 仓库不跟踪个人 Token、Wi-Fi、任务日志、构建缓存或预编译固件。

USB 音频双任务管线与 ES8311 参数选择性参考了 MIT 许可的
[`digitsisyph/codex-micro-stopwatch`](https://github.com/digitsisyph/codex-micro-stopwatch)，
固定评审提交 `e4f51036ebba21815854e7c427a3f51c2dc10fc1`；声明见
[`third_party/codex-micro-stopwatch-MIT.txt`](third_party/codex-micro-stopwatch-MIT.txt)。

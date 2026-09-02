# M5 StopWatch：TickTick 专注 + AI Dashboard

这是 Alice 的 M5Stack StopWatch 圆屏工作台：

- TickTick 专注：A 键控制正计时，B 键控制 25 分钟倒计时。
- Codex：显示活动、等待、错误、额度窗口和 Token 用量。
- Claude：显示活动、额度窗口和 Token 用量。
- AI 热点尖叫：筛选官方 AI 新闻源，新热点到达时切页提示，并使用扬声器与振动马达提醒。
- Obsidian 掷骰子：从明确授权的 Markdown 根目录随机抽一篇笔记并在 Obsidian 中打开。
- 时钟总览：时间、日期、天气、电量、TickTick 今日累计专注分钟，以及当天全部 Coding AI 的
  Token 总处理量。
- Timer：完全离线的本地倒计时器，A/B 保存两个可调预设，到点后以屏幕、振动与提示音提醒。

公开示例默认不展示 Codex/Claude 任务标题和对话。实时对话预览必须由本人显式开启，
且只读取可见的用户/助手文本，不转发推理、工具输入或工具结果。

## 数据路径

StopWatch 默认通过物理 USB CDC 访问本机 Dashboard 桥接，也可选择带 Token 的局域网
HTTP。Dashboard 再复用已经由
[M5StickS3 TickTick Focus Bridge](https://github.com/isalicema/m5stick-ticktick-focus)
验证过的专注服务，以及可选的
[Multi AI Usage Monitor](https://github.com/isalicema/api-usage-board)：

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

本项目默认连接 `http://127.0.0.1:8787`，复用
[m5stick-ticktick-focus](https://github.com/isalicema/m5stick-ticktick-focus) 中的
`mac-bridge/focus_bridge.py`。该服务提供：

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

AI 用量是**可选增强项**。安装并运行
[Multi AI Usage Monitor](https://github.com/isalicema/api-usage-board) 后，Dashboard 默认读取
`http://127.0.0.1:8177/api/token-series?days=380&metric=total`：最后一天值用于
首屏今日总量，各渠道的窗口总和可作为本地日志可回溯累计量；当前 Multi AI Usage Monitor
最多扫描约 95 天本地 Claude 日志，因此 Claude 的“累计”是可回溯累计，不冒充账号创建
以来的绝对终身总量。
来源是 `api-usage-board` 已归一化的 Claude Code、Codex、Kimi Code、DeepSeek、OpenRouter
和 Grok；Cursor 与 Antigravity 目前没有 Token 序列，因此不进入总量。首屏采用
`today.total`，即 input + output + cache read + cache write 的总处理量，同时 Bridge 保留
`today.auth`（不含 cache）和各 Provider 明细。来源不完整时首屏显示 `AI--`，不会把部分
数据冒充完整总量；Grok 当天有数据时因其日志是近似口径，数值前显示 `~`。
当前跨 Provider 没有共同 request id；若同一次请求同时被客户端本地日志和 OpenRouter
analytics 记录，需要在 `api-usage-board` 侧排除重复渠道，手表端不会猜测去重。

没有安装 Usage Monitor 时，Dashboard 仍能启动：Codex 从本机 App Server、Hooks 与 session
日志读取活动、官方额度和本机今日用量；Claude Code 仍从 `~/.claude/projects` 显示活动任务。
缺失的是首页跨 Provider 总量、Claude Token/额度增强数据，以及 Kimi Code、DeepSeek、
OpenRouter、Grok 的汇总。首屏会显示 `AI--`，不会把局部数据冒充完整总量。若不需要这些
增强项，可在本机 `config.json` 中设置 `ai_usage.enabled: false`，避免无意义的连接重试。

TickTick Focus Bridge 只提供当前正计时和倒计时状态，没有今日汇总字段。Dashboard Bridge
因此按两个计时器的进度增量维护按日台账，并持久化到 `ticktick.daily_state_path`；首页显示
`专25m` 这样的今日累计分钟，完成计时或 Bridge 重启后不会归零，跨本地午夜开始新一天。

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

Codex 的完成动画只应绑定产品级 `notify` 发出的 `agent-turn-complete`，不再把 session JSONL
中的 `task_complete` 当作完成信号；因此普通 tool use 不会误播动画。安装器会把接收器安装为：

```text
~/Library/Application Support/M5Dashboard/bin/M5CodexNotify
```

如果 `~/.codex/config.toml` 已经通过包装脚本串联 peon-ping 等完成音效，不要覆盖原有
`notify`；只需在同一个包装脚本中，把收到的原始 JSON payload 原样再传给上面的接收器。
这样音效和手表动画共享 Codex 自己的同一次 `turn-ended` 回调，同时任一辅助程序失败都不应
阻断 Codex。未配置产品级 `notify` 时，旧式 Hooks 仍可提供活动状态，但不会猜测完成动画。

Claude 默认不依赖 peon-ping 或 Stop Hook。Bridge 轻量轮询 `~/.claude/projects` 中的会话
JSONL：`tool_use`、`pause_turn` 和 `max_tokens` 仍视为工作中，thinking-only 的 `end_turn`
也不会触发；只有同时带有可见最终回复的 `end_turn` 才会生成完成动画。标题是否共享仍受
`expose_transcript` 控制，完成判断本身不需要公开正文。peon-ping 可继续独立播放音效，
其成功或失败不会影响手表动画。仅在明确需要旧式 Stop Hook 时，才把
`claude.completion_source` 设置为 `hook` 并运行 `python3 scripts/install.py --claude-hook`。

完成 Hook 会先通过带 Dashboard Token 的本机 HTTP 接口原子合并一条无正文凭据，再向已认证
的手表发送不含 Token、标题或对话的 UDP 状态变化信标；USB 在线时还会直接推送一次新快照。
手表收到信标后只额外拉取一次正常鉴权状态，信标丢失则由原有 2 秒轮询兜底。因此动画无需
依靠 AI 活跃期间的高频轮询，长期运行 Codex/Claude 也不会持续增加手表通信耗电。

StopWatch 插着 USB 时不会长期占用系统默认输入。只有从第 5 页开始 Typeless 听写时，
Bridge 才会记住当前麦克风并临时切换到 `M5 StopWatch Mic`（兼容早期名称
`TinyUSB UAC1`）；手表结束听写或启动失败后会恢复原输入设备。通过键盘或其他方式启动
Typeless 时，仍使用 Mac 原本的默认麦克风。未插 USB 但 Wi-Fi Bridge 在线时，第 5 页会
降级为 `MAC MIC` 遥控模式：只发送 Typeless 启停快捷键，不切换输入设备，直接使用电脑
当前的默认麦克风。

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

真机首次刷入前先确认串口与原厂硬件，再进入官方 Download Mode；只写应用分区，不执行
`erase_flash`。

USB 烧录脚本同时把原厂 8 KiB `otadata` 恢复为空白状态并写入 `ota_0`，确保此前若由 OTA
切到 `ota_1`，救援后也会重新选择刚写入的 `ota_0`。它不会擦除 NVS，已保存的 Wi-Fi、
Dashboard Token 和设备设置仍会保留。

## 5. HTTP OTA

HTTP OTA 是 Bridge 辅助的后续升级通道，不替代 USB 首次烧录和救援。原厂 16 MB 分区表中
`ota_0` 与 `ota_1` 各为 `0x4f0000` bytes；本项目使用实机审计得到的完整分区表构建，编译阶段
也会拒绝超过单个 OTA 分区的固件。

升级流程如下：

1. 在 Mac 上构建并完成测试；不要直接把未经验证的临时产物发布给手表。
2. 用发布脚本把固件复制成以 SHA-256 命名的不可变文件，并原子更新 Bridge 的
   `current.json`：

   ```bash
   python3 scripts/publish_ota.py \
     --firmware firmware/.pio/build/m5stack-stopwatch-uac/firmware.bin
   ```

3. Bridge 通过需要 Dashboard Token 的 `GET /api/ota/manifest` 提供大小、SHA-256 和下载路径，
   再由 `GET /api/ota/firmware/<sha256>` 流式提供镜像。没有 `current.json` 时接口返回 `204`，
   手表保持原版本。
4. 手表只在第 1 屏、亮屏、Bridge 与 Wi-Fi 在线且没有计时、听写、完成动画或配网等交互时
   启动升级；未接 USB 时还要求电量不少于 40%。下载期间屏幕显示进度。
5. 镜像直接写入当前未运行的 OTA 分区，同时计算 SHA-256。只有实际字节数、SHA-256、响应
   身份头和 ESP 应用镜像校验全部通过，才保存版本标记并切换启动分区；任何失败都会中止写入，
   不改变当前启动分区，同一坏候选在本次运行中也不会反复尝试。
6. 新固件完成完整 `setup()` 后才标记为有效。若启动阶段崩溃，ESP32 OTA 回滚机制可回到上一
   可用分区；USB 烧录脚本始终是最终救援入口。

这是一条可信家庭局域网内的轻量通道。Dashboard Token、精确大小和 SHA-256 能防止传输损坏
与误写，但 HTTP 本身不提供 TLS 或固件签名级的发布者身份认证；不要把 Bridge 端口暴露到公网。
需要更强供应链保证时，应再引入签名清单、Secure Boot 或 HTTPS，而不是把哈希误当成签名。

## 操作

- 开机先进入程序选择器：A/B 前后选择 Dashboard、本地 Stopwatch 或 Timer，轻触程序卡进入。
- 本地 Stopwatch：静止时 B 开始；运行时 A 记圈、B 暂停；暂停时 A 复位、B 继续。
- 本地 Timer：默认 A 为 8 分钟、B 为 10 分钟；待机时按对应实体键开始，运行时再按同一键
  暂停/继续，另一个键不会误切当前计时。运行中 `RESET` 置灰，必须先用当前 A/B 键暂停，
  才能结束本轮并归位；待机时轻触 `SET` 进入预设编辑，选择 A/B 后上下拖动分钟滚轮：
  短滑精调、长滑加速，
  `SAVE` 写入设备、`CANCEL` 放弃修改。到点后进入红色超时正计时；同一个 A/B 键仍负责
  暂停/继续超时读数，不会直接开启新一轮。到点音效采用约 2 秒的下降式双响门铃，与 AI 热点
  短促、快速上扬的“尖叫”保持清晰区别，更适合会议和活动现场。
- 红色电源键短按：熄屏；再次短按唤醒。熄屏时关闭显示、触控与麦克风，Wi-Fi、Bridge
  监听与提示音保持工作。
- 红色电源键双击：运行中从任意页面进入程序选择器；真关机后双击开机。
- 红色电源键长按：未连接 USB 时关机；连接 USB 时保留约 2 秒进入 Download Mode 的入口。
- 短按熄屏会快速淡出并轻震；真关机与冷启动分别显示独立的 `SHUTTING DOWN` 和
  `STARTING` 动画，避免把熄屏误认为关机。
- 左右滑动：切换时钟、TickTick 专注、Codex、Claude、Typeless、AI 热点和 Obsidian 七页。
- A 单击：正计时开始 / 暂停 / 继续。
- A 双击：结束正计时并保留本次用时显示。
- B 单击：25 分钟倒计时开始 / 暂停 / 继续。
- B 双击：结束倒计时，回到 25:00。
- B 长按 0.8 秒：回到第 1 页时间总览，不改变任何计时状态。
- 单击会等待约 360 ms，以区分双击。
- A 长按 0.8 秒：打开网络选择。
- A+B 长按 2.5 秒：进入配网。
- 触摸左侧 `2/5` 纵向滑动：调节亮度；右侧 `2/5`：调节提示音量；中间 `1/5` 为
  纵向调节安全区，但仍可左右滑动翻页。
- 第 6 页：`知道了` 清除当前热点，`打开` 在 Mac 上打开来源文章。
- 熄屏期间收到新的 AI 热点时仍会播放尖叫并震动；下一次短按唤醒自动进入第 6 页。
- 第 7 页：`打开文档` 在 Obsidian 中打开抽中的笔记，`再摇` 随机下一篇；在该页晃动
  StopWatch 也会触发抽签，并有 900 ms 防连触间隔。

正计时与倒计时互斥：启动或继续其中一个时，若另一个正在运行，会先暂停另一个。
任意 A/B 专注操作都会自动切换到第二页提供反馈。

原来绑定 B 键的 Typeless 麦克风入口已让位给倒计时；在第 5 页轻触中央麦克风区域，
即可开始或停止 Typeless。物理 USB、TinyUSB 音频和 USB Bridge 均在线时使用 `USB MIC`：
StopWatch 提供真实 48 kHz 麦克风、波形和峰值；USB 不可用但已鉴权的 Wi-Fi Bridge 在线时
使用 `MAC MIC`：仅遥控 Typeless，保留 Mac 当前默认输入，不伪造手表波形。两种模式都在
原生 24 px 标题网格显示来源，中央继续使用同一套原生 80 px `READY / LIVE / ERROR`，
没有运行时缩放或混排基线。两条链路都不可用时才显示两行 `NO / BRIDGE`，且不会发送动作。
USB 会话中拔线会主动结束当前听写；M5 麦克风只在这段会话内临时成为系统默认输入，停止后
恢复开始前的设备，不影响其他语音产品和项目。

## 页面

- 第 1 页：时钟总览。时分右侧以原生抗锯齿 Noto Bold 32 px 数字和下划线显示跳动秒数，
  并靠近 `HH:MM` 组成一个整体；每秒只刷新秒数小区域，分钟变化时才完整重绘，避免整页闪动。
  应用每次启动都会重新启用 M5PM1 充电器，USB 数据与充电可同时工作；薄荷绿强调底上的电池
  始终使用高对比深色，实际充电时显示完整深色电池与加粗闪电切口，不会变成与底色混在一起
  的绿色。紧凑状态条显示 TickTick 当前专注进度
  与当天全部 Coding AI 的 Token 总处理量，例如 `专25m · AI 5.03亿`；Codex/Claude 额度分别
  留在第 3、4 页。
- 第 2 页：TickTick 双计时卡片。左侧 A 为正计时，右侧 B 为 25 分钟倒计时。
- 第 3 页：Codex 仪表盘与动态中心图标。
- 第 4 页：Claude 仪表盘与动态中心图标。
- 第 5 页：Typeless 双模式；USB 时使用手表麦克风并显示真实波形，拔线时经 Wi-Fi 遥控
  Typeless 使用 Mac 麦克风；轻触中央开始/停止。
- 第 6 页：AI 热点尖叫。新文章自动成为当前热点；声音和振动提醒后可确认或打开。
- 第 7 页：Obsidian 幸运笔记。显示可抽数量、标题和来源文件夹，支持触摸或晃动再摇。

七屏属于 Dashboard；Stopwatch 与 Timer 是程序选择器中的另外两个独立 App。

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
- M5 到 Mac 的接口（包括 HTTP OTA）只适合可信局域网或物理 USB。
- `MAC MIC` 依赖手表和 Mac 位于可互访的同一 Wi-Fi，且 Mac Bridge 正在运行；该模式不会
  将 Mac 麦克风峰值回传给手表，因此页面明确显示输入来源而不伪造音量波形。
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

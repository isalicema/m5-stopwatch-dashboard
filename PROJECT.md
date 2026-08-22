# M5 StopWatch × 星子

## 项目定位与当前状态

这是 Alice 与星子共同维护的 M5Stack StopWatch 项目。当前以朋友公开的 Dashboard
项目为可追溯底座，再逐步改造成符合 Alice 日常习惯的版本。

- 上游仓库：<https://github.com/Googler0825/m5-stopwatch-dashboard-oss>
- 上游基线：`2726c3afe6dd1e615caa83d905f00b2a2610fb57`
- 本地开发分支：`alice/main`
- 上游远程名：`upstream`
- 当前程序：程序选择器 + Dashboard 七屏 + 本地 Stopwatch
- 当前能力底座：时钟总览、TickTick 正计时与 25 分钟倒计时、Codex、Claude、
  48 kHz UAC Typeless 麦克风、AI 热点尖叫、Obsidian 幸运笔记、天气、双 Wi-Fi、
  USB/Wi-Fi 桥接与触摸/按键/电源交互
- 当前连接策略：Mac + USB 是 Alice 的默认日常数据通道；首次物理连接自动完成本地 Token
  配对并写入 NVS。Wi-Fi 不再是启动前提，只在 Alice 主动长按 A+B 时进入配网。

软件已经准备好，Alice 的 StopWatch 也已通过 USB 被 Mac 唯一识别；程序选择器、Dashboard
七屏、本地 Stopwatch、自动化测试与 UAC 固件编译均已完成。2026-08-21 首次写入因旧脚本
错用 `0x10000` 而黑屏；串口诊断确认原厂 `ota_0 = 0x20000` 后完成纠正写入、写后哈希校验
与应用 USB 重新枚举。Alice 已确认圆屏正常出现“选择程序”界面；应用启动、基础显示和
程序选择器首屏通过真机验证，触摸、A/B、电源键与各程序内部功能继续逐项验收。

## 台账状态定义

以后功能与改动统一使用下列状态，避免把讨论、代码、编译和真机混成一件事：

| 状态 | 含义 |
|---|---|
| 已决策 | Alice 已确认功能目的、判断规则或交互契约，可能尚未编码 |
| 已实现 | 对应代码已经存在于当前工作树 |
| 软件验证 | 单元测试、交互测试、静态检查、预览或固件编译已经通过 |
| 真机验证 | 已在 Alice 的实体 StopWatch 上烧录并实际操作通过 |
| 待实现 | 已有清晰方案，但代码还没有完成 |
| 已替代 | 曾经存在的方案已被新的产品判断取代，不再作为当前行为 |

Alice 的实际观察和操作感受是最终真机判断；浏览器预览、测试和编译只能证明软件层。

## 当前软件验证记录（2026-08-21）

- `m5-dashboard`：120 项测试通过，独立 C++ 交互测试通过。
- `m5-dashboard-home`：23 项测试通过。
- 两份示例配置通过 JSON 解析。
- `mac/M5AudioInput.c` 已用本机 clang、CoreAudio 和 CoreFoundation 真实编译通过。
- 为避开全局 Python 3.14 与失效的 `~/.local/bin/uv`，已在被 Git 忽略的 `.pio/cli`
  建立 Python 3.12.12 + PlatformIO 6.1.19 隔离环境；自检脚本会优先使用它。
- UAC 使用的 pioarduino 55.3.311 平台和 Python 构建依赖已经安装完成。
- 七屏浏览器预览和 AI 热点/Obsidian 双屏对比通过，无未关闭的 P0/P1/P2 视觉问题。
- 第 6 屏正式后端在线冷启动通过：Codex Resets、AIHOT 热点榜、AIHOT snapshot、
  OpenAI News 与 Google AI 均成功建立连接和基线，历史事件没有触发尖叫。
- 当前 USB-first UAC 固件编译并烧录成功，大小 4,587,920 bytes。
- 当前固件 SHA-256：`b33e814c516a5e59933b03ea985e8e05ac7936f30648622ea6b645e6cca8b853`。
- 固件路径：`m5-dashboard/firmware/.pio/build/m5stack-stopwatch-uac/firmware.bin`。
- Mac 常驻 Bridge 已安装为 `com.local.m5dashboard.bridge` 并通过 `/healthz` 200 检查；本机
  配置权限为 `0600`、USB 已启用、随机 Token 合法，Codex/Claude 对话共享保持关闭。
- Dashboard 首轮真机验收发现五项问题：编辑页文字仍使用位图字体非整数缩放、450 px
  设计画布贴入 466 px 圆屏时右侧强调圆缺少 8 px 外延、额度失败时显示 `↺--`、Claude
  仍保留朋友 iMac 的禁用示例源、Typeless 麦克风未按设计 SVG 绘制。当前候选已分别改为
  14/18/24/104 px 原生抗锯齿 Noto 字体、外层 frame 同色补圆、无数据时“重置待同步”、
  Claude 本地在线模式与 7 px 圆头 SVG 麦克风。Bridge 已重装，候选固件已烧录，等待
  Alice 真机视觉复验。
- Multi AI Usage Monitor 的 `/api/quota` 已成为 Codex/Claude 配额与重置的优先数据补充，
  `/api/token-series` 继续提供今日 Token。2026-08-21 实测 Codex `wham` 官方直连在线，
  7 天已用 20% 且有真实重置时间；Claude `direct` 官方直连在线，5 小时 0%、7 天 99%，
  7 天重置时间可用。Claude 本地活动在线不再依赖远端 iMac；上游缺少重置时间时不伪造。
- 本轮 Dashboard 候选通过 120 项主测试、23 项伴随桥接测试、独立 C++ 交互测试、两份
  JSON、自带 macOS 音频助手真实编译和 UAC PlatformIO 构建。固件 4,878,656 bytes，
  距 `ota_0` 上限尚余 298,688 bytes；SHA-256 为
  `9c464a21b0147287c138092d99172ac2f2fe176e7ea35e0318d6441a2e8a6ac2`。Alice 明确“更新”后，
  已从原厂 `ota_0` 的 `0x20000` 写入实体设备并通过 Flash 数据哈希校验；设备恢复为
  `/dev/cu.usbmodemM5DASHMIC31`，Bridge 随即重新完成客户端认证。
- Alice 真机确认原生字体已经平滑且整体接近设计稿，同时发现首页强调圆边缘仍有锯齿、
  “星盘/成果”等全屏二级页的顶部和右侧残留首页红圆，以及滑入 Codex 页时设备重启并回到
  程序选择器。照片证明第二项来自 450 px 页面之外的 466 px 外框残留；固件已将内外两层
  强调圆改为 M5GFX 平滑圆，并让全屏 overlay 显式关闭外框强调色。Codex 首次绘制会走
  运行时 PNG 解码，是当前与重启时机最吻合的新路径；候选版已把 Codex/Claude 96 px 图标
  预转换为 RGB565，页面切换与轻微缩放动画只做像素拷贝，不再运行时解 PNG。122 项主测试、
  23 项伴随测试、独立 C++ 测试和 UAC 编译通过；固件 4,913,248 bytes，距 `ota_0` 上限
  尚余 264,096 bytes，SHA-256 为
  `8224220f6bcb7ae5edc568a5ebda873c1f2a7ad70b01a9351ebd22990e10c163`。Alice 确认“更新”后，
  已从 `ota_0 / 0x20000` 写入并通过 Flash 数据哈希校验；设备恢复为
  `/dev/cu.usbmodemM5DASHMIC31`，Bridge 客户端重新认证成功。Codex 重启根因是否闭环仍以
  真机复验为最终判据。
- Codex 重启再次复现后，Bridge 侧被动 panic 捕获没有收到异常控制台：UAC 应用 CDC 与 ESP
  ROM 控制台不是同一条可用证据通道。当前诊断版改为在 RTC 内存保存最后渲染阶段，并在
  下次启动通过只含 `reset reason / stage / page` 三个整数的 USB 协议上报；协议拒绝业务文本
  和 Token。124 项主测试与 UAC 编译通过；4,913,856-byte 固件已写入 `0x20000` 并通过
  Flash 数据哈希校验，SHA-256 为
  `d63c79ed08da40bab27d0beb396c355bb1a44bee0cc1e7758a5d2c0c39edf82e`。设备恢复应用 USB
  身份后，Bridge 成功收到正常硬复位基线 `reason=1 stage=0 page=7`，证明诊断链路可用；
  等待再次触发 Codex 重启以定位真实阶段。
- 诊断版复现后 Bridge 收到 `reason=4 stage=0 page=7`：ESP32 官方 reset reason 4 为 PANIC；
  stage 0 证明 Codex 整页绘制、466 px 合成、切页动画和最终推屏均已完成，异常发生在随后
  启动的 Provider 中心图标局部动画刷新。修复候选保留初次静态 Codex/Claude 品牌图标、
  状态/配额/详情入口和任务完成全屏动画，删除进入页面后把 icon sprite 分别同步回页面画布、
  frameCanvas 与物理屏幕的多目标刷新；图标改为只写页面画布并随整页合成。新增回归断言确保
  Provider 图标代码不能直接访问 frameCanvas 或 `M5.Display`。125 项主测试、独立 C++ 测试
  与 UAC 编译通过；4,909,216-byte 候选 SHA-256 为
  `d3e068745938517fff84bf8835087f296b7470c845fba56b4e099bbd5163fcc2`。Alice 确认“更新修复版”
  后已写入 `ota_0 / 0x20000` 并通过 Flash 数据哈希校验；首次应用端口切换已成功进入 ROM
  端口但因 macOS `Device not configured` 未写入，随后从已确认的 `/dev/cu.usbmodem2101`
  直接完成烧录。设备恢复为 `M5 StopWatch Mic`，Bridge 认证成功并收到正常硬复位基线
  `reason=1 stage=0 page=7`，等待真机复验 Codex 与 Claude 页面稳定性。
- Alice 复验确认删除 Provider 图标局部动画后，切入 Codex 仍以完全相同的
  `reason=4 stage=0 page=7` PANIC 重启，故“局部多画布刷新是根因”的判断被实机证伪；它只是
  整页返回后的一个候选路径。二次诊断候选不再改 UI 或功能，在 `changePage()` 返回后的第一条
  语句及 Provider 页主循环的 USB、Wi-Fi、discovery、touch、定时重绘和循环返回前加入阶段
  标记，以区分切页返回栈保护和后续模块。125 项测试与 UAC 编译通过；固件 4,909,424 bytes，
  SHA-256 为 `99d2e06ef07faf8ff95f8d2c49ac863fb5d12c737bee34a8f8756f08503a9b20`，
  尚未烧录，等待 Alice 确认二次诊断更新。
- Alice 指出闪退首次出现的真实变更边界是“Provider 重置显示、原生编辑字体与 Multi AI
  Usage 配额接入”这一整批，而更早的 Codex、Claude、Typeless 均可进入。实时 Bridge 状态
  证明当前 Codex 有 2 个活动任务，因此切页时页脚走“活动任务”分支，并不会绘制 `↺重置`
  文案；配额/重置数值正常，四套 VLW 的字形排序、位图边界与所需字形也通过结构检查。故当前
  证据支持“整批 Provider 页面绘制回归”，但不支持把单独的重置字符串定为根因。为一次验证
  这条边界，已准备回归对照候选：Bridge、新配额与重置字段全部保留，只将 Codex/Claude
  临时切回最初真机可进入的深色 Provider 渲染器和旧 PNG 图标路径；其他五屏不变。126 项主
  测试及 UAC 编译通过，固件 4,876,240 bytes，SHA-256 为
  `4962ff20ef2ab792adb30338cd2135db32361e59b972b99b5ad3d466ab014006`。Alice 明确“更新回归
  对照版”后，固件已写入 `ota_0 / 0x20000`，Flash 数据哈希校验通过；设备恢复为
  `/dev/cu.usbmodemM5DASHMIC31`，Bridge 收到正常硬复位基线 `reason=1 stage=0 page=7`
  并重新认证。Alice 真机确认可连续滑入 Codex 与 Claude，证明后端、配额/重置数据和切页
  状态机并非 PANIC 根因，回归边界位于新版 Provider 绘制路径。回归对照版的旧 UI 不作为
  最终呈现。下一候选已恢复新版编辑式 Codex/Claude UI，并进一步移除独立 `iconCanvas`
  的创建、RGB565 写入和 sprite 回拷；96 px Provider 图标改为直接写入主 `canvas`，旧稳定
  Renderer 仅保留为关闭状态的应急开关。126 项主测试与 UAC 编译通过，固件 4,909,152
  bytes 的首个候选尚未烧录。Alice 随即指出新版重置前缀 `↺` 在真机上实际呈现为带 ×
  的缺字方框；根因是 Noto CJK 对 U+21BA 返回 `.notdef` 占位轮廓，不能把“VLW 中存在码位”
  当作符号可用。当前候选不再从字体绘制 `↺`，改用 M5GFX 圆弧和三角箭头组成原生矢量
  回转图标，并与 `3d8h` 等平滑文字按组合宽度居中；字体生成器也不再把该码位列作覆盖证明。
  126 项主测试与 UAC 重新编译通过，最终候选 4,909,344 bytes，SHA-256 为
  `cd83c1c8d908f788a237b093c0f200c671d92aad5e8d3841f7bb630b0b99d697`。Alice 明确“更新
  新版 UI”后，固件已写入 `ota_0 / 0x20000` 并通过 Flash 数据哈希校验；设备恢复
  `/dev/cu.usbmodemM5DASHMIC31`，Bridge 收到正常硬复位基线 `reason=1 stage=0 page=7`
  并重新认证。等待真机复验新版 Codex/Claude 是否稳定，以及矢量回转箭头是否正确呈现。
- Alice 真机滑入 Codex 后，新版 UI 仍立即以 `reason=4 stage=0 page=7` PANIC；因此“独立
  `iconCanvas` 是根因”再次被实机证伪。现有对照矩阵为：旧 Renderer + 旧 PNG 直绘稳定，
  新 Renderer + RGB565 直绘崩溃，而最早的新 Renderer + PNG 中转也崩溃。下一单变量候选
  保留完整新版编辑式 UI、字体、配额与矢量重置箭头，只把 Provider 图像改为回归版已证明
  稳定的 `codex_icon_png / claude_icon_png` 直接写入主画布，不创建中间 Sprite，也不编入
  RGB565 品牌图数组。126 项主测试与 UAC 编译通过，固件 4,874,832 bytes，SHA-256 为
  `96ace6f519c7181eb98ee817a3a89483e32504968e73d3f0cd34eedb4d859c50`。Alice 明确“更新
  单变量版”后，首次应用端口切换因 macOS `Device not configured` 在写入前退出；设备实际
  已进入 `/dev/cu.usbmodem2101` Download Mode，随后从该 ROM 端口完成 `ota_0 / 0x20000`
  写入和 Flash 数据哈希校验。设备恢复 `/dev/cu.usbmodemM5DASHMIC31`，Bridge 收到正常
  硬复位基线 `reason=1 stage=0 page=7` 并重新认证；等待真机滑入 Codex 验证单变量结果。
- Alice 真机确认“单变量版”滑入 Codex 仍以 PANIC 重启，故旧 PNG、RGB565 与中间 Sprite
  三条图像路径均被实机排除。2026-08-22 未改固件再次复现后，使用设备原厂分区表中的
  `coredump 0xe00000/0x10000` 只读提取完整 ESP-IDF ELF core；回溯将异常精确定位到
  `M5GFX VLWfont::drawChar -> PointerWrapper::read -> ROM memcpy`，参数为 104 px Noto Bold
  百分号位图 `100 x 79 = 7900 bytes`。M5GFX 在 `drawChar()` 内用 `alloca(w * h)` 把整枚
  字形放进 `loopTask` 栈，7900-byte 百分号超过剩余栈空间；时钟的数字/冒号与旧 Provider
  字体因此都不会触发同一问题。修复候选保留 104 px 原生抗锯齿数字，将透明百分号改为
  `fillArc + drawThickRoundedLine` 几何组合，并从 104 px VLW 字体文件中永久删除 `%` 字形；
  最大剩余字形位图降为 5082 bytes。新增 `read_coredump.py` 只读取证工具和防回归断言，
  128 项主测试、独立 C++ 交互测试与 UAC PlatformIO 编译通过。候选固件 4,866,880 bytes，
  SHA-256 为 `48c92e2952d5a24a9ce2d58ee839c3fea5d442e294208b4b6c7b555e64d53df4`。
  Alice 明确“更新”后，首次 1200-bps 应用端口切换在写入前遇到 macOS
  `Device not configured`，设备实际已进入 `/dev/cu.usbmodem2101` Download Mode；随后从该
  ROM 端口完成 `ota_0 / 0x20000` 写入并通过 Flash 数据哈希校验。设备恢复为
  `/dev/cu.usbmodemM5DASHMIC31`，Bridge 收到正常硬复位 `reason=1 stage=0 page=7` 并重新
  完成 Token 鉴权；等待 Alice 真机滑入 Codex 验证百分号栈溢出修复。
- Alice 真机确认 Codex 与 Claude 新版页面均可稳定进入，百分号栈溢出/PANIC 已闭环；同时
  指出几何 `%` 边缘锯齿、Provider 使用了朋友底座的 `CX/CL` 替代图标，以及 Typeless
  `READY` 只显示 `E` 和缺字框。根因分别为几何线条没有字形灰阶、排障期临时回退到通用
  PNG、104 px 子集缺少 `A/D/O/R/Y`。新候选恢复工程中由本机 Codex 与 Claude 官方 App
  准备的 96 px RGB565 品牌资产；新增原生 80 px Noto Bold 子集 `%ADEILORVY`，用同一套
  抗锯齿字形绘制 `%` 与 Typeless 的 `READY/LIVE/ERROR`。该子集最大单字形位图 4697 bytes，
  低于真机已稳定的 104 px 数字上限 5082 bytes，且 104 px 字体继续永久排除 `%`。130 项
  主测试、独立 C++ 交互测试、品牌图逐像素资产校验和 UAC PlatformIO 编译通过。候选固件
  4,932,912 bytes，小于原厂 `ota_0` 的 5,177,344 bytes，SHA-256 为
  `3e8c531e50c29e21321f4006c0b868f79ba055a8ec042a7cb576eba0e91e018b`；尚未烧录。
- Alice 在烧录前继续指出七屏主界面的胶囊形按钮边缘仍有整数像素锯齿。根因是编辑式 UI
  虽已改用原生抗锯齿字体与平滑强调圆，但胶囊仍调用 M5GFX 的普通 `fillRoundRect /
  drawRoundRect`。新候选增加共用 `fillAntialiasedCapsule / drawAntialiasedCapsule`：实心
  胶囊使用 `fillSmoothRoundRect`，描边胶囊用平滑外层与平滑内层形成 2 px 边框；已覆盖
  时钟信息与快捷入口、专注模式与操作区、Codex/Claude 两枚指标及页脚、Typeless 页脚，
  以及 AI 热点和幸运笔记操作区，触摸热区与交互语义不变。131 项主测试、独立 C++ 交互
  测试、UAC PlatformIO 编译和烧录容量保护通过。合并百分号、官方品牌图、Typeless 字体及
  全七屏平滑胶囊后的候选固件为 4,932,640 bytes，SHA-256 为
  `d0314de665d318b339ea84e3caaab50178fa599e85b184936cff339d8a8b6109`。Alice 明确“更新”后，
  固件由应用端口自动切换至 `/dev/cu.usbmodem2101`，完成 `ota_0 / 0x20000` 写入与 Flash
  数据哈希校验；设备恢复 `/dev/cu.usbmodemM5DASHMIC31`，Bridge 收到正常硬复位
  `reason=1 stage=0 page=7` 并重新完成 Token 鉴权。等待 Alice 真机验收百分号、品牌图、
  Typeless 完整字符和七屏胶囊边缘。
- Alice 真机发现恢复的 Codex/Claude 品牌图呈现为噪声、荧光色与过曝色块。离线将同一
  RGB565 数组分别按正常和逐字节交换方式重建后，错误版本与真机现象完全吻合，故根因不是
  96 px 分辨率或压缩，而是 M5GFX 在 `canvas.swapBytes=false` 时将标准 `uint16_t` RGB565
  数组按 `swap565_t` 解释。修复候选在 Provider 品牌图单次 `pushImage` 前保存 canvas 状态、
  临时 `setSwapBytes(true)`，绘制后立即恢复；不修改图标源文件、不新增 PNG 解码，也不影响
  后续页面颜色状态。131 项主测试、独立 C++ 交互测试、UAC PlatformIO 编译和烧录容量保护
  通过。候选固件 4,932,592 bytes，SHA-256 为
  `def63ac6124ba80b570706d128e4e9e2fe02eb17054fcff2acdd6dde97062933`；尚未烧录。
- Alice 同时指出安全版 80 px `%` 与 104 px 数字比例失调。80 px 字形可见高度约 61 px，
  数字约 79 px；但把 VLW 百分号直接放大到 96 px 会产生约 6,716-byte 单字形位图，再次
  越过已由真机证明稳定的 5,082-byte 栈边界。新候选把 `%` 单独生成为 96 px、可见高度
  73 px 的紧裁 RGBA 抗锯齿资源，由 M5GFX 按真实 Alpha 融合白底与 Codex/Claude 强调色；
  104 px VLW 继续永久排除 `%`，80 px VLW 也收窄为 Typeless 所需 `ADEILORVY`，因此放大
  不增加 `drawChar()` 栈压力。132 项主测试、独立 C++ 交互测试、PNG 半透明边缘校验、UAC
  PlatformIO 编译、字体标记和原厂 `ota_0` 容量保护均通过。合并品牌图字节序修复与大号
  百分号后的候选固件为 4,930,464 bytes，SHA-256 为
  `9825782b2f3acd5c0c0a7b7401c32bfd553cecc60df03dfd4b454095a564bdda`。Alice 明确“更新”后，
  固件由应用端口自动切换至 `/dev/cu.usbmodem2101`，完成 `ota_0 / 0x20000` 写入并通过 Flash
  数据哈希校验；设备恢复 `/dev/cu.usbmodemM5DASHMIC31`，Bridge 收到正常硬复位诊断
  `reason=1 stage=0 page=7` 并重新完成 Token 鉴权，`/healthz` 返回 200。等待 Alice 真机验收
  官方品牌图色彩、放大百分号的比例与边缘。
- Alice 真机确认官方 Codex/Claude 品牌图、放大百分号及整体版本均已正常，随后指出
  Typeless 麦克风图标上下断开。对照设计 SVG 后确认不是屏幕拍摄问题：SVG 的托架由
  `M0 42 Q0 82 29 82` 与 `Q58 82 58 42` 两段二次曲线组成，固件此前误合并为一段以
  `(29, 82)` 为控制点的浅曲线，实际最低点仅到 `Y=62`，与 `Y=83` 开始的竖杆留下约
  21 px 断口。修复候选恢复左右两段曲线，并让两段托架与竖杆共同重叠在 `(29, 82)`；
  麦克风胶囊、位置、触摸热区和 Typeless 功能保持不变。132 项主测试、独立 C++ 交互测试、
  UAC PlatformIO 编译、字体标记和 `ota_0` 容量保护均通过。候选固件 4,930,512 bytes，
  SHA-256 为 `ac7b6ec6f3d1ba4affe571f5f7c69b7d00fe13cfa387eb8c5170b2916b67efec`；
  尚未烧录。
- Typeless 真机联调进一步确认当前 `LIVE` 只代表 StopWatch 已启动 USB 音频：固件此前未向
  Mac 发送 Typeless 动作，Mac 音频助手也只选择 `M5 StopWatch Mic`，不会触发听写快捷键。
  新候选复用 Stick S3 已验证的原生按键方案并收进本项目：触屏开始发送经 Token 鉴权的
  `typeless-start`，停止、锁屏或退出发送 `typeless-stop`；Bridge 后台打开 Typeless 但不抢
  当前写作窗口焦点，再由独立 `TypelessKeySender.app` 触发已配置的
  `Ctrl+Cmd+Shift+Space`。安装器会同时保留 `Fn` 入口、构建稳定 App Bundle，并明确检查
  macOS Accessibility 授权。138 项主测试、独立 C++ 交互测试、原生 helper 编译、UAC
  PlatformIO 编译、字体标记与 `ota_0` 容量保护均通过。合并麦克风图标连接修复和完整
  Typeless 控制链路后的候选固件为 4,931,184 bytes，SHA-256 为
  `3f3568b6abd93c3bddadc448cf080d9aa0d898f8cf702229e5a2754e3d64c9e6`；尚未烧录。
  Mac 安装首次因涉及常驻 LaunchAgent、Typeless 配置修改和全局按键辅助功能权限而被安全
  审查拦下；Alice 随后明确授权。当前已备份并写入 Typeless 的 `Fn + Ctrl/Cmd/Shift/Space`
  双入口、安装稳定路径的 `TypelessKeySender.app`、重装 Dashboard/音频 LaunchAgent；真实
  用户环境复核 `accessibility_trusted=true`，Bridge `/healthz` 返回 200。未主动触发听写，
  避免向 Alice 当前焦点窗口注入内容。Alice 随后明确“更新麦克风图标连接修复 + Typeless
  启停动作”，固件由应用端口自动切换至 `/dev/cu.usbmodem2101`，完成 `ota_0 / 0x20000`
  写入并通过 Flash 数据哈希校验；设备恢复 `/dev/cu.usbmodemM5DASHMIC31`，Bridge 收到正常
  硬复位诊断 `reason=1 stage=0 page=7` 并重新完成 Token 鉴权。真实用户环境再次确认 helper
  授权有效、Bridge TCP 8765/UDP 8766 均监听且 `/healthz` 返回 200；等待 Alice 触屏完成首次
  端到端听写验收。
- 首次端到端验收暴露两个独立问题。其一，Bridge 在 Typeless 尚未运行时先后台打开应用、
  随即发送快捷键，应用界面虽已出现但全局快捷键尚未注册，因此没有进入听写；现改为仅在
  进程缺席时启动，确认进程出现并等待 1 秒就绪后再发送，停止动作也不会为了停止而反向
  打开 Typeless。其二，固件把 Typeless `LIVE` 误归为深色全屏 overlay，466 px 外框被填成
  黑色，而 450 px 编辑式内页仍是纸白，形成顶部与左侧约 8 px 黑色切割；现将 LIVE 外框
  改为纸白并继续绘制珊瑚强调圆。140 项主测试、独立 C++ 交互测试、JSON、补丁洁净检查及
  UAC PlatformIO 构建全部通过；Mac Bridge 已更新并由 `/healthz` 确认在线，未主动触发
  Typeless。候选固件为 4,931,248 bytes，SHA-256 为
  `6e057620126c68b7610ea6e39d4f36398bec3cc7665fea42ac28f55fde7f2662`。Alice 明确“更新”后，
  固件由应用端口自动切换至 `/dev/cu.usbmodem2101`，完成原厂 `ota_0 / 0x20000` 写入并通过
  Flash 数据哈希校验；设备恢复 `/dev/cu.usbmodemM5DASHMIC31`，Bridge 收到正常硬复位诊断
  `reason=1 stage=0 page=7` 并重新完成 Token 鉴权，`/healthz` 返回 200。等待 Alice 实机复验
  首次轻触进入听写，以及 LIVE 页顶部、左侧画布是否完整。
- Alice 复验确认 LIVE 页外框黑色切割已解决，但首次轻触仍未进入听写。新增不含 Token 的
  USB 动作收据后，实机证明确有 `typeless-start` 抵达 Bridge；上一条“UAC/CDC 动作丢失”
  假设被证伪。真正失败点是 Mac 后台 LaunchAgent 直接执行未完整签名的 helper 时，macOS
  TCC 返回 `accessibility_trusted=false`；从 Codex 前台环境得到的 `true` 属于责任进程继承，
  不能代表 helper 自身授权。安装器现改为先生成完整 App Bundle，再以独立 Bundle ID
  `studio.machiwhale.m5stopwatch.typeless-key-sender` 做 ad-hoc 整包签名；同时 Bridge 把
  Typeless 切换快捷键封装为幂等 start/stop，避免 start 失败后 stop 反向开启听写，并记录
  `received / completed / failed` 三段收据。针对该 Bundle ID 清理旧签名 TCC 记录、由签名
  App 重新登记并由 Alice 开启后，LaunchServices 收据变为 `accessibility_trusted=true`，
  真实 LaunchAgent Bridge 的 `/api/typeless/start` 返回 200，证明手动 Bridge 路径可进入听写。
  随后的手表动作虽记录 `received / completed`，却没有第二条 `shortcut sent`；Alice 指出手表
  并未真正打开听写。根因是手动测试已把 Bridge 内部 active 置真，幂等逻辑误把手表 start
  当作重复动作跳过。上一条“手表端到端 Owner PASS”判断撤回，当前仅确认手动 Bridge 路径
  PASS；Bridge 已重启清空测试状态，等待纯手表路径重新验收。
- 实体设备已稳定识别为 `/dev/cu.usbmodem2101`，USB `303A:1001`，序列号
  `28:84:85:44:6A:D8`。
- 首次尝试写入 4,546,928 bytes 后返回 `Hash of data verified`，但黑屏；串口启动日志随后证明
  原厂分区为 `nvs 0x9000`、`ota_0 0x20000/0x4f0000`、`ota_1 0x510000/0x4f0000`，并明确
  报告 `image at 0x20000 has invalid magic byte` 与 `No bootable app partitions`。
- 根因是旧烧录脚本沿用 `0x10000` 假设，使固件相对 `ota_0` 错位 64 KiB；不是显示硬件、
  UI 或固件编译失败。NVS、bootloader 和 partition table 均未被写入，个人配置区未受影响。
- 烧录脚本已改为 `0x20000`，并加入 `0x4f0000` 分区容量保护；第二次 Download Mode 写入
  4,546,928 bytes 后哈希校验通过，设备由 ROM 端口重新枚举为
  `/dev/cu.usbmodemM5DASHMIC31`（`M5 StopWatch Mic`），证明当前应用已启动。
- Alice 真机确认本地 Stopwatch 功能语义正常，但指出图形锯齿明显、动画不够丝滑。软件侧
  已完成第二版视觉/性能修复：专用 56 px Noto 8-bit alpha 数字字体、平滑圆角、360 × 78
  局部画布 50 FPS 刷新，并在运行期间维持 240 MHz，避免 15 秒后降至 80 MHz。新版
  4,585,104 bytes，小于原厂 `ota_0` 的 5,177,344 bytes；已通过应用端口自动进入 Download
  Mode、写入 `0x20000`、Flash 哈希校验并重新枚举为 `M5 StopWatch Mic`，等待真机视觉比较。
- Alice 确认第二版的分辨率和动画明显改善，但运行时数字行偶发向上跳。根因是
  `middle_center` 会按当前整串字形包围盒居中，而数字字形顶部存在 1 px 差异；同时首帧与
  局部刷新帧原来相差 3 px。当前候选版改为共用固定的全局 baseline `Y=226`，不改变计时
  逻辑或 50 FPS 刷新；110 项测试、独立 C++ 测试与 UAC 编译通过，尚未烧录，等待 Alice
  确认更新。
- Lap 仍最多保存 24 条、屏幕每页显示 3 条。Alice 确认增加列表区域翻页：上滑一页查看
  更早 Lap，下滑一页返回更新 Lap；5 条记录时从 `LAP 3–5` 上滑可直接看到 `LAP 1–3`。
  新增 Lap、复位或重新进入 Stopwatch 时自动跟随最新页；到达最早/最新边界有轻震反馈，
  页脚按当前位置提示上滑或下滑。该功能与固定 baseline 合并后，111 项测试、独立 C++
  测试和 UAC 编译通过；4,585,568 bytes 固件已写入 `ota_0` 的 `0x20000` 并通过 Flash
  哈希校验，设备重新枚举为 `M5 StopWatch Mic`，等待 Alice 真机复验。
- Alice 真机确认数字行跳动与 Lap 翻页均已解决，同时指出“下滑返回最新 · 电源键返回”
  下沿贴近圆屏弧线。测量后确认 `Y=420` 时长文案两端下沿仅余约 0–1 px；当前候选版保持
  字号和居中，将页脚整体上移 12 px 至 `Y=408`。111 项测试、独立 C++ 测试与 UAC 编译
  通过；4,585,568 bytes 固件已写入 `0x20000` 并通过 Flash 哈希校验，设备重新枚举为
  `M5 StopWatch Mic`，等待 Alice 真机复验页脚安全区。
- Alice 复验确认上移后下沿仍固定缺失 1–2 px，证明上一条“仅圆屏边缘裁切”的判断不完整。
  根因改判为 M5GFX 对 16 px VLW 字体执行 `0.9×` 非整数缩放时会丢弃部分源像素行；当前
  候选版保留安全位置 `Y=408`，将页脚改为原生 `1.0×` 像素映射，原生宽约 199 px，仍在
  圆屏安全区内。111 项测试、独立 C++ 测试和 UAC 编译通过；4,585,568 bytes 固件已写入
  `0x20000` 并通过 Flash 哈希校验，设备恢复 `M5 StopWatch Mic` 身份，等待 Alice 复验。
- Alice 真机确认原生 `1.0×` 页脚下沿已经完整；本地 Stopwatch 的数字稳定性、Lap 翻页与
  页脚安全区均通过 Owner 复验。Stopwatch 本轮视觉与交互修复闭环，接下来转入 Dashboard
  七屏 App 真机验收。

此前“底层依赖下载停滞、尚未生成 firmware.bin”的状态已经解决，保留为一次构建环境
历史，不再代表当前软件状态。

## 七屏功能总览

| 屏幕 | 目的 | 主要数据与后端 | 主要交互 | 当前最终呈现 | 状态 |
|---|---|---|---|---|---|
| 1. 时钟总览 | 一眼查看时间与工作状态 | Mac 校时、Open-Meteo、设备电量、TickTick、Multi AI Usage Monitor | `星盘`查看运行任务；`成果`查看今日完成项 | 暖白底、珊瑚圆、超大时间、日期天气、电量、`专/AI`紧凑状态条 | 已实现、软件验证；待真机 |
| 2. TickTick 专注 | 统一控制正计时与 25 分钟倒计时 | 复用 Stick S3 的本机 TickTick Focus Bridge | A 单击正计时开始/暂停/继续，双击结束；B 对倒计时执行同样操作；屏内可触摸 | 当前计时为主视觉，A/B 模式条与开始/暂停/继续、结束按钮清晰分离 | 已实现、软件验证；待 StopWatch 真机 |
| 3. Codex | 查看工作状态与额度 | Codex Hooks、本地任务状态、用量与可选对话摘要 | 轻触 Codex 图标查看活动任务详情 | 蓝紫强调、真实 Codex 图标、剩余额度、今日/累计用量、任务或重置状态 | 已实现、软件验证；待真机与真实账户联调 |
| 4. Claude | 查看工作状态与额度 | 本机 Claude 日志或明确配置的伴随 Bridge | 轻触 Claude 图标查看活动任务详情 | 橙色强调、真实 Claude 图标、剩余额度、今日/累计用量、任务或重置状态 | 已实现、软件验证；待真机与真实数据联调 |
| 5. Typeless | 把 StopWatch 作为 Mac 的 USB 麦克风 | 设备 ES8311 麦克风、48 kHz 单声道 UAC1 | 轻触中央开始/停止设备侧收音 | `READY / LIVE / ERROR`、麦克风图标、实时波形、峰值 dBFS、单一触摸动作 | 已实现、固件编译；待真机枚举与音质验证 |
| 6. AI 热点尖叫 | 只为真正重要且与 Alice 相关的 AI 事件报警 | Codex Resets、AIHOT、官方信源三路汇聚 | `知道了`确认；`打开`在配对 Mac 打开原文；新尖叫自动切页 | 爆发图形、两行标题、来源与时间、声音/震动状态、确认/打开 | 正式后端已实现、软件与在线冷启动验证；待真机 |
| 7. Obsidian 幸运笔记 | 从授权知识库随机重遇一篇笔记 | Mac 本地扫描明确授权的 Markdown 根目录 | `打开文档`、`再摇`、轻触骰子或晃动设备重新抽取 | 黄色圆与骰子、可抽数量、笔记标题、来源文件夹、打开/再摇 | 已实现、软件验证；待真机与真实 Vault 联调 |

当前七屏视觉预览：`design/stopwatch-ui-preview.png`。七屏统一使用暖白底、黑色主信息、
明快的珊瑚红/黄色及各 Provider 品牌强调色，并以 466 × 466 圆屏安全区为硬约束。

## 全局交互契约

- 开机进入双程序选择器：A 选中 `Dashboard`，B 选中 `Stopwatch`，轻触选中的程序卡进入。
- Dashboard 是下述七屏工作台；本地 Stopwatch 是独立程序，不会控制 TickTick。
- 左右滑动依次切换 7 屏。
- A/B 专注按键是全局动作，不受当前页面限制；执行后自动切到第 2 屏反馈。
- A 单击控制正计时，A 双击结束；B 单击控制 25 分钟倒计时，B 双击结束。
- 单击等待约 360 ms，以区分双击；正计时与倒计时互斥，启动其中一个会先暂停另一个。
- A 长按 0.8 秒打开 Wi-Fi 选择；B 长按 0.8 秒回到第 1 屏且不改变计时状态；A+B
  长按 2.5 秒进入配网。
- 屏幕两侧纵向滑动分别调节亮度和提示音量。
- 红色电源键短按熄屏/唤醒；双击从任意页面进入程序选择器；长按在未接 USB 时关机。
- 接 USB 时不由软件截获电源键长按，保留原厂 PMIC 的约 2 秒 Download Mode 入口。
- 熄屏关闭 AMOLED、触控与麦克风；Wi-Fi、Bridge 监听、扬声器通知能力和震动保持可用。
  熄屏期间收到新 AI 热点会立即播放尖叫并震动，同时登记待处理唤醒路由；下一次短按
  唤醒自动进入第 6 屏。双击进入程序选择器属于显式选择，会覆盖这条自动路由。
- USB 是首次烧录、救援和 Alice 日常使用的默认通道；Wi-Fi 与双网络自动选择是可选能力，
  未配置 Wi-Fi 时 Dashboard 仍会正常进入并等待 USB Bridge。

## USB-first 连接契约

- Mac 安装器在首次安装时生成 32-byte URL-safe 随机 Token，保存于权限 `0600` 的本机
  `config.json`；仓库与固件镜像都不内置个人 Token。
- 未配对设备通过物理 USB CDC 发送设备 ID，Mac Bridge 只在该串口回传 Token；设备验证
  Token 格式后写入 NVS，随后所有取数和动作仍按既有 Token 鉴权。
- 设备保留两个 Mac Token 槽：全新设备自动使用第一个；插到第二台 Mac 且旧 Token 被拒绝
  时，只写入空槽。两个槽均满时不会自动覆盖，避免静默丢失已有电脑。
- 没有 Wi-Fi 配置不是错误，也不会自动打开热点。A+B 长按 2.5 秒仍是显式配网入口；已保存
  Wi-Fi 的设备继续保留局域网发现与自动漫游，不影响朋友原来的无线使用方式。
- USB 配对的信任边界是“本机用户可访问的物理串口”。Token 不经公网或临时热点传输；拔线后
  USB 数据通道自然断开。

## 各屏判断规则与呈现契约

### 第 1 屏：时钟总览

显示 24 小时制时间、日期、天气、温度、电量与充电状态。时间由 Mac Bridge 校时后在
设备本地平滑推进；天气来自配置城市的 Open-Meteo；设备电量直接读取本机电源状态。

底部紧凑状态条表示：

- `专`：当前 TickTick 专注进度。倒计时按完成比例计算；正计时以 90 分钟作为满进度参考。
- `AI`：当天 Coding AI Token 总处理量，格式如 `AI518M`。数据来自本机
  本机 Multi AI Usage Monitor 的 `/api/token-series`，包含
  Claude Code、Codex、Kimi Code、DeepSeek、OpenRouter 与 Grok；Cursor、Antigravity
  暂无 Token 序列，不计入。口径为 input + output + cache read + cache write。

Bridge 同时保留不含 cache 的 `today.auth`、四类 Token 拆分和逐 Provider 明细。当天来源
不完整时首屏显示 `AI--`，不把部分总量当完整值；Grok 当天有数据时因其日志是上下文快照
近似值，首屏在数值前显示 `~`。Codex 与 Claude 的额度快捷信息不再挤在首屏状态条，分别
保留在第 3、4 屏。

当前跨 Provider 没有可共享的 request id，因此总量默认各渠道互不重叠。如果未来某个
Coding Agent 同时把同一次请求记入自己的本地日志和 OpenRouter analytics，可能发生重复
计数；遇到这种接法时应在 Multi AI Usage Monitor 上配置排除渠道，不能在手表端猜测去重。

`星盘`汇聚当前 TickTick、Codex、Claude 运行任务，轻触任务可进入详情；`成果`汇聚当天
已完成的 Codex/Claude 任务，以可随设备倾斜、晃动的成果球呈现，轻触可看摘要。

旧版“三段深色外圈”描述已经被当前暖白编辑式总览替代，现行固件使用紧凑状态条。

### 第 2 屏：TickTick 专注

正计时用于不预设时长的长任务；倒计时固定为 25 分钟。两种计时共享同一套开始、暂停、
继续与结束语义，但不能同时运行。

- A 单击：正计时开始 / 暂停 / 继续。
- A 双击：结束正计时并保留本次用时反馈。
- B 单击：25 分钟倒计时开始 / 暂停 / 继续。
- B 双击：结束倒计时并回到 25:00。
- B 长按 0.8 秒：从任意页面回到第 1 屏时间总览，不开始、暂停或结束倒计时。
- 触摸主按钮直接执行当前模式的开始/暂停/继续；触摸`结束`直接结束。

后端复用已经在 Stick S3 上验证过的 `http://127.0.0.1:8787` TickTick Focus Bridge。
正计时控制仍可能依赖 macOS UI 自动化；倒计时开始可同步 TickTick，暂停/继续/结束的
准确边界继续以该 Bridge 的实际能力为准。

### 第 3、4 屏：Codex 与 Claude

两屏共用同一信息层级，但保留各自真实品牌图标与色彩：

- 顶部状态：离线、当前空闲、正在工作、等待确认、需要检查。
- 主值：优先显示本周剩余额度；若 Codex 只有短窗口数据，则显示五小时剩余额度。
- 次级值：今日 Token 与累计 Token。
- 底部：活动任务数量、等待/异常提示，或紧凑重置倒计时 `↺3d8h`。
- 有活动任务时轻触 96 × 96 Provider 图标进入详情。

隐私默认值保持 `expose_titles: false` 与 `expose_transcript: false`。只有 Alice 明确开启后，
才展示可见的用户/助手文本；不转发推理、工具输入、工具结果、浏览器 Cookie 或 Keychain。

### 第 5 屏：Typeless USB 麦克风

StopWatch 自身采集麦克风 PCM，并通过 USB UAC1 以 48 kHz、16 bit、单声道输入设备提供给
Mac；同时经已鉴权的 USB Bridge 调用 Mac 端原生快捷键，让一次轻触完成 Typeless 启停，
不再要求用户先手动打开 Typeless。

- `READY`：USB 音频可用但未收音。
- `LIVE`：正在采集并向 Mac 发送，显示实时波形与峰值。
- `ERROR`：麦克风或 USB 音频启动失败，轻触可重试。
- 轻触中央区域切换开始/停止：首次启动 Typeless 时等待应用就绪后触发听写，后续不抢当前
  输入窗口焦点；B 键不再控制 Typeless，已经专用于倒计时。

麦克风与扬声器共享音频电源轨；固件已包含启停与资源释放处理，但必须在真机验证枚举、
Typeless 识别、底噪、音量、连续录音和停止响应。

### 第 6 屏：AI 热点尖叫

#### 旧链路原型（已替代）

第一版 `AIHotspotMonitor` 每 60 秒轮询 OpenAI News 与 Google AI RSS，首次只建立基线，
之后用标题关键词寻找新条目。它完成了 HTTP/USB 状态同步、自动切页、650 ms 震动、
`知道了`和`打开`的链路验证。

这个原型证明了“抓取 → Bridge → 设备尖叫 → 确认/打开”的完整链路，但标题关键词不是
最终的热点判断系统。Google 的宽泛 Feed、`Agent/发布/上线`等单词都可能导致误报。

#### 已实现的正式后端

当前正式版本已经改为三路汇聚：

1. **Codex Reset 专线**：读取 <https://codex-resets.com/api/v1/status>。
2. **AIHOT 发现线**：首次读取 `/api/v1/selected/snapshot`，后续使用
   `/api/v1/selected/changes`；`/api/v1/hot-topics`只作为多源热度佐证。
3. **官方信源线**：OpenAI、Anthropic、Google DeepMind/Gemini、DeepSeek、Kimi/Moonshot，
   以及 Alice 明确关心的官方 Changelog、Status、社交账号和模型仓库。

所有线路先标准化、去重、检查时效，再进入本地判断。AIHOT 的分数、摘要和推荐理由只是
输入，不是最终裁决；第三方热点没有官方原文时不能直接升级为最高级尖叫。

#### 分级规则

| 等级 | 判断 | 设备行为 |
|---|---|---|
| `scream` | Codex 确认重置；旗舰模型或 Codex/Claude Code 重大上线；DeepSeek/Kimi 新模型及多模态/视觉模型正式上线；价格、额度、访问权、重大故障或安全事件 | 自动切第 6 屏、声音、震动 |
| `alert` | 与 Alice 高相关的新能力；AIHOT 高相关精选但尚不足以成为最高级事件；Codex Reset `strong` 预测 | 不抢最高级语义，以震动/亮屏和待处理提示为主 |
| `inbox` | 教程、观点、论文、融资、合作、普通产品更新 | 只累计角标或进入稍后查看队列 |

Codex Resets 的确认规则：

- 首次读取只保存 `latest_reset.id`，不为历史记录尖叫。
- `latest_reset.id` 出现新值时，无条件生成 `scream`。
- `active_watch.level=strong` 只生成 `alert`；`elevated`只进入角标。
- `active_watch` 是 AI 预测，不得呈现为 OpenAI 已经确认重置。
- 页面显示来源为 `Codex Resets / @thsottiaux`，保留公告原文链接。

AI 新闻优先关注：Codex、OpenAI、GPT、Claude、Claude Code、Anthropic、Gemini、
Google DeepMind、DeepSeek、Kimi/Moonshot、ChatGPT Work、Agent/MCP/Coding Agent，
以及新模型、多模态/视觉能力、相关额度、价格、套餐、
可用地区与服务故障。`Agent`等宽泛实体词不能单独触发尖叫，必须与重大事件词和可信
来源组合。

正式轮询使用 `ETag`、`304`、`Retry-After`与指数退避，并维护逐信源健康状态、事件
队列、跨源去重和撤选处理。Bridge 未运行时不能推送，这是当前本地优先架构的明确边界。

上述网络与状态规则已经写入后端：AIHOT 遵循 snapshot → changes 游标合同，并能在
`409 snapshot_required` 时重建基线；同一原文 URL 或同标题时间窗会合并；AIHOT 撤选会
把对应事件撤回。事件队列持久化在本地状态文件，最多保留配置数量；只有未确认的
`scream`会映射为旧固件兼容字段 `active=true`，`alert/inbox`只进入队列和计数，不会误叫。

统一事件契约：

```json
{
  "kind": "codex_reset | ai_news",
  "severity": "scream | alert | inbox",
  "title": "Codex 额度已重置",
  "summary": "预计将在一小时内到账",
  "reason": "检测到新的确认重置公告",
  "source": "Codex Resets",
  "url": "https://...",
  "published_at": "...",
  "event_id": "..."
}
```

### 第 7 屏：Obsidian 幸运笔记

Bridge 只扫描 `obsidian.roots` 明确授权的 Markdown 根目录。默认根目录是
`~/Smart Workspace`，默认硬排除 `Alice Writing`、隐藏目录、`.obsidian`、`.trash`、
`.git` 和 `node_modules`；不得因为“随机笔记”扩大私人内容边界，frontmatter
`lucky: true` 也不能绕过这些边界。

- 默认每 15 分钟重建一次可抽索引，最多扫描 5000 个 Markdown 文件。
- 标题优先读取 frontmatter `title`，其次一级标题，最后使用文件名。
- 核心洞察池权重 4：`Insights`、`Machiwhale Studio`、`Alice兴趣研究`、`Tech History`、
  `妙蛙种子进化史`，池内目录等权。
- 灵感探索池权重 1：`妙蛙种子收藏夹` 1、`Newsletter Digests` 0.8、`HCI arXiv` 0.6、
  `rabbitT dream` 0.35、`Codex Report` 0.25；后两项按 Alice 的决定降低出现概率。
- `RabbitT Creation`、自动缓存、日报、Memory 与草稿因不属于任何池而默认不入选；其中
  非私人目录的单篇笔记可通过 `lucky: true` 加入“手动精选”。
- 抽取顺序固定为“池权重 → 目录权重 → 目录内笔记”，不会让大目录用文件数量吞没小目录。
- 最近 30 篇写入本地状态并跨 Bridge 重启冷却；目录内优先从最久未出现的一半中随机。
- frontmatter `lucky: false` 可排除单篇；`lucky: true` 可把非默认且非硬排除目录的单篇加入
  “手动精选”。
- `打开文档`调用 Mac 上的 Obsidian 打开已选文件。
- 在第 7 屏轻触骰子或晃动设备也可重抽；900 ms 冷却避免连续误触发。
- Bridge 只向设备发送标题、相对来源文件夹、所属池与入选原因，不发送正文摘录或 Vault
  绝对路径；页面当前显示可抽数量、标题与相对来源文件夹。

## 本轮加固

- 安装器不会再自动打开 Codex/Claude 对话内容展示；需要时由本人显式开启。
- `--all` 会先检查 Typeless 设置、JSON 和音频助手构建条件，避免修改 hooks 后才失败。
- 缺少被 Git 忽略的预编译音频助手时，安装器会从 `mac/M5AudioInput.c` 现场构建。
- 根目录 `scripts/check_ready.py` 会检查两个桥接测试集、配置 JSON、macOS 音频助手，
  并可选择编译普通或 UAC 固件。
- 删除 P2S/Bambu Cloud 监控、凭据安装与打印机页面；第二页改为 TickTick 专注。
- A 单击控制正计时、双击结束；B 单击控制 25 分钟倒计时、双击结束。
- 复用 Stick S3 已验证的 TickTick 本机服务；Dashboard 新增带认证的 HTTP/USB 动作代理。
- 时钟、TickTick、Codex、Claude 与 Typeless 迁移到统一的暖白编辑式圆屏视觉。
- Codex 与 Claude 使用真实品牌图标，第 5 屏确定为 StopWatch UAC Typeless 麦克风。
- 增加第 6 屏 AI 热点尖叫和第 7 屏 Obsidian 幸运笔记，并完成软件侧交互闭环。
- 增加开机程序选择器与独立本地 Stopwatch；秒表采用原厂 A/B 语义并保留 USB 下载模式。
- 将朋友底座的 Wi-Fi-first 首次启动改为 Alice 的 USB-first：增加物理 CDC 自动配对、安装器
  随机 Token、USB-only NVS 保存和双 Mac 空槽策略；A+B 显式配网与既有 Wi-Fi 漫游保留。

## 决策与变更台账

### 2026-08-21

- 以朋友的开源 Dashboard 为底座建立 Alice 分支，保留可追溯的上游基线。
- 删除 3D 打印机监控；Alice 没有 3D 打印机，不为无关硬件保留产品入口。
- 第 2 屏确定为 TickTick 专注，采用 A 正计时、B 25 分钟倒计时、双击结束的全局契约。
- 第 5 屏确定为 Typeless，使用 StopWatch 设备麦克风通过 48 kHz UAC1 输入 Mac。
- 完成七屏统一视觉、真实 Provider 图标、圆屏安全区与软件构建验证。
- 复用现成 Multi AI Usage Monitor 作为首屏“今日 Coding AI 总 Token”统一来源；首屏采用
  含 cache 的总处理量，Bridge 另外保留不含 cache 口径和逐 Provider 明细，并对缺源与
  Grok 近似值明确降级。
- AI 热点当前 RSS 关键词实现被定义为链路原型，不作为最终判断系统。
- Alice 批准“Codex Reset 专线 + AIHOT 发现线 + 官方信源线”的正式后端方案，并确认
  Codex 额度重置属于最高级尖叫事件。
- 正式后端实现完成：加入确定性分级、持久化队列、逐源健康、ETag、退避、AIHOT
  snapshot/changes/撤选与 409 重建、Codex Reset 基线/预测边界和跨源去重；91 项主测试通过。
- 使用临时状态文件完成真实在线冷启动，五项远程入口全部成功，且没有把历史记录当新警报。
- 第 7 屏随机契约确定并实现：`RabbitT Creation` 禁入；`rabbitT dream`、`Codex Report`
  以低权重加入灵感探索；采用两级权重、30 篇持久冷却、久未访问优先和 frontmatter
  单篇覆盖，同时取消正文摘录下发；主测试总数更新为 96 项。
- 修订 `RabbitT Creation` 边界：上一条“禁入”决定被替代为“默认不抽”，允许 Alice 对
  单篇笔记设置 `lucky: true` 后加入手动精选；`Alice Writing` 继续永久禁入。
- B 键长按 0.8 秒确定为全局“回到时间首页”；B 单击/双击倒计时语义保持不变。102 项
  主测试、独立 C++ 交互测试与 UAC 固件重新编译通过。
- 增加双程序选择器，保留 Dashboard 七屏并恢复独立的原厂风格 Stopwatch：静止时 B 开始；
  运行时 A 记圈、B 暂停；暂停时 A 复位、B 继续。原“电源键单击待机、双击关机”方案被
  替代为“短按返回程序选择器、未接 USB 时长按关机”；接 USB 长按继续用于 Download Mode。
- 新应用壳层纳入主测试和独立 C++ 状态机测试；UAC 固件重新编译成功。实体设备已在
  `/dev/cu.usbmodem2101` 唯一识别。
- Alice 确认 Download Mode 绿灯后，首次真机写入的数据哈希校验成功，但设备黑屏；串口
  诊断确认原厂 `ota_0` 起点为 `0x20000`，旧脚本的 `0x10000` 写入假设错误。当前已修正
  脚本并增加容量保护，NVS 未受影响。
- Alice 第二次进入 Download Mode 后，固件已从正确的 `0x20000` 写入并通过 Flash 哈希
  校验；watchdog 重启后出现 `M5 StopWatch Mic` 应用 USB 身份，黑屏启动循环已解除。
  Alice 随后确认圆屏已出现“选择程序”界面，应用启动、显示和选择器首屏获得 Owner
  真机确认；触摸、A/B、电源键与 UAC 体验继续逐项验收。
- Alice 确认 Stopwatch 的开始、记圈、暂停、复位与返回交互均可用，但真机视觉未过关：
  边缘锯齿严重、计时动画不够丝滑。根因定位为缩放位图/普通圆角，以及通用省电策略在
  15 秒后把 CPU 从 240 MHz 降到 80 MHz；现已改为原生尺寸抗锯齿数字字体、平滑圆角、
  运行期高性能和 50 FPS 局部刷新。109 项测试与 UAC 编译通过，新版已自动切换下载模式并
  烧录成功；应用 USB 身份恢复正常，等待 Alice 对锯齿和 15 秒后流畅度进行 Owner 复验。
- Alice 确认分辨率和流畅度提升后，发现计时数字行偶发上跳；已定位为动态字形包围盒居中
  与首帧/局部帧坐标不一致，改成固定 baseline `Y=226`。110 项测试、独立 C++ 测试与 UAC
  编译通过；该基线候选版尚未烧录。
- Alice 确认 Stopwatch 的 Lap 列表需要回看入口；当前增加列表区域上滑查看更早三条、下滑
  返回更新三条，新增 Lap 自动回到最新，并为翻页边界提供轻震反馈与页脚提示。与固定基线
  合并后的候选固件通过 111 项测试、独立 C++ 测试和 UAC 编译；已从正确的 `0x20000`
  写入并通过 Flash 哈希校验，应用 USB 重新枚举成功，等待 Owner 真机复验。
- Alice 真机确认固定基线和 Lap 翻页通过，但页脚长文案下沿被圆屏边缘轻微切掉；候选修复
  保持字号不变，把页脚从 `Y=420` 上移至 `Y=408`，编译与既有 111 项测试通过；已写入
  正确的 `0x20000`、通过 Flash 哈希校验并恢复应用 USB 身份，等待 Owner 真机复验。
- 上移后的真机复验仍缺失同样的 1–2 px，下沿问题改判为 VLW 字体 `0.9×` 非整数缩放丢行；
  新版使用原生 `1.0×` 绘制并保留 `Y=408`，既有 111 项测试与 UAC 编译通过；已写入正确
  的 `0x20000`、通过 Flash 哈希校验并恢复应用 USB 身份，等待 Owner 真机复验。
- Alice 真机确认页脚下沿完整；固定数字基线、Lap 上下滑翻页及页脚原生像素绘制全部通过
  Owner 复验，本地 Stopwatch 本轮关闭，转入 Dashboard 七屏 App 真机验收。
- Alice 进入 Dashboard 后遇到朋友底座的首次强制配网，并明确选择改成自己的 Mac 直连
  习惯。当前已实现 USB-first 候选：无 SSID 时不再自动开热点，固件通过物理 CDC 自动取得
  安装器生成的本地 Token 并写入 NVS，保留两个 Mac Token 槽且不自动覆盖已满槽位；A+B
  仍可主动进入 Wi-Fi 配网。主工程 115 项、伴随桥接 23 项、独立 C++ 测试与 UAC 固件编译
  通过。Mac 常驻 Bridge 随后已安装并通过健康、权限与 USB 串口打开检查。
- Alice 确认“更新”后，4,587,920-byte USB-first 固件已从正确的 `0x20000` 写入并通过
  Flash 哈希校验，设备重新枚举为 `/dev/cu.usbmodemM5DASHMIC31`。Bridge 日志确认设备
  `M5-D86A44858428` 首次自动配对并随即完成 Token 鉴权；Bridge 再次重启后设备无需配对即可
  直接鉴权，证明 Token 已持久保存。`/healthz` 返回 200，Mac 常驻服务保持运行。
- 真机更新后的联网验证发现一次官方 RSS 分块传输中断会退出 AI 热点线程；已将
  `http.client.HTTPException` 收敛为单源失败、指数退避和下轮重试，不影响其他 Bridge
  能力。新增回归测试后主工程更新为 116 项通过，Mac Bridge 已重装生效，错误日志未新增。
- Dashboard 首屏真机验收暴露字体、右侧图形边缘、Provider 重置、Claude 离线和 Typeless
  麦克风五项问题。当前候选用原生字号 Noto 子集取代非整数缩放，frameCanvas 补齐强调圆
  外延，麦克风按设计 SVG 重绘；重置字段接入 Multi AI Usage Monitor 的 `/api/quota`，
  缺值时显示“重置待同步”。朋友 iMac 示例源已由安装器迁移为 Claude 本地在线模式。
  Bridge 已更新并实测 Codex/Claude 官方配额均在线；120+23 项测试、独立 C++ 与 UAC 构建
  通过。Alice 确认“更新”后，4,878,656-byte 固件已从正确的 `0x20000` 写入并通过 Flash
  数据哈希校验；应用重新枚举为 `M5 StopWatch Mic`，Bridge 客户端重新认证成功，等待
  Owner 真机视觉复验。
- Alice 复验确认文字平滑、整体已接近设计稿；新发现的强调圆锯齿改用 M5GFX 平滑圆，二级
  全屏页改为清除 466 px 外框强调色，Codex/Claude 品牌图标改为构建时生成 RGB565，以移除
  与 Codex 切页重启时机相符的运行时 PNG 解码路径。122+23 项测试、独立 C++ 与 UAC 构建
  通过。Alice 确认“更新”后，4,913,248-byte 固件已写入正确的 `0x20000`、通过 Flash
  数据哈希校验并恢复应用 USB 身份与 Bridge 鉴权，等待真机复验三项问题。
- Codex 重启仍可复现，上一轮 PNG 根因假设被真机证伪。由于 UAC 通道收不到 ROM panic，
  当前改用 RTC 阶段标记与三整数 USB 诊断协议；诊断固件已烧录且 Bridge 收到正常启动基线，
  等待下一次复现给出 reset reason 与最后渲染阶段。
- 诊断复现得到 `reason=4 stage=0 page=7`，将根因收敛为整页切换完成后的 Provider 图标局部
  多目标刷新。修复已将图标改为静态随整页合成，保留任务完成全屏动画；125 项测试、独立
  C++ 与 UAC 构建通过，固件已写入并恢复应用 USB/Bridge 鉴权，等待 Alice 真机复验。
- 静态图标修复版仍以相同 `reason=4 stage=0 page=7` 重启，上一条根因判断被实机证伪。
  二次诊断版已把阶段标记细化到切页返回后与主循环各模块，构建通过但尚未烧录。
- 建立本 `PROJECT.md` 功能、判断、呈现、验证与决策台账；后续变更按日期追加，旧判断
  被替代时保留历史并明确标注。

### 2026-08-22

- Typeless 已由单纯 USB 麦克风升级为“UAC 收音 + Mac 原生快捷键启停”的一触链路；首次
  真机验收进一步修正应用启动与快捷键注册竞态，并把 `LIVE` 从深色全屏 overlay 分类中
  移除，消除 450 px 内页外侧的黑色画布切割。Mac Bridge 修复已上线并健康，固件已写入
  正确的 `ota_0 / 0x20000`、通过 Flash 哈希校验并恢复 USB/Bridge 鉴权，等待实机复验。
- Typeless 动作收据证实 USB 传输正常，最终根因是未完整签名的 helper 在 LaunchAgent
  责任进程下无法命中 macOS TCC。安装器已加入独立 Bundle ID 整包签名，Bridge 已加入
  幂等启停与安全收据；清理并重新登记该 Bundle ID 权限后，手动 Bridge 听写成功。Alice
  随即纠正：手表 start 被手动测试残留的 active 状态错误跳过，尚未获得端到端 PASS；Bridge
  已重启清空状态，等待纯手表路径复验。
- Bridge 干净重启后，纯手表路径取得 `typeless-start received -> shortcut sent -> completed`
  完整收据，Alice 真机确认已成功呼出 Typeless；录音输入同时确认来自 StopWatch 通过 USB
  暴露的 `TinyUSB UAC1`，而非 MacBook 内置麦克风。当前仅 start 获得 Owner 真机确认，完整
  start/stop 闭环仍待下一版复验。
- Alice 点击 Typeless 页底部黑色胶囊未能结束，Bridge 日志中没有收到 `typeless-stop`；根因
  精确定位为视觉胶囊 `Y=344..396` 位于原中央触控区 `Y=94..340` 之外，并非 Mac 快捷键或
  USB 链路故障。当前候选把中央区和页脚胶囊作为两个独立安全触控区的并集，避免扩大为越出
  圆屏安全区的大矩形；142 项主测试、独立 C++ 交互测试与 UAC 固件构建均通过，仍需烧录和
  Owner 真机确认。此次未响应的听写已由 Bridge 补偿发送 stop，日志确认快捷键已发出。
- Alice 授权“更新”后，4,931,264-byte Typeless 页脚触控修复固件已写入正确的
  `ota_0 / 0x20000`，Flash 数据哈希校验通过；设备重新枚举为 `M5 StopWatch Mic`
  `/dev/cu.usbmodemM5DASHMIC31`，Bridge `/healthz` 返回 200，日志确认正常重启
  `reason=1 stage=0 page=7` 并重新鉴权。软件与部署验证已完成，等待 Alice 依次真机复验
  “轻触开启 -> Typeless 听写 -> 轻触底部胶囊结束”的完整闭环。
- Alice 指出七屏实机底色看起来是纯白，与设计稿略偏黄的纸张暖白不符。核对确认设计源色
  为 `#F8F5ED`，固件此前虽照搬该值，但在 StopWatch 高亮度 RGB565 面板上的实际观感趋近
  中性白；问题改判为缺少真机色彩校准，而非设计稿使用白底。当前候选把所有七屏、Typeless
  LIVE、二级页外围和程序选择器统一收口到 `editorialPaperColor()`，采用轻微增强暖度的
  `#F7F1E2`（RGB565 实际 `248/240/224`）；深色二级页和黑底本地 Stopwatch 保持不变。
  143 项主测试、差异检查与 UAC 固件构建通过。Alice 授权更新后，4,931,264-byte 固件已
  写入正确的 `ota_0 / 0x20000`，Flash 数据哈希校验通过；设备重新枚举为
  `/dev/cu.usbmodemM5DASHMIC31`，Bridge 健康，日志确认正常重启并重新鉴权。部署验证完成，
  等待 Owner 真机判断暖度。同期 Bridge 收据显示上一版 Typeless 已完成一次纯手表
  `start -> shortcut -> completed` 与 `stop -> shortcut -> completed`，但视觉和交互最终结论
  仍以 Alice 明确复验为准。
- Alice 真机判断 `#F7F1E2` 仅能隐约感到变暖，决定再暖一级。新候选仅调整统一纸色常量为
  `#F5EAD6`，七屏、Typeless LIVE、二级页外围和程序选择器同步生效，强调色、深色二级页及
  黑底本地 Stopwatch 不变；143 项主测试、差异检查与 UAC 固件构建通过。Alice 授权更新后，
  4,931,264-byte 固件已写入正确的 `ota_0 / 0x20000`，Flash 数据哈希校验通过；设备恢复
  `/dev/cu.usbmodemM5DASHMIC31`，Bridge 健康并重新鉴权。Alice 真机确认“这回对味了”，
  `#F5EAD6` 正式成为七屏及其暖白外围的 Owner PASS 真机纸色，本轮底色校准关闭。
- Alice 发现时钟总览的“星盘 / 成果”触控区会落到上排“天气 / AI 用量”信息胶囊。核对
  视觉与交互几何后，根因不是整屏触控校准，而是下排视觉按钮 `Y=344..392` 的旧热区被向上
  扩到 `Y=326`，与上排 `Y=282..324` 只剩 2 px 间隔。候选把热区收回为 `Y=340..400`，
  完整覆盖下排并保留少量容错，同时锁定上排中心、下沿及两排间隙均返回无动作；144 项主
  测试、独立 C++ 交互测试、差异检查和 UAC 固件构建通过，尚未烧录。
- Alice 继续验收发现三项独立缺陷：Codex 首页有 3 个活动任务但二级页为空、AI 热点爆发图
  右侧被设计画布直切、Obsidian 计数与“篇可抽”重叠且随机标题乱码、文档无法打开。根因分别
  为 `expose_transcript: false` 直接清空详情数组、280 px 爆发图从 `X=185` 绘制而超出
  450 px 内画布、动态标题误用仅 216 个静态字形的设计字体，以及 Bridge 用异步
  `open -a Obsidian` 在系统确认前就回报成功。候选修复保持隐私默认值不变：最多显示 3 个
  泛化活动任务卡片并明确“对话内容保持私密”，不传真实标题或消息正文；爆发图移到 `X=170`
  使右边界完整落在画布内；Obsidian 数字降为原生 80 px 并拆分计数、说明、标题三行，随机
  标题清理 emoji、零宽字符和长横线后交给完整中文字体；打开动作改用 URL 编码的
  `obsidian://open?path=...` 并同步检查 LaunchServices 结果。已确认本机 Obsidian 注册该
  URL scheme，当前 3 个 Codex 活动任务在隐私模式下全部生成泛化卡片且正文为空；147 项主
  测试、独立 C++ 交互测试、差异检查和 UAC 固件构建通过。候选镜像为 4,931,696 bytes，
  SHA-256 `af4f402970f96180a8551d71a38846e304cb801ee7e98d4f758b6fcc725df85c`；同时包含上一条
  尚未烧录的时钟触控区修复，当前仍未安装 Bridge、未烧录、未做实机复验。
- Alice 用真机照片否证了“把既有 AI 爆发图左移 15 px 即可”的判断：旧 220 px PNG 自身
  的红色内容已经顶到右边界并形成直断面，移动只会把断面一起搬进屏幕。当前候选废弃该
  位移方案，改为构建时以 4 倍超采样生成完整的 300 px 不规则放射图；每条射线尖端都在
  素材内部闭合并保留透明余量，边缘先与 Owner PASS 的 `#F5EAD6` 纸色预混合，再以安全
  出血位置绘制，让超出部分只由圆形表盘自然收边，内部不再出现素材直切线。该素材修复
  已通过边界资产测试、全部 147 项主测试、独立 C++ 交互测试、差异检查与 UAC 固件构建；
  候选镜像为 4,932,240 bytes，SHA-256
  `395facc0ce4c67377cfa793bd0cb8e1f1f3229db5184c6a9b2258d692a88faf6`。尚未烧录，仍需
  Owner 实机视觉复验后才能关闭。
- Alice 在软件圆屏预览中否决了重新生成的 300 px 星芒：虽然消除了素材断边，但规则、均匀
  的放射节奏弱化了原图的失控爆裂感，而且视觉体量仍不够“尖叫”。该候选未部署并立即废弃。
  新方向恢复 Owner 选中的原始不规则素材，在构建期用 Lanczos 预放大为原生 360 px，固件
  以 `X=130 / Y=-35` 绘制；爆心体量由原来的 280 px 增至接近其他页 328 px 强调圆的级别，
  原素材右边界落到内画布外 40 px，由圆形表盘自然遮挡，同时避免设备运行时低质量拉伸。
  Alice 放大预览后继续发现原图放大会暴露像素锯齿，因此最终构建不再直接放大彩色像素：先
  提取原始不规则透明轮廓，以 0.55 px 轻微高斯柔化后用 Lanczos 放大 alpha，再用纯珊瑚红
  重建主体，并在半透明边缘预混 Owner PASS 的 `#F5EAD6` 纸色。这样保留原图不规则射线和
  失控节奏，只重建抗锯齿边缘。该版本通过资产测试、全部 147 项主测试、独立 C++ 交互测试、
  差异检查与 UAC 固件构建；最终镜像为 4,936,592 bytes，SHA-256
  `bdffbae8b0769b9de957a2b901334b329cbe191d389f573dbc73fa9c74a6b1bf`。Bridge 已安装并保持
  健康，固件已写入正确的 `ota_0 / 0x20000`，Flash 数据哈希校验通过；设备恢复为
  `/dev/cu.usbmodemM5DASHMIC31`，Bridge 已重新打开 USB 并完成 Dashboard 鉴权。软件、烧录
  与传输链路验证完成，仍等待 Owner 实机确认尖叫图抗锯齿与构图，以及本轮 Codex 活动卡、
  Obsidian 排版/打开和时钟下排触控四项可见行为。
- Alice 实机复验发现该尖叫图仍有锯齿，且红色图形到物理表圈之间露出纸色；Obsidian 可抽
  数字则显示为三个缺字方框。进一步核对确认是两个新的真机边界：尖叫 PNG 虽已在 450 px
  设计画布中出血，但最终合成到 466 px 物理帧时，外围 8 px 仍只填纸色；此前的透明索引与
  Floyd-Steinberg 抖动也会把预混边缘重新变成可见噪点。骰子调用的 80 px 字体则是专供
  Typeless `READY/LIVE` 的 9 个英文字母子集，完全不含 `0–9`。新候选在 4 倍超采样中将
  原始不规则轮廓直接预混到精确的 `#F5EAD6` 纸色，关闭抖动量化，并在 466 px 外框中再次
  绘制同一素材，使红色真正延伸到物理表圈；骰子改用已经由 Codex/Claude 额度页验证、包含
  数字的 104 px 字体并以 0.76 倍显示为约 79 px。同期 UI session 将第 1 屏从 TickTick 同款
  珊瑚红改为独立的薄荷绿 `#18E5A1`，右上强调图形、电池状态点和 AI 用量点统一使用该绿色；
  本候选已合并这一改动，没有覆盖 UI session 的其他工作。148 项主测试、绿色首页专项回归、
  独立 C++ 交互测试、差异检查与 UAC 固件构建通过；候选镜像为 4,935,872 bytes，SHA-256
  `3beb37da505741cb33cff62eeaeb92eec3ff52897cf33e319b42a028b427b25e`。Alice 授权更新后，
  固件已写入正确的 `ota_0 / 0x20000` 且 Flash 数据哈希校验通过；设备恢复
  `/dev/cu.usbmodemM5DASHMIC31`，Bridge 健康并重新完成 Dashboard USB 鉴权。软件、烧录和
  传输链路验证完成，等待 Owner 实机判断绿色首页、尖叫边缘/贴圈和骰子数字三项可见结果。
- Alice 实机确认薄荷绿首页通过、Obsidian 数字内容恢复，但尖叫与骰子数字边缘仍有锯齿，
  同时 Typeless 再次调用失败。日志确认手表与 USB Bridge 均正常，失败点是后台 Python 直接
  执行 Helper 时被 macOS 判为无辅助功能权限；同一个 Helper App 独立检查却为已授权，且
  系统中只有一个副本。Bridge 因此改为通过 LaunchServices 按已授权的 `.app` 身份启动
  Helper，不再把后台 Python 作为责任进程；该 Bridge 已部署，健康检查、Typeless 开始与
  停止 API 均返回 200，日志确认两次快捷键均已发送。视觉候选则把骰子 `0–9` 正式加入原生
  80 px Noto Bold 字体，删除 104 px 的 0.76 倍运行时缩放；尖叫改为在设备端 220 px 专用
  Sprite 上保留原始不规则素材，再使用 M5GFX `pushRotateZoomWithAA` 放大到 360 px，并以
  相同路径覆盖 450 px 设计画布和 466 px 物理外框。149 项主测试、独立 C++ 交互测试、差异
  检查和 UAC 固件构建通过；候选镜像为 4,975,360 bytes，SHA-256
  `8d64a093fb2ebbceec8a3cd42e48acb67b7e87736ada24093bc4bf39872ff554`。Bridge 修复已生效，
  固件候选尚未烧录，等待 Owner 授权更新后复验尖叫与骰子数字的原生 AA。
- 上一条“LaunchServices 修复已生效”的判断随后被 Alice 真机操作否证：HTTP 200 只表示
  LaunchServices 接受了启动请求，没有透传 Helper 随后的辅助功能拒绝，因此属于假成功。
  macOS TCC 日志给出确定根因：辅助功能记录仍绑定旧 Helper CDHash `4139a4d2…`，当前
  Helper 已因重签变为 `e136c71a…`，签名要求不匹配。修复将 Bridge 恢复为直接执行已签名
  Helper 并读取真实退出码，使权限拒绝明确返回 502；安装器新增外置源码指纹，源码未变时
  不再重编或重签 Helper，避免再次破坏 TCC 身份。仅重置
  `studio.machiwhale.m5stopwatch.typeless-key-sender` 的 Accessibility 记录后，使用 `.app`
  自身身份重新申请，Alice 在系统设置开启新的 `TypelessKeySender`。随后通过与手表一致的
  本机 Bridge API 完成真实启停闭环：开始返回 200 且 Alice 确认成功听写，结束亦返回 200；
  14 项 Typeless/安装器专项测试通过。该修复只更新 Mac Bridge 与授权，没有重烧固件；
  上述视觉固件候选仍保持未烧录状态。
- Alice 确认 Typeless 开始与结束听写均已实机通过后，授权更新包含 AI 尖叫设备端 AA 与
  Obsidian 原生 80 px 数字字体的最新 UAC 固件。更新前重新执行 150 项 Python 测试、独立
  C++ 交互测试和 `m5stack-stopwatch-uac` 构建，全部通过；镜像保持为 4,975,360 bytes，
  SHA-256 `8d64a093fb2ebbceec8a3cd42e48acb67b7e87736ada24093bc4bf39872ff554`。
  固件已写入正确的应用分区 `0x20000`，esptool 回读确认 Flash 数据哈希一致；设备从下载
  端口 `/dev/cu.usbmodem2101` 恢复为 `/dev/cu.usbmodemM5DASHMIC31`，Bridge 随后重新打开
  USB、读取重启诊断并完成 Dashboard 鉴权。软件、烧录与传输链路验证完成；AI 尖叫边缘与
  Obsidian 数字的最终视觉质量仍以 Alice 本轮真机观察为准。
- Alice 最终决定不再继续追逐 AI 尖叫图的真机边缘锯齿；该项按 Owner 判断接受现状并收口。
  Obsidian 数字与 Typeless 启停均由 Alice 实机确认通过。Codex 二级页并非渲染失败，而是
  本机私人配置仍保持 `codex.expose_transcript: false`，因此只显示任务卡片和“对话内容保持
  私密”。Alice 明确授权后，仅将这台 Mac 的运行配置改为 `true`，仓库默认安全值仍保持
  `false`；Bridge 重启并完成 USB 鉴权，内容无关的核对收据为 3 个可见任务、18 条可见消息。
  展示范围仍只包含近期用户/助手可见文本，不包含推理、工具输入输出、Cookie、凭据或完整
  历史；本项是 Mac Bridge 配置更新，无需再次烧录固件。
- Alice 随后明确授权 Claude 使用与 Codex 相同的对话展示策略。本机运行配置已将
  `claude.expose_transcript` 改为 `true`，仓库默认仍保持关闭；Bridge 已重启并重新连接 USB。
  启用时 Claude 处于空闲状态，内容无关收据为 0 个活动任务、0 个可见消息，因此静态图标
  当前点击无动作符合既有交互条件；下一次 Claude Code 出现活动任务时才可进入二级页查看
  近期用户/助手可见文本。本项同样不需要固件更新。
- Alice 观察到 Codex / Claude 完成反馈动画播放时，圆形屏幕上、右、下、左四个边缘会各露
  出一个白点。根因是动画已将 450 px 设计画布替换为深色供应商背景，但
  `currentRenderedBackground()` 在成功圆完全铺满前仍把 466 px 物理外圈填为暖白纸色；圆屏
  只暴露四个轴向边缘，因此表现为四颗白点。候选修复让所有可见动画帧的物理外圈同步使用
  Codex / Claude 深色底，成功圆铺满后继续跟随强调色渐变，不改变动画内容、时长或业务
  状态。151 项 Python 测试、独立 C++ 交互测试与 UAC 构建通过；候选镜像为 4,975,424 bytes，
  SHA-256 `9bdba56c501fbb29eccbabd2392cddd839266372f1201e02d8118098acb67bbe`，尚未烧录，等待
  Alice 授权更新与真机动画复验。
- Alice 随即提供约 1.99 秒、28 fps 的真机动画视频。逐帧检查补充否证了上一候选的完整性：
  外圈不仅继承暖白底，还会继续执行动画前一页遗留的 `editorialFrameAccentActive`，因此
  视频中顶部/右侧可短暂漏出原页面强调色，其他方位则露纸色。最终候选除同步动画外圈底色
  外，还在每个可见完成动画帧明确关闭 `editorialFrameAccentActive` 与
  `editorialFrameBurstActive`，使 466 px 物理圆屏只显示动画自己的背景、圆环和成功色。
  151 项 Python 测试、独立 C++ 交互测试与 UAC 构建再次通过；新镜像为 4,975,440 bytes，
  SHA-256 `19cfdce267bbae01ba57f42e13e9fa263866ed406ef4caab0a6b5a4577ea342b`。前一候选废弃，
  本候选尚未烧录。
- Alice 授权更新最终动画外圈修复版。首次从 UAC 端口请求下载模式时，设备在 `tcsetattr`
  期间先完成重新枚举，脚本以 `Device not configured` 退出且尚未开始擦写；确认唯一下载端口
  `/dev/cu.usbmodem2101` 后安全重试。4,975,440-byte 镜像已写入应用分区 `0x20000`，esptool
  回读确认 Flash 数据哈希一致；设备恢复为 `/dev/cu.usbmodemM5DASHMIC31`，Bridge 读取正常
  重启诊断并重新完成 Dashboard USB 鉴权。烧录与传输链路验证完成，等待 Alice 通过下一次
  Codex / Claude 完成动画真机确认四边纸色和遗留强调色均已消失。
- Alice 发现首页天气显示“暂不可用”。Bridge 状态确认原配置仍是朋友底座遗留的苏州坐标，
  且本次 Open-Meteo 首次请求碰到瞬时 HTTP 503；旧监控会在首次失败后等待完整一小时，放大
  了短暂故障。天气监控现改为失败后默认 60 秒重试；已有成功天气时继续展示最后有效值，
  只在后台保留错误。153 项 Python 测试通过并已部署 Bridge。Alice 指定改为北京朝阳区，
  本机私人配置已原子更新为行政区中心 `39.9204498, 116.4369109`、时区
  `Asia/Shanghai`，不再继承朋友城市；Bridge 重启后的实测状态为可用、北京朝阳、23.5°C、
  多云、错误为空，并已重新通过 USB 同步。该项无需固件更新。
- Alice 重新确定电源键契约：短按熄屏/唤醒，双击进入程序选择器，未接 USB 时长按关机；
  接 USB 的约 2 秒长按继续保留原厂 Download Mode，避免失去首次烧录和救援入口。软件状态机
  使用 500 ms 双击窗口，单击在窗口结束后才结算，长按会取消待结算单击，因此不会先熄屏再
  关机。新的屏幕待机只关闭 AMOLED、触控和设备麦克风，不再断开 Wi-Fi、UDP 自动发现、
  HTTP/USB Bridge、扬声器通知能力或震动；后台继续以原节奏同步状态。熄屏期间遇到新的最高
  级 AI 热点会立即播放尖叫并震动，并登记待处理唤醒路由；下一次短按唤醒直接进入第 6 屏，
  而显式双击程序选择器会覆盖该自动路由。Stopwatch 页脚同步改为“双击电源键”提示。
  153 项 Python 回归、独立 C++ 电源状态机测试、差异检查与 UAC 固件构建全部通过；候选镜像
  为 4,975,808 bytes，SHA-256
  `c28c717f49feaf8794b9e7416b7291993c76dec9513f8c49d14f2e8f458ed64c`。Alice 随后授权
  更新；镜像已写入正确的应用分区 `0x20000`，esptool 回读确认 Flash 数据哈希一致。设备从
  下载端口 `/dev/cu.usbmodem2101` 恢复为 `/dev/cu.usbmodemM5DASHMIC31`，Bridge 健康检查
  返回正常、读取重启诊断并重新完成 Dashboard USB 鉴权。软件、烧录与传输链路验证完成；
  短按熄/亮、双击选择器、脱线长按关机，以及熄屏 AI 尖叫/震动/第 6 屏唤醒路由仍待 Alice
  逐项真机验证。
- Alice 指出 2026-08-21 的 DeepSeek 多模态模型发布本应触发尖叫，暴露出关注名单偏向
  OpenAI/Anthropic/Google 的漏报。Bridge 已把 DeepSeek、Kimi、Moonshot/月之暗面加入永久
  关注池，把“多模态、视觉模型、multimodal、vision model、vision-exp”加入重大模型事件词；
  DeepSeek/Kimi 官网域名以及两家的官方 X、GitHub、Hugging Face 组织路径进入权威原文识别。
  这些规则会与旧私人配置强制合并，避免保留旧配置时再次漏掉。新增回归以
  `DeepSeek-V4-Flash-Vision-Exp is now available`和“Kimi 新一代多模态模型正式上线”为样例，
  两者在官方原文条件下均稳定判为 `scream`；任意第三方 X/GitHub 路径不会被误认成官方。
  AI 热点专项 11 项、Bridge 全套 155 项 Python 测试通过；本轮只需部署 Bridge，无需重刷固件。
- Alice 指出 StopWatch 未连接 USB 时 Typeless 第 5 屏不应显示 `READY`。候选固件现将
  可用性收紧为四个同时成立的条件：UAC 固件已就绪、检测到物理 USB、TinyUSB 链路可用、
  USB Bridge 已鉴权；未插线显示 `USB 未连接 / VOID / 连接 USB 后使用`，插线但 Mac 尚未
  就绪显示 `Mac 未就绪`。不可用状态会拒绝触发 Typeless，录音中拔线会主动向 Mac 发送停止
  并关闭采集；USB 物理状态从 15 秒电池刷新中拆出，以 500 ms 节奏更新，拔插页面可及时变化。
  顺带修正一个会随日期老化的 AI 热点测试夹具，将其显式测试时效窗固定为 72 小时。
  156 项 Python 回归、独立 C++ 交互测试、差异检查和 UAC 构建通过；候选镜像为
  4,976,176 bytes，SHA-256
  `bf99041c882420a346ca0b965ebb5856d8644581fbb563dd613a7da6b2fd89bf`。本轮尚未烧录，等待
  Alice 授权更新后实机验证拔线不可用、插线恢复 READY 与录音中拔线自动结束。
- Alice 在烧录前要求确认新增中文状态不会重现缺字方框，并选择更保守的全英文文案：未插
  USB 为 `NO USB`，已插线但未建立 Mac Bridge 为 `NO BRIDGE`。核查证实现有 80 px 字体仅
  包含 `READY/LIVE/ERROR` 与数字，确实缺少 `B/G/N/S/U`；直接替换会产生方框。工程找到
  当初生成字体的同一份 `NotoSansHans-Bold.otf`，源文件 SHA-256 与字体清单一致，因此把
  所需字母和空格补入原生 80 px VLW 子集，未采用运行时缩放或系统字体回退。`NO USB`
  单行显示；`NO BRIDGE` 原生宽度超出圆屏安全区，排为 `NO` / `BRIDGE` 两行。字体测试会
  逐字符断言两组文案完整存在。157 项 Python 回归、独立 C++ 交互测试、差异检查和 UAC
  构建全部通过；新候选镜像为 4,993,168 bytes，SHA-256
  `e66bd66a7a291777cd188e779f7520053265d4fb4d8f955d5c291610bb712e86`，正式替代上一候选，
  仍未自动烧录。
- Alice 同意让时钟总览增加持续跳动的秒数，复用 TickTick 专注页已经批准的小号秒数与
  下划线几何（中心 `382,225`，下划线 `359,250,46x5`）。固件新增独立 `56x64` 秒数画布：
  同一分钟内每秒只推送右侧局部区域，分钟跳变、首次进入或时钟状态失配才完整重绘；二级
  页面、完成动画与熄屏期间不会局部覆盖当前画面。该变化只使用现有 24 px 数字字形，不会
  引入新的字体字符或缺字方框；时钟页还会抑制 Bridge 常规两秒同步带来的无条件整页重绘，
  天气、AI 用量、专注摘要与电量最迟在下一次分钟跳变时一并更新，其他页面刷新节奏不变。
  158 项 Python 回归、独立 C++ 刷新状态机、差异检查与 UAC
  固件构建全部通过；合并 `NO USB / NO BRIDGE` 后的新候选镜像为 4,993,904 bytes，SHA-256
  `8ec295b12cd3f0c78399a14996913d777defef3c24e831b382765631fd903291`。候选尚未烧录，等待
  Alice 授权“更新”后再做实机秒数位置、逐秒稳定性与分钟换页验证。
- Alice 随后授权“更新”。上述 4,993,904-byte 合并候选已写入 StopWatch 原厂应用分区
  `0x20000`；esptool 完成写入后回读并确认 `Hash of data verified`，未擦除整片 Flash。
  设备已从下载端口 `/dev/cu.usbmodem2101` 恢复为 UAC/Bridge 端口
  `/dev/cu.usbmodemM5DASHMIC31`；本机 `/healthz` 返回 `{"ok":true}`，Bridge 日志确认重新
  打开串口、读取重启诊断并完成 Dashboard USB 鉴权。软件、烧录、Flash 回读与传输链路验证
  已完成；时钟秒数的位置、逐秒稳定性、分钟跳变整页更新，以及拔线 `NO USB` / 插线未鉴权
  `NO BRIDGE` 仍待 Alice 实机目视确认。
- 首轮实机验证确认 Typeless 拔线后可正确显示 `NO USB`。Alice 同时指出首页秒数 24 px 偏小、
  与 `HH:MM` 距离过远，不像一个时间整体；USB 重新插拔进入充电态后，电池由黑色变为绿色，
  与薄荷绿强调底融在一起。下一候选把秒数升级为仅含 `0-9` 的原生 Noto Sans SC Bold
  32 px 抗锯齿子集，并把秒数中心从 `x=382` 收到 `x=342`、下划线同步移至 `x=316`
  且加宽至 52 px。薄荷首页显式禁用绿色充电强调，保持深色电池轮廓，仍通过底色闪电切口
  表示正在充电；其他页面的充电配色规则不变。159 项 Python 回归、独立 C++ 状态机、字体
  清单校验、差异检查与 UAC 构建全部通过；新候选镜像为 4,999,104 bytes，SHA-256
  `1ae47681daf5c12daadb729b7a482c29edce3742b83da0095005fbf2d4c8512d`。本轮尚未自动烧录，
  等待 Alice 授权“更新”后实机确认秒数整体感与插线充电时的电池对比度。
- Alice 授权“更新”后，上述 4,999,104-byte 候选已写入应用分区 `0x20000`，esptool 回读
  确认 `Hash of data verified`，未擦除整片 Flash。设备已从下载端口
  `/dev/cu.usbmodem2101` 恢复为 `/dev/cu.usbmodemM5DASHMIC31`，Bridge 健康检查返回
  `{"ok":true}`，日志确认重新读取重启诊断并完成 USB 鉴权。软件、烧录、Flash 回读与传输
  链路验证完成；32 px 秒数的整体感和 USB 充电时深色电池的可见性待 Alice 实机目视确认。

## 回家后的首次连接顺序

1. 先用原厂固件确认屏幕、触摸、A/B/电源键与充电正常。
2. 使用确认能传数据的 USB-C 线连接 Mac，执行 `.pio/cli/bin/pio device list`，记录唯一串口；
   本机本次识别结果为 `/dev/cu.usbmodem2101`。
3. 在根目录执行 `python3 scripts/check_ready.py --firmware uac`，必须看到 PlatformIO
   `SUCCESS` 且确认下述 `firmware.bin` 存在后再继续。
4. 设备进入官方 Download Mode：连接 USB 时长按电源/复位约 2 秒，内部绿灯亮后松开。
5. 只烧录原厂 `ota_0` 应用分区（C152 真机起点 `0x20000`），不执行 `erase_flash`：

   ```bash
   cd m5-dashboard
   python3 scripts/flash_compiled.py \
     --firmware firmware/.pio/build/m5stack-stopwatch-uac/firmware.bin \
     --port /dev/cu.usbmodemXXXX
   ```

6. 首次启动后先验证程序选择器和本地 Stopwatch，再验证 Dashboard 的显示、触摸切页、
   按键、电池、配网、USB CDC 与麦克风枚举。
7. 再根据个人配置安装桥接；Typeless 必须先启动一次并完成登录、麦克风权限。

若首次刷入异常，先停止继续写入并记录串口与终端输出；保留原厂恢复路径，不擦除整片 Flash。

## 下一阶段

1. 增加明确的本机配置层，不把朋友的城市、节点名称、网络或隐私选择当成默认值。
2. 真机烧录后分别注入 `scream/alert/inbox` 测试事件，验证声音、震动、自动切页与不误叫。
3. 在真机上校准字体、触摸热区、亮度、震动、声音、续航与麦克风质量。
4. 真机通过后再评估 ArduinoOTA；USB 始终保留为首次烧录和救援通道。
5. 真机联调第 7 屏的抽取、打开与晃动防连触，并观察当前权重是否符合实际惊喜感。

## Git 工作方式

`upstream` 只跟踪朋友的公开仓库；等 Alice 创建自己的 GitHub Fork 后，再把个人仓库加为
`origin`。本地修改在确认前不提交、不推送，个人密钥与生成物继续由 `.gitignore` 隔离。

当前工作树包含另一条 UI 设计 session 的未提交改动。后端和文档工作必须使用精确文件
清单，不能覆盖、回退或批量暂存那些改动。

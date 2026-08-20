# M5 StopWatch：远程 P2S + Codex 状态屏

这是一个只读状态屏：

- 拓竹 P2S：通过 Bambu Cloud 查看连接状态、打印进度、剩余时间、温度和层数。打印机可以和 Mac 位于不同网络。
- Codex 桌面 App：查看正在工作的任务数、等待你处理的任务数、额度窗口和 Token 用量。

公开配置模板默认不会把 Codex 任务标题或对话发给 M5，也不提供暂停、取消打印等控制功能。
可选的“运行中任务对话”只有主动点开 Codex/Claude 中心图标时才显示当前 Mac 上可见的
用户/助手消息；推理、thinking、工具输入和工具结果都会过滤。开启前请阅读下文的隐私说明。

## 数据路径

P2S 主动连接拓竹云，Mac 桥接服务再通过拓竹云 MQTT 获取只读状态。M5 只访问 Mac 的局域网接口，所以不需要把 Mac 或 P2S 的端口映射到公网。

Codex 生命周期 Hook 仍只记录会话 ID、状态、模型和时间。可选的实时对话读取器直接跟随
本机 Codex/Claude 会话文件，并只把可见的用户/助手文本放进内存状态；不会复制推理、
thinking 或工具内容，也不会上传到新的云服务。账户用量通过 Codex App Server 读取。

> 如果你说的“放在公网”是指给打印机做了路由器端口转发，请关闭转发。云模式不需要公网入站端口，直接暴露打印机服务有安全风险。

## 1. 配置 Bambu Cloud

需要拥有已绑定 P2S 的拓竹账号。这里不需要 LAN Access Code，也不会保存账号密码。

```bash
cd /path/to/m5-dashboard
python3 scripts/cloud_setup.py
```

向导会：

1. 让你选择中国大陆或全球账号区；
2. 中国大陆账号默认使用手机号短信验证码，也支持邮箱；全球账号使用邮箱验证码；
3. 用验证码换取云端访问令牌；
4. 自动读取账号 UID 和已绑定的打印机；
5. 生成 `config.json`，并把令牌单独保存到权限为 `600` 的文件。

手机号或邮箱只用于当次登录，不会写入磁盘。访问令牌通常约三个月有效，失效后重新运行向导即可。令牌等同于临时凭据，不要发到聊天或提交到 Git。

### 验证码接口被拦截时

拓竹云是未公开的接口，Cloudflare 规则变化时，短信或邮箱验证码请求可能返回 403。此时可以从已经登录的拓竹网页复制 `token` cookie，然后运行：

```bash
python3 scripts/cloud_setup.py --region cn --paste-token
```

全球账号把 `cn` 换成 `global`。Chrome/Edge 中的获取位置是：开发者工具 → Application → Cookies → `bambulab.cn` 或 `bambulab.com` → `token`。输入令牌时终端不会回显。

若云端设备列表也被拦截，向导会让你输入 P2S 序列号；序列号可以在 Bambu Handy 的设备信息页或机器标签上找到，它不是密码。

如果向导意外退出但短信已经到达，可避免重复发送并继续使用现有验证码：

```bash
python3 scripts/cloud_setup.py --region cn --use-existing-code
```

## 2. 启动 Mac 桥接服务

桥接程序只使用 macOS 自带的 Python 3，不需要额外 Python 包：

```bash
python3 -m bridge --config config.json
```

另开一个终端检查。`api_token` 位于刚生成的 `config.json`：

```bash
python3 scripts/check.py --token 'YOUR_DASHBOARD_TOKEN'
```

看到 `P2S: connected=True` 表示云链路正常。如果显示离线，查看终端错误；MQTT 拒绝通常表示账号区域选错或令牌已过期。

## 3. 安装 Codex 状态 Hook

安装器会先备份已有的 `~/.codex/hooks.json`，再合并自己的 Hook：

```bash
python3 scripts/install.py --hooks
```

重启 ChatGPT/Codex 桌面 App。非托管 Hook 首次使用需要信任；如果桌面界面没有审查入口，可在终端启动 `codex`，输入 `/hooks` 检查并信任。

Hook 安装之后的新任务会显示 `working`、`waiting_approval`、`waiting_input` 和 `idle`。安装前已经运行的任务，需要再发送一条消息才会进入监控。

## 4. 设置开机启动

确认 `config.json` 的云连接已验证，再运行：

```bash
python3 scripts/install.py --launch-agent
```

安装器会自动加载或重启服务，无需再手动执行 `launchctl bootstrap`。

安装后的配置位于：

```text
~/Library/Application Support/M5Dashboard/config.json
```

修改后重启服务：

```bash
launchctl kickstart -k gui/$(id -u)/com.local.m5dashboard.bridge
```

Mac 必须保持开机联网，因为 Codex 状态来自这台 Mac。P2S 可以在任何能连接拓竹云的网络里；M5 仍需能访问这台 Mac 的局域网地址。

如果当前 Wi-Fi 不支持 ESP32、存在客户端隔离，M5 也可以通过 USB 线直接读取这台 Mac
的桥接状态。新版桥接会自动打开 M5 的原生 USB 串口，使用同一个本地令牌鉴权；USB
可用时优先，拔掉 USB 后仍按原逻辑尝试家庭/公司 Wi-Fi。USB 只传输只读仪表盘 JSON，
不会清除或改写 M5 的 Wi-Fi 配置。

桥接服务同时在 UDP `8766` 提供局域网自动发现，只公布 Mac 地址和 HTTP 端口，不广播桥接令牌。M5 仍会使用自己的令牌访问 `/api/state`；令牌不匹配时不会取得任何监控数据。

## 5. 刷入 M5 StopWatch

固件二进制不包含 Wi-Fi 密码或桥接令牌。已有设备继续读取 NVS 里的配置；全新设备在首次启动后自动进入手机配网模式。StopWatch 的 ESP32-S3 仅支持 2.4 GHz Wi-Fi。

使用已编译且只更新应用分区的安全烧录脚本：

```bash
python3 scripts/flash_compiled.py
```

不要执行 `erase_flash`，否则会清除设备里已有的网络配置。

### Arduino IDE

1. 安装 M5Stack Board Manager 3.3.7 或更高版本。
2. 选择开发板 `M5StopWatch`。
3. 安装 `M5Unified`、`M5GFX` 和 `ArduinoJson 7`。
4. 打开 `firmware/M5Dashboard/M5Dashboard.ino`。
5. 长按设备复位键约两秒，内部绿灯亮起后松开，选择串口并上传。

### PlatformIO

```bash
cd firmware
pio run -e m5stack-stopwatch
pio run -e m5stack-stopwatch --target upload
```

带 USB 麦克风的构建使用 Arduino ESP32 3.3.11 与 TinyUSB Audio，并保留复合 USB CDC
供现有桥接传输状态：

```bash
pio run -e m5stack-stopwatch-uac
```

中文界面使用官方 `Noto Sans CJK SC Regular`。将
`NotoSansCJKsc-Regular.otf` 放在项目根目录后运行
`python3 scripts/generate_ui_font.py NotoSansCJKsc-Regular.otf`，生成的 VLW 字体会直接映射
Flash；源 OTF 默认被 Git 忽略，不会进入仓库。

中心图标是本项目自绘的通用 `P2S`、`CX` 和 `CL` 图形，不包含第三方商标或官方美术素材。
使用 Pillow 重新生成 PNG8 头文件（需在开发环境安装 Pillow）：

```bash
python3 firmware/scripts/generate_open_assets.py
```

该构建刷入后，macOS 会同时看到串口和名为 `M5 StopWatch Mic` 的单声道
USB 麦克风。M5 现在从 ES8311 原生采集 48 kHz / 16-bit 单声道 PCM，不再经过
21.333 kHz 时钟补偿或软件升采样。采集与 USB 发送使用独立任务和两块 10 ms
缓冲，USB 短写会续传，积压时只丢弃最旧的完整音频块。ES8311 使用 24 dB
模拟 PGA、24 dB ADC scale、+6 dB 数字增益和动态硬件高通；寄存器在每次开启
麦克风时写入并回读验证。运行 `python3 scripts/install.py --all`
会把 Typeless 设为系统默认麦克风和 `Fn` 听写键，并安装插线后自动选择
`TinyUSB UAC1` 的后台服务。

自行编译或从 [GitHub Releases](../../releases) 下载的应用分区镜像可用安全脚本刷入；
脚本会临时释放桥接占用的串口，通过 1200-bps
切换到 ESP32-S3 下载口，刷完用 watchdog 回到应用并恢复桥接。全程只写 `0x10000`，
不清除 NVS：

```bash
python3 scripts/flash_compiled.py \
  --firmware firmware/.pio/build/m5stack-stopwatch-uac/firmware.bin
```

## 操作

- 屏幕横向滑动：依次切换拓竹、Codex 与 Claude 页面；左右轻点不再切页，避免误触。
- 左半屏纵向滑动：上滑增加亮度、下滑降低亮度，范围 10%–100%；按 1% 连续跟手显示。
- 右半屏纵向滑动：上滑增加通知音量、下滑降低音量，降到 0% 时静音；按 1% 连续跟手显示。
- A 键短按：显示数据通道、桥接服务和最近更新时间，并立即触发一次状态刷新。
- A 键长按约 0.8 秒：打开“连接中心”，可点击“自动选择”、“家庭网络”、“公司网络”或“添加或修改网络”。手动目标尝试失败后会留在连接中心，不会擅自进入配网或改写已保存的凭据。
- B 键短按：开启或关闭 M5 麦克风。开启后显示真实实时呼吸、声波和 16 段音量动画，
  并向 Mac 发送 48 kHz 单声道 USB 音频；再按一次停止。需要听写时按 Typeless 的
  `Fn` 键开始/停止转写。麦克风页底部直接显示居中的“再按一次关闭麦克风”，不再显示
  容易让人困惑且位置分离的 `B` 标识。M5 不再模拟 USB 键盘，因此不会干扰 Mac 的真实键盘输入。
- 底部左侧红色电源键：运行时单击进入真正待机，再单击唤醒；快速双击关机；关机状态单击开机。连接 USB 时长按约 2 秒，看到内部绿色 LED 后松开，即进入 M5Stack 官方下载模式。单击会等待约 500 ms 排除双击后再执行。
- 同时长按 A+B 约 2.5 秒：进入手机配网模式。
- 第 1 页：P2S 中文打印仪表盘，外圈为打印进度，显示剩余时间、温度和层数。
- 第 2 页：Codex 中文任务与用量仪表盘，也是开机默认大屏；外圈用填充色带显示本周剩余额度；右下角以“亿”为单位显示累计 Token 用量，五小时窗口存在时优先显示五小时剩余额度。中间使用自绘的 Tableau 蓝色 `CX` 机器人：工作、等待确认、完成和异常分别播放对应动画，空闲时静止。存在运行中任务时，点击中心机器人可打开实时对话；一个任务直接进入，多个任务先选择。对话使用 iMessage 风格的左右气泡，竖向滑动可看较早或较新的消息，点击圆屏顶部居中的下箭头返回。
- 第 3 页：Claude 中文用量仪表盘，位于 Codex 右侧；组件位置、字号和尺寸与 Codex 页一致，使用 Tableau 橙色和自绘 `CL` 标识。Claude 正在工作时，中心标识会缩放呼吸，空闲时静止；点击运行中的中心图标可按与 Codex 相同的方式查看实时对话。右下角显示累计 Token；官方周额度不可用时，顶部百分比和底部重置时间显示 `--`，不推算或伪造。
- 麦克风浮层改用暖珊瑚红表示“正在采集”，与 Codex 蓝、Claude 橙及系统连接状态区分；去掉装饰外环，细线麦克风、声波、峰值条和小号底部操作文案统一为一套更紧凑的视觉层级。珊瑚红保留录音语义，但比故障告警红更柔和。
- 四个大屏（拓竹、Codex、Claude、麦克风）先在 450×450 设计层绘制，再合成一张每个像素都被明确填充的 466×466 成品帧，最后居中送入 M5GFX 的 468×468 逻辑窗口；圆环、中心图标、指标、浮层和页码共用真实屏幕圆心，页面切换不会残留上一页边缘像素。
- 页面切换使用约 140 ms 的方向一致滑动过渡；内存不足时自动降级为即时切换。
- 拓竹、Codex 和 Claude Logo 正上方常驻显示 M5 自身电量；充电时为绿色闪电，30% 以下为黄色，15% 以下为红色。
- 喷嘴、热床和机舱温度均显示“℃”单位。
- 底部状态灯默认关闭，锁屏和关机时也保持熄灭以降低耗电。
- GPT-5.3-Codex-Spark 的独立额度不会显示。
- P2S 完成/故障、Codex 等待批准、全部 Codex 任务完成时会震动并播放不同短提示音。
- 亮屏时无触摸、按键、语音或页面动画 15 秒后，CPU 从 240 MHz 自动降到 80 MHz；再次交互会立即升频，网络和 USB 数据仍保持在线。红键进入待机后会关闭 AMOLED 与触摸、停止麦克风/通知、断开 Wi-Fi 并暂停 USB 状态传输；待机期间不监控，唤醒后自动恢复连接和刷新。

## 家庭/公司自动切换

1. 同时长按 M5 的 A+B 约 2.5 秒，屏幕出现“配网模式”。
2. 手机连接屏幕显示的 `M5-Dashboard-XXXX` 热点，密码为 `m5dashboard`。
3. 手机通常会自动弹出配置页；没有弹出时访问 `http://192.168.4.1/`。
   如果不想修改，可点击 M5 屏幕上的“选择已保存网络”，或再次同时长按 A+B 约 2.5 秒取消。
4. 手机页面会明确列出扫描到的附近 Wi-Fi；可分别为“家庭”和“公司”选择网络，也可手动输入隐藏 SSID。
5. Mac 桥接地址建议留空，让 M5 在当前局域网自动发现电脑。
6. 保存后 M5 自动重启。以后设备会自动连接当前能用的家庭或公司网络，并自动验证对应 Mac 的令牌，不需要手动切换。
7. 如果两个已保存网络都无法连接，设备会留在连接中心，由用户选择重试、自动模式或添加/修改网络；不再自动打开配网热点。

固件升级会把原来的单套配置自动迁移为“家庭”配置，不会清除家庭 Wi-Fi 或现有 Mac 令牌。

USB 与 Wi-Fi 会并行保持：USB 可用时状态数据优先走 USB，但设备仍在后台自动连接家庭或公司 Wi-Fi。两个网络按槽位轮询，每个网络最多尝试约 12 秒；USB 在线时即使暂时找不到 Wi-Fi，也不会强制跳入配网模式。

新电脑安装桥接服务的手动命令是：

```bash
python3 scripts/install.py --all
```

安装器会配置 Codex Hook、启动桥接并安装自动选择 M5 麦克风的服务。每台 Mac 首次运行时
仍需同意 macOS 的麦克风/辅助功能权限，并在 Codex 中信任本地状态 Hook；这些系统权限
不能随配置文件迁移。网络必须允许 M5 与 Mac 互相访问 UDP `8766` 和 TCP `8765`；带客户端
隔离、企业证书或网页认证的网络可能无法使用，独立的 2.4 GHz 局域网通常更稳定。

### 合并另一台 Mac 的今日 Token

`codex.peer_usage_sources` 可以读取同一局域网里另一台本人所有的用量服务，并只把它的
“今日 Total”合并到当前 M5 的“今日用量”。账号累计、活动任务和等待确认仍由当前连接
M5 的 Mac 提供，避免重复累计账号数据或把远端任务混进来。示例配置默认保持空数组；
实际地址和认证信息只写入每台 Mac 的本地 `~/Library/Application Support/M5Dashboard/config.json`，
不要同步到项目源码。

远端返回值必须带有当天的 `generated_at`；昨天的缓存会被拒绝。短暂不可达时，桥接会在
当天继续使用最近一次成功值，并在后续刷新时自动追上。

### 汇总同行节点的实时活动与会话

M5 只连接主桥接；另一台 Mac 可运行无界面的同行节点，把本机 Codex 与 Claude Code
活动数、等待状态、可见对话摘要和今日完成结果交给主桥接汇总。同行节点不会启动 USB
响应、UDP 自动发现、天气或拓竹，因此 M5 不会误连；官方额度、账号累计和既有用量服务
也不会被替换或重复计算。

在同行节点执行一次：

```bash
python3 scripts/install.py --peer-node
```

再在主桥接执行：

```bash
python3 scripts/install.py --add-peer-from-usage --launch-agent
```

第二条命令从主桥接已有的 `peer_usage_sources` 取同行主机，只新增受令牌保护的
`8765` 活动连接，不读取或打印既有密码。令牌只保存在各节点本地配置中，不能提交到仓库。
任一端
`active_count > 0` 都会驱动对应中心图标动画；同行断线后远端活动立即从汇总中移除。

如果 StopWatch 还需要在同行节点上通过 USB 直连，可把该节点升级为 USB 模式：

```bash
python3 scripts/install.py --peer-usb
```

该模式仍关闭 UDP 自动发现，只有设备物理插入时才会接管串口，不会和主桥接抢无线连接。
HTTP 同行接口继续使用独立认证，USB 则使用 M5 已保存的桥接认证。同行节点会把主桥接的
完整聚合状态转发给 USB；主桥接暂时不可达时，USB 自动退回同行节点本机 Codex/Claude
状态。`M5_PEER_USB_API_TOKEN`、`M5_PEER_USB_UPSTREAM_TOKEN` 和
`M5_PEER_USB_UPSTREAM_URL` 只由受保护的部署流程在节点本机注入，不能写入共享源码。

### Claude 页面数据

`claude.source` 可读取同网段 AI 用量服务中的 Claude 数据，并提供今日 Token、累计
Token 与可选的官方额度窗口。认证信息只保存在当前 Mac 的本地配置中，不写入示例配置或
固件。官方周额度或重置时间不可用时，M5 显示 `--`，不会把本地 Token 统计推算成官方额度。

## LAN 模式备选

如果将来把打印机和 Mac 放到同一网络，仍可把 `bambu` 配置改成：

```json
{
  "enabled": true,
  "name": "P2S",
  "mode": "lan",
  "host": "192.0.2.50",
  "port": 8883,
  "serial": "YOUR_SERIAL",
  "access_code": "YOUR_LAN_ACCESS_CODE",
  "verify_tls": false,
  "full_refresh_seconds": 30
}
```

## 验证结果

```bash
python3 -m unittest discover -s tests -v
cd firmware && pio run
```

发布前应运行上面的 Python 测试、UAC 固件构建，以及带 `-Wall -Wextra -Werror` 的
独立 C++ 交互测试。预编译镜像及其 SHA-256 应随具体 GitHub Release 发布，不写死在源码文档中。

## 已知边界

- 拓竹目前没有面向个人监控场景的公开稳定 API；云登录和 MQTT 细节来自社区协议记录，拓竹或 Cloudflare 改动后可能需要更新。
- 云端连接使用有效 CA 验证；令牌和打印机序列号保存在 Mac，不写入 M5。
- 云监控只订阅状态并低频请求完整状态，不提供远程打印控制。
- `waiting_input` 根据最终回答是否明显在提问来判断，准确度低于 `working` 和 `waiting_approval`。
- M5 到 Mac 的 v1 接口是带 Token 的局域网 HTTP，不要把端口暴露到公网。

参考资料：

- USB 音频双任务管线与 ES8311 语音参数选择性参考了 MIT 许可的
  [`digitsisyph/codex-micro-stopwatch`](https://github.com/digitsisyph/codex-micro-stopwatch)，
  固定评审提交 `e4f51036ebba21815854e7c427a3f51c2dc10fc1`；所需版权声明和许可全文见
  [`third_party/codex-micro-stopwatch-MIT.txt`](third_party/codex-micro-stopwatch-MIT.txt)。

- [OpenBambuAPI：Cloud MQTT 连接方式](https://github.com/Doridian/OpenBambuAPI/blob/main/mqtt.md)
- [OpenBambuAPI：Cloud HTTP 与 UID](https://github.com/Doridian/OpenBambuAPI/blob/main/cloud-http.md)
- [BambuHelper：P2S 云模式与令牌说明](https://github.com/Keralots/BambuHelper)
- [OpenAI Codex App Server](https://learn.chatgpt.com/docs/app-server)
- [OpenAI Codex Hooks](https://learn.chatgpt.com/docs/hooks)
- [M5Stack StopWatch 上传指南](https://docs.m5stack.com/en/arduino/stopwatch/program)

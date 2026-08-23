# M5 StopWatch Dashboard

> Alice 的个人分支以好友@Googler0825 的开源 Dashboard 为底座；项目基线、当前加固、真机首次连接顺序
> 与后续个性化路线见 [PROJECT.md](PROJECT.md)。

这不是把电脑仪表盘硬塞进一块圆屏，而是 Alice 的一张桌面工作切片：它会报时、盯住专注、
看看 Coding AI 今天忙成什么样，在真正重要的 AI 消息到来时尖叫一声，也会从 Obsidian 里
捞起一篇很久没有见过的笔记。

## 一块表，两个程序

开机先进入程序选择器：A 选中 `Dashboard`，B 选中本地 `Stopwatch`。A/B 只切换高亮选项；
轻触任一程序卡可直接进入对应程序。

- **Dashboard** 是七屏个人工作台，连接 Mac Bridge 后获得 TickTick、AI 用量、热点、
  Obsidian 与 Typeless 能力。
- **Stopwatch** 保留独立的本地秒表体验，不联网也能开始、暂停、记圈和复位。

## Dashboard 的七个世界

| 屏幕 | 它在做什么 | 可以怎么用 |
|---|---|---|
| 1. 时钟总览 | 显示时间、跳秒、日期、北京朝阳天气、电量、TickTick 进度与当天全部 Coding AI Token | 轻触 `星盘` 看正在运行的任务，轻触 `成果` 回看今天完成的工作 |
| 2. TickTick 专注 | 把正计时和 25 分钟倒计时放在同一页 | A 控制正计时，B 控制倒计时；单击开始/暂停/继续，双击结束 |
| 3. Codex | 显示当前状态、剩余额度、重置时间、今日与累计用量 | 有活动任务时轻触 Codex 图标查看详情；对话内容默认保持私密 |
| 4. Claude Code | 显示 Claude Code 的活动、额度窗口与 Token 用量 | 有活动任务时轻触 Claude 图标查看详情；没有任务时保持安静 |
| 5. Typeless | 插线时把 StopWatch 变成 48 kHz USB 麦克风，拔线时降级为 Mac 麦克风遥控器 | `USB MIC` 临时接管输入、结束后归还原麦克风；`MAC MIC` 经 Wi-Fi 启停 Typeless 并保留电脑麦克风；两条 Bridge 链路都不可用时显示 `NO BRIDGE` |
| 6. AI 热点尖叫 | 监听 Codex Reset、AIHOT、DeepSeek、Kimi 与官方信源；重大模型、额度或安全事件才真正“尖叫” | 新热点会播放声音并震动；可点 `知道了` 确认，或点 `打开` 在 Mac 查看原文 |
| 7. Obsidian 幸运笔记 | 从明确授权的知识库随机重遇一篇笔记 | 轻触骰子、点 `再摇` 或晃动设备重新抽取；点 `打开文档` 回到 Obsidian |

![M5 StopWatch Dashboard 七屏预览](design/stopwatch-ui-preview.png)

## 按键与电源

在 Dashboard 中，A/B 是全局专注键，无论当前停在哪一屏，操作后都会自动切到第 2 屏反馈：

- **A 单击**：正计时开始、暂停或继续；**A 双击**：结束正计时并保留本次用时。
- **B 单击**：25 分钟倒计时开始、暂停或继续；**B 双击**：结束并回到 `25:00`。
- **A 长按 0.8 秒**：打开网络选择；**B 长按 0.8 秒**：回到第 1 屏，不改变计时状态。
- **A+B 长按 2.5 秒**：主动进入配网。

红色电源键负责整块表的状态：

- **短按**：熄屏或唤醒。熄屏时关闭显示、触控与麦克风，但 Wi-Fi、扬声器和震动仍待命；
  若此时收到 AI 尖叫，下一次唤醒会直接进入第 6 屏。
- **双击**：从任意页面回到程序选择器。
- **长按约 1.6 秒**：未连接 USB 时关机；连接 USB 时软件不截获长按，继续按住约 2 秒会
  进入原厂 Download Mode，方便烧录与救援。

触摸屏左右滑动切换七屏；沿左、右边缘纵向滑动分别调节亮度与提示音量，上滑增加、
下滑降低。

进入独立 Stopwatch 后，A/B 会恢复秒表语义：静止时 B 开始；运行时 A 记圈、B 暂停；
暂停时 A 复位、B 继续。这里不另设 A/B 双击或长按动作，电源键契约保持不变。

## 项目里有什么

- `m5-dashboard/`：M5 固件、通用 Mac 桥接、安装脚本和测试。
- `m5-dashboard-home/`：只读取本机 Claude Code 日志的轻量伴随桥接。

## 安全与隐私

- 公开示例默认关闭任务标题和对话预览。
- 真实的 `config.json`、TickTick/桥接令牌、`secrets.h`、任务日志、构建缓存
  和 `dist/` 均被 `.gitignore` 排除。
- 局域网接口必须使用随机 Token，不能映射到公网。
- 本地 Claude 模式只读取 `~/.claude/projects` 会话日志，不读取浏览器 Cookie、Keychain
  或官方账户接口。

## 固件

仓库不跟踪预编译固件。可按 [固件构建说明](m5-dashboard/README.md#platformio) 自行编译；
项目维护者也可以通过 [GitHub Releases](../../releases) 提供已验证的应用分区镜像。
首次安装和故障救援仍使用 USB。救援脚本只重置原厂 `otadata` 并写入 `ota_0`
（起点 `0x20000`），不会执行 `erase_flash`，因此 NVS 中保存的 Wi-Fi、令牌和设备设置会保留。

首次用 USB 装入支持 OTA 的固件后，后续版本可由可信局域网内的 Bridge 提供。手表只在首页、
亮屏且没有计时、听写或动画等交互时检查更新；候选镜像会流式写入当前未运行的另一 OTA 分区，
并在大小、SHA-256 与 ESP 应用镜像三项校验全部通过后才切换启动分区。发布仍是显式动作，Bridge
没有候选时不会更新。完整操作见 [HTTP OTA](m5-dashboard/README.md#5-http-ota)。

## 验证

```bash
cd m5-dashboard
python3 -m unittest discover -s tests -v

cd ../m5-dashboard-home
python3 -m unittest discover -s tests -v
```

```bash
cd m5-dashboard/firmware
pio run -e m5stack-stopwatch-uac
```

完整配置、安装、操作与已知边界见 [m5-dashboard/README.md](m5-dashboard/README.md)。

## 许可证

本项目原创代码采用 [MIT License](LICENSE)。项目引用或包含的第三方内容继续遵循各自
许可证；相关声明见 `m5-dashboard/third_party/`。

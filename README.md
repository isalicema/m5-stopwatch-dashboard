# M5 StopWatch Dashboard

> Alice 的个人分支以好友@Googler0825 的开源 Dashboard 为底座；项目基线、当前加固、真机首次连接顺序
> 与后续个性化路线见 [PROJECT.md](PROJECT.md)。

一个面向 M5Stack StopWatch 的双程序个人工作台。开机可在 Dashboard 七屏与独立本地
Stopwatch 之间选择；项目包含 ESP32-S3 固件和 macOS 本地桥接，可用 A/B 键控制 TickTick
正计时与 25 分钟倒计时，显示 Codex/Claude 活动与用量，并在第 5 屏控制 48 kHz UAC1
Typeless USB 麦克风。

## 目录

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
烧录脚本只应写入原厂分区表的 `ota_0`（起点 `0x20000`）；不要执行 `erase_flash`，否则会清除 NVS 中保存的
Wi-Fi、令牌和设备设置。

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

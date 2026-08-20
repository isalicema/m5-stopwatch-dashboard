# M5 StopWatch Dashboard

一个面向 M5Stack StopWatch 的开源只读状态仪表盘。项目包含 ESP32-S3 固件和 macOS
本地桥接，可显示 P2S 打印状态、Codex/Claude Code 活动与用量，并提供 48 kHz UAC1
USB 麦克风、双网络配置和多 Mac 同行节点。

## 目录

- `m5-dashboard/`：M5 固件、通用 Mac 桥接、安装脚本和测试。
- `m5-dashboard-home/`：只读取本机 Claude Code 日志的轻量伴随桥接。

## 安全与隐私

- 公开示例默认关闭任务标题和对话预览。
- 真实的 `config.json`、Bambu Cloud 凭据、桥接令牌、`secrets.h`、任务日志、构建缓存
  和 `dist/` 均被 `.gitignore` 排除。
- 局域网接口必须使用随机 Token，不能映射到公网。
- 本地 Claude 模式只读取 `~/.claude/projects` 会话日志，不读取浏览器 Cookie、Keychain
  或官方账户接口。

## 固件

仓库不跟踪预编译固件。可按 [固件构建说明](m5-dashboard/README.md#platformio) 自行编译；
项目维护者也可以通过 [GitHub Releases](../../releases) 提供已验证的应用分区镜像。
烧录脚本只应写入 `0x10000` 应用分区；不要执行 `erase_flash`，否则会清除 NVS 中保存的
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

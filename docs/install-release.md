# 安装 Release 固件

当前版本：[v2026.09.14](https://github.com/isalicema/m5-stopwatch-dashboard/releases/tag/v2026.09.14)。
适用于 **M5Stack StopWatch / C152、ESP32-S3、原厂 16 MB 分区布局**；Mac Bridge 面向 macOS。
本次镜像通过自动化测试与编译，尚未对本次镜像重新进行实机验收。

## 1. 取得同版本源码和固件

Mac 需要 Git、可用的 Python 3 和支持数据传输的 USB-C 线。使用预编译固件不需要 PlatformIO。
在终端运行：

```bash
git clone --branch v2026.09.14 --depth 1 https://github.com/isalicema/m5-stopwatch-dashboard.git
cd m5-stopwatch-dashboard/m5-dashboard
mkdir -p dist
curl -fL -o dist/M5Dashboard-v2026.09.14-uac.bin https://github.com/isalicema/m5-stopwatch-dashboard/releases/download/v2026.09.14/M5Dashboard-v2026.09.14-uac.bin
curl -fL -o dist/SHA256SUMS https://github.com/isalicema/m5-stopwatch-dashboard/releases/download/v2026.09.14/SHA256SUMS
(cd dist && shasum -a 256 -c SHA256SUMS)
```

必须看到固件文件校验为 `OK` 后再继续。`SHA256SUMS` 校验固件；Release 另附 `build-info.json`
记录源码、构建环境、固件大小和验证范围，`THIRD-PARTY-NOTICES.txt` 包含随二进制分发的许可声明。

## 2. 首次刷入前保存备份

如果从未备份过这块设备，先保存可恢复的完整 Flash。确认设备是上述 C152 原厂分区布局；
若曾改过分区，先恢复并核对原厂布局，不要直接使用本页的烧录命令。

将设备接入 USB 并进入官方 Download Mode；用 `ls /dev/cu.usbmodem*` 查看下载端口，
把下文 `/dev/cu.YOUR_STOPWATCH_PORT` 替换成这块表实际的端口。只连接要操作的设备，避免选错。

```bash
python3 -m venv .flash-env
.flash-env/bin/python -m pip install esptool==4.9.0
mkdir -p backups
.flash-env/bin/python -m esptool --chip esp32s3 --port /dev/cu.YOUR_STOPWATCH_PORT --before no_reset --after no_reset read_flash 0x0 0x1000000 backups/stopwatch-before-release.bin
shasum -a 256 backups/stopwatch-before-release.bin > backups/stopwatch-before-release.bin.sha256
```

确认读取成功、文件为 16,777,216 字节，并把备份和校验文件存到安全的本机位置。
完整备份可能包含设备里的 Wi-Fi 和令牌，不要上传到 Issue 或公开仓库。

## 3. 烧录应用固件

仍在 `m5-dashboard` 目录，设备保持 Download Mode：

```bash
.flash-env/bin/python scripts/flash_compiled.py --port /dev/cu.YOUR_STOPWATCH_PORT --firmware dist/M5Dashboard-v2026.09.14-uac.bin
```

已有备份的用户可以直接使用 `python3 scripts/flash_compiled.py` 的同样参数；脚本会寻找可用的
esptool，缺少时创建一次性烧录环境。

脚本校验字体标记与分区容量，只重置 `0xD000` 的 8 KiB OTA 选择区，并在 `0x20000` 写入
应用固件；不重写引导程序、分区表或 NVS，也不执行全片擦除。不要把此应用镜像写到 `0x0`。
已有 Wi-Fi、Token 和设备设置会保留。若重启后没有进入新应用，重新进入 Download Mode，
检查 USB 线和端口，再使用同一脚本救援。

开机后选择 **Stopwatch** 或 **Timer** 即可体验离线秒表和倒计时；这两项无需 Mac 服务或 Wi-Fi。

## 4. 连接 Dashboard

仍在 `m5-dashboard` 目录运行：

```bash
python3 scripts/install.py --launch-agent
```

安装器会复制 Bridge、生成随机 Token 并安装 macOS 常驻服务。配置保存在
`~/Library/Application Support/M5Dashboard/config.json`。如果已有配置，先备份并检查自己的设置；
安装器会保留已有有效 Token。

插线进入 Dashboard 后，设备通过 USB 自动配对，不需要先配置 Wi-Fi。
首次使用先跑通这一条连接；没有安装的数据源可能显示离线或 `AI--`，不代表固件安装失败。
示例天气为北京，请改成自己的城市；使用 Obsidian 前请明确设置自己授权的 `obsidian.roots`，
不使用的功能可在配置中关闭对应的 `enabled`。

## 5. 按需接入功能

| 想使用的功能 | 下一步 |
|---|---|
| TickTick 专注 | 安装 [TickTick Focus Bridge](https://github.com/isalicema/m5stick-ticktick-focus)，再核对两个 Bridge 的 Token 配置 |
| Codex / Claude 活动与完成动画 | 阅读 [Hook 与常驻服务](../m5-dashboard/README.md#3-安装-codex-hook-与常驻服务) |
| 完整 AI 用量汇总 | 按需安装 [Multi AI Usage Monitor](https://github.com/isalicema/api-usage-board) |
| Typeless USB 麦克风 / 遥控 | 先安装并登录 Typeless，完成麦克风权限，再按 [Bridge 说明](../m5-dashboard/README.md#3-安装-codex-hook-与常驻服务)配置 |
| Wi-Fi 与后续 OTA | 在 Dashboard 长按 A+B 进入配网；升级见 [HTTP OTA](../m5-dashboard/README.md#5-http-ota) |

## 反馈

[安装或使用问题](https://github.com/isalicema/m5-stopwatch-dashboard/issues/new?template=bug_report.yml) ·
[功能建议](https://github.com/isalicema/m5-stopwatch-dashboard/issues/new?template=feature_request.yml) ·
[我用起来了 / 使用体验](https://github.com/isalicema/m5-stopwatch-dashboard/issues/new?template=experience.yml)

报告问题时请写固件与 Bridge 版本、macOS 版本、设备型号、USB / Wi-Fi 连接方式及复现步骤。
日志和截图请先脱敏，不要提交完整备份、Token、Wi-Fi 密码、私人笔记或对话内容。

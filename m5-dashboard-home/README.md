# M5 Dashboard 本地伴随桥接

这是供独立 Mac 使用的轻量 companion，不修改另一台 Mac 已安装的主桥接，也不需要重刷
M5 固件。

本地伴随桥接只读取这台 Mac 上的 Claude Code 会话日志：

- 今日、5 小时和 7 天 Token 来自本机 `~/.claude/projects` 日志；
- 不读取 Claude Desktop Cookie、Keychain 或账户接口；官方 5 小时/本周额度显示 `--`
  属于预期行为；
- “累计”默认是这台 Mac 的本地会话小计；如私人部署需要从已核对的累计检查点继续，
  可只在本机配置中填写检查点字段，不要提交到仓库；
- 继续沿用本机已有的 M5 桥接令牌、拓竹配置和 Codex 配置。
- Codex 与 Claude Code 的中心图标会直接读取本机会话日志的活动状态：Codex 使用
  `task_started/task_complete`，Claude 使用 `tool_use/end_turn`。因此即使系统的
  Codex 通知 Hook 被其他功能占用，工作时动画仍会在约 3 秒内开始或停止。

安装：

```bash
/usr/bin/python3 scripts/install_home.py
```

服务使用独立目录 `~/Library/Application Support/M5Dashboard-Home` 和独立启动项
`com.local.m5dashboard.home.bridge`。同机的旧服务会被停用但文件仍保留，方便恢复；
其他 Mac 上的桥接不受影响。

示例配置默认关闭 Codex/Claude 对话预览。开启 `expose_transcript` 会让受 Token 保护的
局域网接口返回本机可见的用户/助手文本，仅应在可信局域网中主动启用，且不得把端口暴露
到公网。

验证：

```bash
/usr/bin/python3 -m unittest discover -s tests -v
```

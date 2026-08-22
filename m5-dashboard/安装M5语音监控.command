#!/bin/zsh
set -euo pipefail

cd "${0:A:h}"

pause_before_close() {
  if [[ -t 0 ]]; then
    read -k 1 "?$1"
  fi
}

echo "正在配置 M5 监控、Codex 状态、Typeless 和按需麦克风……"
echo

if ! open -Ra Typeless; then
  echo "未找到 Typeless，请先安装后再运行本文件。"
  pause_before_close "按任意键退出……"
  exit 1
fi

TYPELESS_SETTINGS="$HOME/Library/Application Support/Typeless/app-settings.json"
if [[ ! -f "$TYPELESS_SETTINGS" ]]; then
  echo "这是这台 Mac 第一次配置 Typeless。"
  echo "Typeless 已打开：请完成登录，并同意 macOS 的麦克风权限。"
  open -a Typeless
  if [[ -t 0 ]]; then
    read -r "?登录和授权完成后，回到本窗口按回车继续（不需要重新运行）："
  else
    deadline=$((SECONDS + 600))
    while [[ ! -f "$TYPELESS_SETTINGS" && $SECONDS -lt $deadline ]]; do
      sleep 1
    done
  fi
  if [[ ! -f "$TYPELESS_SETTINGS" ]]; then
    echo "仍未检测到 Typeless 设置。请确认已完成登录后重新双击本文件。"
    pause_before_close "按任意键退出……"
    exit 1
  fi
fi

/usr/bin/python3 scripts/install.py --all

echo
echo "配置完成。仅从手表启动 Typeless 时临时使用 M5 麦克风，结束后恢复；Typeless 听写键为 Fn。"
echo "第一次使用若 macOS 询问麦克风或辅助功能权限，请选择允许。"
pause_before_close "按任意键关闭……"

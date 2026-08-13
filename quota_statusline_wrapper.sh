#!/usr/bin/env bash
# statusLineの入口。quota_statusline.pyへそのまま渡すだけ。
#
# Claude CodeはWindows上でstatusLine.commandをbashスタイルでパースする
# （バックスラッシュはエスケープとして食われ、.cmdは起動しない）。
# そのため bash + フォワードスラッシュのパスで安定して呼ぶ形にしている。
# macOS/Linuxならこのラッパー自体は不要（statusLine.commandに直接
# `python3 -X utf8 /path/to/quota_statusline.py` を指定すればよい）。
python -X utf8 "$(dirname "$0")/quota_statusline.py"

"""Stopフック。5時間クォータが閾値を超えていれば、引き継ぎメモを
書かせるまでターン終了をブロックする。

多重ブロック対策：
- stop_hook_active が立っていれば（＝このフック起因で既に継続中）何もしない
- 引き継ぎファイルが既に存在すれば何もしない（書き終わっているので素直に終了させる）
- 上記に加え、Claude Code自体が8回連続blockで強制的にターンを終える
  セーフティを持っている（公式ドキュメント確認済み）ので、想定漏れがあっても
  無限ループにはならない

キャッシュはstatusLine経由でquota_statusline.pyが書いたものを
読むだけ。外部API呼び出しは行わない。
"""

import json
import sys
import time
from pathlib import Path

CACHE_PATH = Path.home() / ".claude" / "hooks" / "quota_cache.json"
HANDOFF_DIR = Path.home() / ".claude" / "hooks" / "quota_guard_handoffs"

THRESHOLD = 88
STALE_SECONDS = 15 * 60
RESET_SOON_MIN = 15


def safe_id(session_id: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in (session_id or "default"))


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return
    if payload.get("stop_hook_active"):
        return

    try:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return  # キャッシュ不明 → 常に無干渉（フェイルセーフ）

    fetched_at = cache.get("fetched_at")
    if not isinstance(fetched_at, (int, float)) or (time.time() - fetched_at) > STALE_SECONDS:
        return

    used = cache.get("five_hour_used")
    if not isinstance(used, (int, float)) or used < THRESHOLD:
        return

    resets_at = cache.get("five_hour_resets_at")
    if isinstance(resets_at, (int, float)):
        reset_min = (resets_at - time.time()) / 60
        if reset_min <= RESET_SOON_MIN:
            return

    session_id = payload.get("session_id") or "default"
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    handoff_path = HANDOFF_DIR / f"{safe_id(session_id)}.md"

    if handoff_path.exists():
        return  # 既に引き継ぎを書き終えている → 素直に終了させる

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"【5時間クォータ {used:.0f}% 到達】新しいタスクに着手しないこと。"
            f"完了したこと・残っている作業・次にすべきことを"
            f"{handoff_path} にMarkdownで書き出してから、"
            "それ以上の作業をせずターンを終了すること。"
        ),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

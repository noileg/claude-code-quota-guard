"""PreToolUseフック（全ツール対象）。

5時間クォータが閾値に達したことを、そのセッションで最初に検知した
瞬間だけ additionalContext で警告注入する。ブロックはしない
（denyし続けるとモデルが言い回しを変えて再試行し、quota節約のために
quotaを浪費する事故になるため）。

実際に作業を止めさせる強制はquota_guard_stop.py（Stopフック）の役目。
こちらは「早く気づかせる」だけの軽量な役割分担。

キャッシュはstatusLine経由でquota_statusline.pyが書いたものを
読むだけ。外部API呼び出しは行わない。
"""

import json
import sys
import time
from pathlib import Path

CACHE_PATH = Path.home() / ".claude" / "hooks" / "quota_cache.json"
WARNED_DIR = Path.home() / ".claude" / "hooks" / "quota_guard_state"

THRESHOLD = 88
STALE_SECONDS = 15 * 60  # これより古いキャッシュは信用しない（5hウィンドウがリセット済みの可能性）
RESET_SOON_MIN = 15  # あと15分でリセットするなら、待てば済むので介入しない


def safe_id(session_id: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in (session_id or "default"))


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return
    session_id = payload.get("session_id") or "default"

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

    WARNED_DIR.mkdir(parents=True, exist_ok=True)
    flag = WARNED_DIR / f"{safe_id(session_id)}.warned"
    if flag.exists():
        return
    flag.write_text("1", encoding="utf-8")

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"[5時間クォータ警告] 現在の5時間枠の使用率が{used:.0f}%です。"
                "新しい大きなタスクには着手せず、区切りの良いところで"
                "作業内容の要約（完了/未完了/次の一手）を残してターンを"
                "終える準備をしてください。"
            ),
        }
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

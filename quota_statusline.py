"""statusLineの本体。表示とキャッシュ書き出しを1つにまとめたスクリプト。

statusLineへ渡ってくるstdin JSON中の公式フィールドのみを使う
（context_window.used_percentage, rate_limits.five_hour/seven_day）。
外部API呼び出し・OAuthトークンの読み取りは一切行わない。

rate_limitsのキャッシュ書き出しは、quota_guard_pretool.py / quota_guard_stop.py
（閾値到達時の強制引き継ぎフック）が読むデータ元を兼ねる。表示を消しても
このキャッシュ書き出しだけは残す必要がある（消すとフックが道連れで無効化される）。
"""

import json
import sys
import time
from pathlib import Path

CACHE_PATH = Path.home() / ".claude" / "hooks" / "quota_cache.json"


def fmt_pct(value):
    if not isinstance(value, (int, float)):
        return "--"
    return f"{value:.0f}%"


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print("Claude")
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("Claude")
        return

    model = "Claude"
    try:
        model = data.get("model", {}).get("display_name") or model
    except AttributeError:
        pass

    ctx_used = data.get("context_window", {}).get("used_percentage")

    rate_limits = data.get("rate_limits")
    five_used = seven_used = None
    reset_min = None
    if isinstance(rate_limits, dict):
        five = rate_limits.get("five_hour") or {}
        seven = rate_limits.get("seven_day") or {}
        five_used = five.get("used_percentage")
        seven_used = seven.get("used_percentage")
        resets_at = five.get("resets_at")
        if isinstance(resets_at, (int, float)):
            reset_min = max(0, int((resets_at - time.time()) / 60))

        cache = {
            "five_hour_used": five_used,
            "five_hour_resets_at": resets_at,
            "seven_day_used": seven_used,
            "seven_day_resets_at": seven.get("resets_at"),
            "fetched_at": time.time(),
        }
        try:
            tmp = CACHE_PATH.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            tmp.replace(CACHE_PATH)
        except Exception:
            pass

    reset_str = f"({reset_min}m)" if reset_min is not None else ""
    print(
        f"{model} | context {fmt_pct(ctx_used)} | "
        f"5h {fmt_pct(five_used)}{reset_str} | 7d {fmt_pct(seven_used)}"
    )


if __name__ == "__main__":
    main()

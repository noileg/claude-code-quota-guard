# claude-code-quota-guard

Claude Code の5時間クォータ（`rate_limits.five_hour`、Claude.ai Pro/Max向けの
アカウント全体・複数セッション合算のレート制限）が閾値に達したら、作業を止めて
引き継ぎメモを書かせる仕組み。外部APIコール・OAuthトークンの読み取りは一切行わない。

## 仕組み

Claude Codeの`statusLine`には、公式に`rate_limits.five_hour.used_percentage` /
`resets_at`（`seven_day`も同様）が渡ってくる
（[公式ドキュメント](https://code.claude.com/docs/en/statusline)、
「Available data」節）。ただし`PreToolUse`/`Stop`などのhookの入力には
この情報は含まれない。そこで:

1. `quota_statusline.py` が `statusLine` 呼び出しのたびに `rate_limits` を
   ローカルのキャッシュファイル（`~/.claude/hooks/quota_cache.json`）に書き出す
   （ついでに簡易なステータス行も表示する）
2. `quota_guard_pretool.py`（`PreToolUse`、全ツール対象）が、閾値到達を
   セッション内で最初に検知した瞬間だけ `additionalContext` で警告を注入する
   （ブロックはしない。denyし続けるとモデルが再試行を繰り返し、
   quota節約のためにquotaを浪費する事故になるため）
3. `quota_guard_stop.py`（`Stop`）が、閾値到達中は「完了したこと・残っている
   作業・次の一手」を所定のファイルに書き出すまでターン終了を `decision:"block"`
   で強制する。書き終えれば以後は無干渉

`PreToolUse`は早期検知（ほぼリアルタイム）、`Stop`は実際の強制、という
役割分担。`PreToolUse`はツール呼び出し1回ごとにプロセスが起動するコストが
乗る（実測 約94ms）ので、常時ブロックはせず1セッション1回の警告注入に留めている。

多重発火防止に `stop_hook_active` を見ているが、それに加えて
Claude Code自体が「8回連続blockで強制的にターンを終える」というセーフティを
持っているため、想定漏れがあっても無限ループにはならない。

## フェイルセーフ

以下のいずれかに該当する場合は常に無干渉（ブロックしない）:

- キャッシュファイルが存在しない、または壊れている
- キャッシュが15分より古い（5時間ウィンドウが既にリセットされている可能性があるため）
- リセットまで15分以内（待てば済むため）

## 導入

`~/.claude/settings.json` の `statusLine` と `hooks` に追記する
（既存の設定とはマージすること。配列を丸ごと上書きしない）:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash \"/path/to/claude-code-quota-guard/quota_statusline_wrapper.sh\"",
    "padding": 0
  },
  "hooks": {
    "PreToolUse": [
      {
        "hooks": [
          { "type": "command", "command": "python3 /path/to/claude-code-quota-guard/quota_guard_pretool.py", "timeout": 10 }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "python3 /path/to/claude-code-quota-guard/quota_guard_stop.py", "timeout": 10 }
        ]
      }
    ]
  }
}
```

Windows環境の注意点は `quota_statusline_wrapper.sh` のコメントを参照
（Claude CodeはWindows上で`statusLine.command`をbashスタイルでパースするため、
バックスラッシュ入りのパスや`.cmd`はそのままでは使えない）。

`rate_limits` はClaude.ai Pro/Maxサブスクライバーのみに提供され、セッション内で
最初のAPI応答が返った後に出現する。それまでは `quota_statusline.py` が
`5h --` と表示し、フック側もキャッシュ未生成として無干渉になる。

## 閾値について

既定は88%（90%ではなく）。複数セッションを並行して動かしている場合、
90%到達時に全セッションが同時に引き継ぎを書き始めると残りの枠を
食い潰しかねないため、各スクリプト冒頭の `THRESHOLD` で調整できる。

## 未検証事項

- `hookSpecificOutput.additionalContext` が `PreToolUse` で実際にモデルへ
  どう影響するかは、合成データでのフック単体テストと公式ドキュメントの記載を
  根拠にしており、実運用で閾値到達時に自然発火する場面での確認はまだ十分でない
- macOS/Linuxでは未検証（Windows + Git Bash環境で作成）

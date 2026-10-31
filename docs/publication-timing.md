# 現行運用（2026-10-31更新）

- PR [#112](https://github.com/stvvlab/stvv-lab-auto-post/pull/112)で公開時刻を **JST 08:00 / 18:00 / 23:00 の1日3枠** に変更。従来7枠の記述は以下の履歴節に限る。
- 将来予約の探索範囲は36時間、30分以上先。審査済み候補がなければ予約しない。
- PR [#113](https://github.com/stvvlab/stvv-lab-auto-post/pull/113)で、明示承認・一次情報本文SHA256一致の文章のみのBuffer予約経路を追加。現時点で文章のみのready候補は登録しておらず、実際のBuffer受付・X公開は未実証。画像付きの既存審査・重複防止・pending先行保存・再送禁止は維持。
- GitHub Actionsの6時間超遅延時は安全停止。3枠への削減だけで起動遅延は解消しない。Buffer scheduled/sent とX実表示は区別する。

---

# 公開時刻の改善：既存7枠へのBuffer事前予約

2026-10-27の改善継続指示に基づき、既存7枠の公開時刻を維持したまま、
GitHub開始後の即時送信からBufferの事前予約へ切り替える。
設定・実装と、実際の予約→公開→X表示の成功実績は区別する。

## 遅延の実測

[通常21時枠40340928129](https://github.com/stvvlab/stvv-lab-auto-post/actions/runs/40340928129)：

| 段階 | JST |
| --- | --- |
| 予定枠 | 2026-10-26 21:00:00 |
| GitHub run作成・開始 | 2026-10-26 23:34:59 |
| 実投稿ステップ開始 | 2026-10-26 23:35:31 |
| Buffer受付（返却状態sent） | 2026-10-26 23:35:36 |
| 履歴保存完了 | 2026-10-26 23:35:37 |
| X本文・画像の後続確認 | 2026-10-27 00:10:23 |

大部分はrun作成以前の2時間34分59秒。run作成後のBuffer受付までは約38秒。
GitHub内部で開始が遅れた理由は未特定であり、混雑や障害と断定しない。
[X掲載先](https://x.com/stvvlabo/status/2114727647368331366)。
当時のdelivery-runs記録は送信時点のスナップショットとして保持する。

[通常23時枠40349598794](https://github.com/stvvlab/stvv-lab-auto-post/actions/runs/40349598794)は
2026-10-27 00:28:38 JSTに実投稿ステップを開始（88分38秒遅延）。
検証済み未投稿情報がなく正しくスキップ。新しい送信・pendingはなかった。

## 予約方式と保護

公開時刻：JST08:00/10:30/12:30/15:30/18:00/21:00/23:00。
GitHubの既存7回の通常処理が、30分以上先・最大24時間先の関連する枠へ最大1件を予約する。
`mode:customScheduled`とUTCの`dueAt`を指定する。新しい公開トリガーや手動実行は追加しない。
審査済み情報がなければ何も予約せず、即時送信へ戻さない。

1. 完全一致の審査済み本文・公式出典・固定タグ込み270以下・公開予定日の7日以内条件を確認。
2. 公式本文、厳密な初先発事実と本文ハッシュ、画像のSHA/寸法/immutable公開バイトを確認。
3. 接続先@stvvlabo、予約権限、停止・切断状態、実際の上限と空き容量、リモート重複を読み取り確認。
4. 本文・出典・画像・予定枠・一意キーをpendingとしてmainへ保存してから、一度だけcreatePost。
5. 返却ID・本文・channel・dueAt・画像受付が一致し、scheduledの場合だけreserved_postsへ保存。
6. 後続の通常枠で同じIDを読み取り照合。sentになってからpublication_logへ追加。
7. X本文・画像表示は別途確認し、Buffer受付やsentをX表示確認と呼ばない。

used_postsは予約した枠の占有も表す。公開済み件数はpublication_logとX証跡で判断する。
予約済みの出典・事実は他の枠や旧送信経路でも重複防止対象。
通信タイムアウト、応答不明、保存失敗、内容や時刻の変更、Bufferエラーでは自動再送しない。
IDを受け取れなかったpendingは自動推測で解消せず、照合・確認待ちにする。
レポートのみの競合に限定したgit push再試行は既存state_syncを再利用する。

## 実測した利用可否

[読み取り検証40353229659](https://github.com/stvvlab/stvv-lab-auto-post/actions/runs/40353229659)で
2026-10-27 00:50 JSTに接続先、予約権限、予約上限10件、利用中0件、空き10件と
既存投稿の状態取得を確認。投稿変更・有料API使用・契約変更は0件。
この証拠は予約mutationの成功実測ではない。APIは送信直前にも再確認する。

## 実装と限界

buffer_reservations.pyは読み取りと一度だけの予約送信、advance_reservations.pyは
pending・予約・sentの状態遷移、delivery_run.pyは通常枠の実行証跡を担当する。
reservation_preview.pyは引き続き送信しない計算用。全体の通常送信はmain.ymlで有効化する。
reservation-capability.ymlはコード更新時の読み取り検証のみで、送信しない。

現在の審査済み未投稿画像は0件。新しい正規の候補ができてから、予約→定刻公開→X本文・
画像表示を複数枠で実測する必要がある。事前予約があれば公開をGitHub起動から分離できるが、
画像準備・予約自体が遅れたり、Buffer側が遅れたりした場合の定刻公開は保証できない。
安定運用達成とはまだ扱わない。補足リプの送信経路は別件の未完了事項として維持する。

公式仕様：
- https://developers.buffer.com/examples/create-scheduled-post.html
- https://developers.buffer.com/guides/posts-and-scheduling.html
- https://developers.buffer.com/types/Channel.html
- https://developers.buffer.com/types/ChannelAction.html
- https://developers.buffer.com/types/OrganizationLimits.html

## 予約後の画像同一性（2026-10-27）

予約受付で返された画像asset IDをreserved_posts.buffer_asset_idsへ保存し、
後続の状態確認でも同じIDであることを必須にする。画像1件が存在するだけでは
同一画像とは扱わない。本文・日時が一致しても画像IDが違えば、sentを公開履歴へ
追加せず停止し、自動再送しない。ID未保存の既存レコードも暗黙に承認しない。
この照合はX表示や画像バイトの目視確認の代用ではない。

## 2026-10-27 08時枠の実測

通常run 40418810614は08:18:14 JSTに作成され、実投稿ステップは08:18:38に開始（18分38秒遅延）。advance_reservations方式で起動し、ready=0のためskipped_no_verified_content。新規予約・公開・pendingは0件で、delivery-runs/40418810614.jsonとlatestの保存を確認した。これは通常枠の起動・正しいスキップ・証跡保存の実測であり、実予約→Buffer sent→X表示の証明ではない。278テストの出力と実投稿ステップの結果は区別する。

## Bufferのdraft状態と取消主体の区別（2026-10-30）

予約済み投稿をBufferの読み取りAPIで再照合した際、statusが`draft`になっている場合は、**予約が維持されていないことだけ**を確定できる。ユーザー自身が取り消したのか、Buffer側の操作・状態変更なのかは、この応答だけでは特定できない。以前の`cancelled_by_user`は取消主体を推定した不適切なラベルであり、過去の台帳に残る同ラベルも利用者の取消を証明しない。

新規の遷移は`draft_no_longer_scheduled`として記録する。既存`cancelled_by_user`は互換性のため終端状態として読み取るが、報告では`buffer_draft_not_scheduled_x_unverified`とする。どちらも公開成功ではなく、元の予約枠は使用済みのまま保持し、**再送・再予約・取消を自動実行しない**。原因や操作主体を特定するには別の監査証跡が必要。

---
title: 通知が難しい理由
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: Home Assistant で 1 つの通知をメール、Telegram、モバイルプッシュ、SMS に同時に送るのがなぜ難しいのか。通知アクションのさまざまなスタイルと、各インテグレーションがそれらをどう使っているかの一覧つき
---
# Home Assistant で通知が難しい理由

このページでは、Home Assistant で 1 つのメッセージを複数のチャネルに送ることが、見た目よりも難しい理由を説明します。これが
Supernotify の存在理由であり、同時に、通知をもっと簡単にしようという Home Assistant の現在の取り組みへの貢献も意図しています。
内容は Home Assistant **2026.11** をソースコードで確認したものです。リリースのたびに notify エンティティへ移行するインテグレーションが
増えるため、[表](#integrations-and-their-styles)のいくつかの行は今後変わります。

## 「グループを使えばいいのでは？」 { #why-cant-i-just-use-a-group }

1 つのアラートを、自分のスマートフォン、自分のメール、家族の Telegram チャット、そしてスマートフォンを持たない人への SMS に
届けたいとします。Home Assistant には notify グループがあるので、この 4 つでグループを作ってそこに送るのが自然に思えます。
notify グループには 2 種類ありますが、どちらも 4 つすべてを入れることはできません。

**Notify グループヘルパー**は UI で作成し、**notify エンティティ**をまとめて `notify.send_message` で送信します。
Companion App、SMTP、Telegram ボットには notify エンティティがあるので、4 つのうち 3 つは入れられます。SMS は入れられません。
Twilio SMS や ClickSend などの SMS インテグレーションには、古いスタイルの notify アクションしかないからです。グループが送るのは
`message` と `title` だけで、タイトルに対応していないメンバーが 1 つでもあれば、全員に対してタイトルを外します。カメラの
スナップショット、スマートフォンの通知のボタン、HTML のメール本文などを追加する方法はありません。

**古い notify グループ**は YAML 専用で、`notify.mobile_app_annas_phone` や `notify.smtp` のような古い **notify アクション**を
まとめます。Telegram は入れられません。Telegram の notify アクションは 2026.11 で削除され、notify エンティティだけが残っている
からです。残りの 3 つは入れられますが、どのメンバーも同じ呼び出しを受け取ります。

- `target` の意味はメンバーごとに違います。SMTP ではメールアドレス、Twilio では電話番号で、スマートフォン専用のアクションは
  これを無視します。1 つの `target` ですべてに正しく対応することはできません。
- `data` は、どんなキーが入っていてもすべてのメンバーに送られます。画像は Companion App では `data.image`、SMTP では
  `data.images`(ローカルファイルのリスト)、Twilio SMS では `data.media_url` です。各メンバーは自分用のキーに加えて、
  他のメンバー用のキーも受け取ります。
- 各メンバーには YAML で固定の `data` を設定できますが、このアラート用の画像のように、通知ごとに変わるデータは設定できません。

どちらのグループも、誰に通知しているのかを知りません。スマートフォンを買い替えたらグループを編集する必要があります。誰かが外出中の
ときや、家にいる人だけに送りたいときも、グループには判断できません。グループは送り先の固定リストにすぎません。

## なぜこうなっているのか { #why-its-like-this }

これは誰かのミスではありません。Home Assistant には 10 年間で数百もの通知インテグレーションが加わり、それぞれが自分のサービスの
必要に合わせて作られてきました。そして通知の共通部分は、ずっととても小さいままでした。

- **共通なのは `message` だけです。** `title` はほとんどのアクションにあります。`target` はあるスタイルにはあっても他には
  なく、インテグレーションごとに意味が違います。それ以外のすべて(画像、ボタン、優先度、サウンド、HTML、添付ファイル、タップ時の
  動作)は、古いスタイルでは自由形式の `data` キーの下に、新しいスタイルではインテグレーション独自のアクションのフィールドに
  入ります。これらを扱う共通のスキーマはありません。
- **同じものに別々の名前がついています。** タップ時の動作は、同じ Companion App でも iOS では `data.url`、Android では
  `data.clickAction` です。ntfy では `click`、Prowl と Pushover では `url` です。優先度は Pushover と Prowl では `-2` から
  `2`、ntfy では `1` から `5`、LaMetric では `info`/`warning`/`critical`、iOS の Companion App では `push` の下の
  `interruption-level` です。
- **送り先ごとにアクションがあるサービスもあります。** Companion App の古いスタイルでは、スマートフォンごとに
  `notify.mobile_app_<device>` アクションが作られるため、アクション名そのものが送り先になります。オートメーションは人ではなく
  スマートフォンを指定することになり、スマートフォンを買い替えるたびに変更が必要です。
- **2 つのスタイルを同時に持つサービスもあります。** 新しいインテグレーションは notify エンティティを提供し、これは
  `notify.send_message`、エリア、ラベル、グループで使えますが、送れるのはメッセージとタイトルだけです。それ以外のために、
  `smtp.send_message` や `ntfy.publish` のように、同じエンティティを対象とする独自のアクションを追加しています。画像を送るには、
  共通のアクションを離れてインテグレーション独自のアクションを使う必要があります。
- **音声、チャイム、画面上のメッセージはさらに別です。** `tts.speak`、`persistent_notification.create`、
  `alexa_devices.send_sound`、`mqtt.publish` はそれぞれ独自の形と送り先を持ち、どれも notify アクションではありません。

notify エンティティは正しい方向です。エリア、ラベル、デバイスで指定でき、UI にも正しく表示されます。ただし、まだメッセージと
タイトル以外は送れず、多くのインテグレーション、特に SMS はまだ移行していません。

## 通知アクションのスタイル { #the-styles-of-notification-action }

### 1. サービスごとの古い notify アクション { #1-legacy-notify-action-for-a-service }

設定したサービスごとに 1 つのアクションがあり、`message`、`title`、`target`、自由形式の `data` という共通の形を持ちます。
`target` の意味と `data` のキーは各インテグレーションが決めます。

```yaml
action: notify.smtp
data:
  title: Front door
  message: The front door has been open for 10 minutes
  target:
    - anna@example.com
  data:
    images:
      - /config/www/snapshots/front_door.jpg
```

Twilio SMS の同じアクションでは、`target` に電話番号を、`data` に `media_url` を指定します。

### 2. デバイスごとの古い notify アクション { #2-legacy-notify-action-for-a-device }

形はスタイル 1 と同じですが、インテグレーションがデバイスごとにアクションを作るため、送り先がアクション名に含まれます。代表例は
Companion App で、スマートフォンごとに `notify.mobile_app_<device>` があり、iOS と Android で `data` のキーが異なります。

```yaml
action: notify.mobile_app_annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
  data:
    image: /api/camera_proxy/camera.front_door
    url: /lovelace/doors          # iOS
    clickAction: /lovelace/doors  # Android
    actions:
      - action: CLOSE_DOOR
        title: Close it
```

### 3. `notify.send_message` と notify エンティティ { #3-notify-entity-with-notifysend_message }

すべての notify エンティティに共通の 1 つのアクションで、エンティティ、デバイス、エリア、ラベルで送り先を指定でき、UI の
エディターでも完全にサポートされています。受け取るのは `message` と `title` だけで、タイトルは対応を宣言しているエンティティ
だけが使います。`data` はありません。

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. notify エンティティを対象とするインテグレーション独自のアクション { #4-the-integrations-own-action-aimed-at-its-notify-entity }

送り先にはインテグレーションの notify エンティティを使い、`notify.send_message` では送れないものすべてのために、
インテグレーションがフラットなフィールドを持つ独自のアクションを追加します。フィールドはインテグレーションごとに異なります。

```yaml
action: ntfy.publish
target:
  entity_id: notify.ntfy_alerts
data:
  title: Front door
  message: The front door has been open for 10 minutes
  priority: 4
  click: https://my.home/lovelace/doors
  attach: https://my.home/local/snapshots/front_door.jpg
```

`smtp.send_message`、`html5.send_message`、`prowl.send_message`、`nfandroidtv.send_message`、`telegram_bot.send_*`
アクションも同じ仕組みで、それぞれフィールドが異なります。

### 5. 独自の送り先を持つインテグレーション独自のアクション { #5-the-integrations-own-action-with-its-own-targets }

notify にはまったく基づかず、独自の方法で送り先を選ぶアクションです。送り先はデバイス、ルーム、トピック、あるいは TTS エンジンと
組み合わせたメディアプレーヤーなどです。

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

ほかに `lametric.message`(`device_id` で指定)、`alexa_devices.send_sound`(`device_id` で指定)、`matrix.send_message`
(ルームで指定)、`mqtt.publish`(トピックで指定)、`persistent_notification.create`(送り先なし、Home Assistant の UI に
表示)があります。

### 6. グループ { #6-groups }

2 種類の notify グループについては[上](#why-cant-i-just-use-a-group)で説明しています。Notify グループヘルパーは、
スタイル 3 で使う notify エンティティです。古い notify グループは、スタイル 1 または 2 の他のアクションを呼び出す
スタイル 1 のアクションです。

## インテグレーションとそのスタイル { #integrations-and-their-styles }

Home Assistant 2026.11。**両方** は、そのインテグレーションに 2 つのスタイルがあることを示します。notify エンティティが簡単な方で、
メッセージとタイトル以外を送るにはもう一方が必要です。

| インテグレーション        | 古いアクション (1 または 2)               | notify エンティティ (3)          | 独自のアクション (4 または 5)                     | メッセージとタイトル以外                           |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **両方**、スマートフォンごと      | -                                                | 古い `data`: `image`、`actions`、`url` (iOS)、`clickAction` (Android)、`push` |
| SMTP (メール)            | `notify.<name>`、`target` = アドレス      | **両方**、受信者ごと              | `smtp.send_message` (4)                          | 古い `data.images`、`data.html`、独自のアクション `html`、`attachments`、`priority` |
| Telegram ボット          | 2026.11 で削除                            | あり、チャットごと                | `telegram_bot.send_message`、`send_photo`、... (4) | 独自のアクション: `keyboard`、`inline_keyboard`、`parse_mode`、写真やファイルは別アクション |
| Twilio SMS              | `notify.<name>`、`target` = 電話番号      | なし                            | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`、`target` = 電話番号      | なし                            | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`、`target` = 電話番号      | なし                            | -                                                | `data.attachments`、`data.urls`、`data.text_mode` |
| Pushover                | `notify.<name>`、`target` = デバイス      | なし                            | -                                                | `data.priority`、`sound`、`url`、`attachment`、`html`、... |
| Slack                   | `notify.<name>`、`target` = チャンネル    | なし                            | -                                                | `data.blocks`、`data.file`                        |
| Discord                 | `notify.discord`、`target` = チャンネル ID | **両方**、チャンネルごと、タイトルなし | -                                           | 古い `data.images`、`data.embed`、`data.urls`      |
| Matrix                  | `notify.<name>`、`target` = ルーム        | なし                            | `matrix.send_message` (5)                        | `data.images`                                     |
| HTML5 プッシュ           | `notify.<name>`、`target` = 登録          | **両方**                         | `html5.send_message` (4)                         | 独自のアクション: `image`、`icon`、`actions`、`urgency`、`ttl`、... |
| ntfy                    | -                                        | **両方**                         | `ntfy.publish` (4)                               | 独自のアクション: `priority`、`tags`、`click`、`attach`、`actions`、... |
| Prowl                   | `notify.<name>`、非推奨                   | **両方**、タイトルなし            | `prowl.send_message` (4)                         | 独自のアクション: `priority`、`url`                |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **両方**                         | `nfandroidtv.send_message` (4)                   | 独自のアクション: `image`、`icon`、`duration`、`position`、... |
| LaMetric                | `notify.<name>`                          | **両方**、タイトルなし            | `lametric.message` デバイスで指定 (5)             | `icon`、`sound`、`cycles`、`priority`             |
| Kodi                    | `notify.<name>`                          | なし (提案中)                    | -                                                | `data.icon`、`data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | なし                            | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **両方**、デバイスごとに読み上げとアナウンス | `alexa_devices.send_sound` デバイスで指定 (5) | サウンドは独自のアクションのみ                  |
| 音声合成 (TTS)           | `notify.<name>` (YAML `platform: tts`)   | なし                            | `tts.speak` (5)                                  | `media_player_entity_id`、`language`、`options`   |
| 永続通知                 | `notify.persistent_notification`         | なし                            | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | あり、タイトルなし                | `mqtt.publish` トピックで指定 (5)                 | 任意のペイロード                                   |

## デバイスではなく人に通知する { #notifying-a-person-not-a-device }

Home Assistant は、各人物が誰で、どのデバイストラッカーがその人を追跡しているかは知っていますが、その人への連絡方法は知りません。
Home Assistant チームは、コミュニティの「What the Heck?」ディスカッション
[Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879) を受けて、
[アーキテクチャディスカッション #1552](https://github.com/home-assistant/architecture/discussions/1552) の提案でこれに
取り組んでいます。各人物に notify エンティティのリストを持たせ、`notify.send_message` を `person.anna` に送れるようにする
というものです。これにより、すべてのオートメーションでスマートフォンを差し替えるという日常的な最大の問題が解決し、notify
エンティティが人に連絡するための自然な方法になります。

Supernotify は、これがリリースされたらできるだけ早く対応します。人物にリンクされた notify エンティティを通じてその人に送ることと、
人物宛ての `notify.send_message` を Supernotify 独自のルーティングに通すことの両方に対応する予定です。

## Supernotify ができること { #what-supernotify-does-about-it }

Supernotify は、1 つのオプションセットを持つ 1 つの通知を受け取り、チャネルごとに適切な呼び出しに変換します。

- **すべてを 1 つのアクションで。** `supernotify.notify` はメッセージ、タイトル、画像、ボタン、優先度を一度だけ受け取り、各
  [transport](../../transports/index.md) が、そのチャネルで対応できるものを、インテグレーションが必要とするスタイル、
  フィールド名、送り先に合わせて変換します。古いアクション、notify エンティティ、独自のアクション、TTS のいずれにも対応します。
- **デバイスではなく人。** [Recipients](../../configuration/people.md) は各人のメールアドレス、電話番号、Telegram チャット
  などを保持し、Companion App のスマートフォンは自動的に見つかります。`person.anna` に通知すれば、各チャネルが正しい宛先を
  受け取ります。各 recipient には専用の notify エンティティもあります。
- **誰に届けるか。** 通知を在宅中の人だけ、あるいは外出中の人だけに送ったり、他のチャネルや他の人にフォールバックしたりできます。
  レシピ[在宅状況によるルーティングとフォールバック](../../recipes/presence_routing_with_fallback.md)を参照してください。
- **何についての通知か。** [Scenarios](../../configuration/scenarios.md) と優先度によって使うチャネルが決まるため、優先度の
  低いメッセージはスマートフォンだけに、重大なメッセージはチャイムも鳴らしてスピーカーでも読み上げる、といったことができます。
- **繰り返しすぎない。** [スヌーズ](../../usage/snoozing.md)と[重複検出](../../configuration/dupe_detection.md)で、同じ
  アラートが繰り返されるのを防ぎます。

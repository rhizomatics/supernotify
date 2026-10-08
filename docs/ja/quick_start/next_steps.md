---
title: 次にやること
tags:
  - quickstart
  - automation
  - dashboard
  - recipes
description: 最初の Supernotify 通知のあとにやること - オートメーションから通知する、ダッシュボードを追加する、誰に何を通知するかを選ぶ、レシピでアイデアを探す
---
# 次にやること

まずはオートメーションから始めましょう。通知はそのためにあります。残りは任意で、どの順番で行ってもかまいません。

## オートメーションに通知を追加する { #add-a-notification-to-an-automation }

`supernotify.notify` はほかのアクションと同じなので、通常どおりオートメーションに追加できます。この例では、廊下の人感センサーが反応したときに通知を送ります。

人感センサーをトリガーにしたオートメーションを作成し、**アクションを追加** を選んで Supernotify を検索します。

![アクションの選択](../../assets/images/add_action_automation.png){width=600}

メッセージを入力し、[最初の通知](first_notification.md)で使ったターゲットや delivery など、必要なものを指定します。

![アクションの設定](../../assets/images/automation_action_simple.png){width=600}

```yaml title="人感センサーのオートメーション"
alias: Hallway motion notification
triggers:
  - trigger: state
    entity_id: binary_sensor.hallway_motion
    to: "on"
actions:
  - action: supernotify.notify
    data:
      title: Motion detected
      message: Something is moving in the hallway
      target: person.john_mcdoe
```

スピーカーでも聞けるようにするには、`alexa_devices_announce_all` と `mobile_push` を delivery に追加します。このアクションでできるその他のことは、[通知を送る](../../usage/notifying.md)にまとめてあります。

音声アナウンスとカメラ画像を使った、より詳しい実例は、レシピ[玄関に誰か来た](../../recipes/someone_at_the_door.md)を参照してください。

## ダッシュボードを追加する { #add-a-dashboard }

[Supernotify Cards](https://github.com/lollox80/supernotify-cards) には、通知の制御と監視、手動送信、設定のテストに使える専用のダッシュボードカードが数多くあります。

![概要カードと transport カード](../../assets/images/cards.png)

[Dashboard](../../configuration/dashboard.md) のページに、新しいダッシュボードへ貼り付けられる完全な例があります。貼り付けたあとは画面上で編集できます。

## 人と delivery をオン・オフする { #switch-people-and-deliveries-on-and-off }

Supernotify が把握している人には、それぞれ Home Assistant の `switch` エンティティがあり、delivery にもそれぞれあります。オフにすれば、オートメーションを変更せずに、特定の人への通知を止めたり、スピーカーをしばらく静かにしたりできます。

## 一部のデバイスだけに通知する { #notify-just-some-devices }

ターゲットには、人やデバイスのほかに**エリア**、**フロア**、**ラベル**も指定できます。そのため、1階のスピーカーだけ、あるいはキッチン用のラベルが付いたものすべてに通知を送れます。[Targets](../../usage/targets.md) と、よくある質問をまとめた [FAQ](../../faqs.md) を参照してください。

## 設定を調整する { #tune-the-settings }

アーカイブ、重複検出、ハウスキーピングは、**設定 → デバイスとサービス** にある統合の **設定** オプションから変更できます。[アーカイブ](../../configuration/archiving.md)と[重複検出](../../configuration/dupe_detection.md)を参照してください。

## アイデアを探す { #be-inspired }

設定例つきのアイデアが[レシピ](../../recipes/index.md)にたくさんあります。

## YAML でさらに先へ { #go-further-with-yaml }

YAML で少し設定すると、できることが増えます。いずれも任意です。

- 人にメールアドレスや電話番号を設定する - [People](../../configuration/people.md)
- HTML メールや決まったスピーカーの組み合わせなど、独自の delivery を作る - [Deliveries](../../configuration/deliveries.md)
- 夜間や誰も家にいないときの通知の動作を変える - [Scenarios](../../configuration/scenarios.md)
- カメラのスナップショットを添付する - [Multimedia](../../configuration/multimedia.md)

これらの背景にある考え方は[高度なコンセプト](advanced_concepts.md)で説明しており、リファレンスは[設定](../../configuration/index.md)にあります。

## 助けを求める { #get-help }

[Discussions](https://github.com/rhizomatics/supernotify/discussions) のページで質問するか、AI エージェントを使ってください - [FAQ](../../faqs.md) の最後の回答を参照してください。

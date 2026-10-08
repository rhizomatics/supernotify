---
title: 最初の通知を送る
tags:
  - quickstart
  - developer tools
  - notification
description: Home Assistant から最初の Supernotify 通知を送ります - 全員に、1人に、そして Alexa スピーカーに
---
# 最初の通知を送る

このページの作業は、[インストール](installation.md)の直後に、すべて Home Assistant の UI で行います。YAML を使いたい人のために、各ステップに YAML も載せています。

## 1. 全員に通知する { #1-notify-everyone }

**開発者ツール** の[アクションタブ](https://www.home-assistant.io/docs/tools/dev-tools/#actions-tab)を開き、`supernotify.notify` アクションを選んでメッセージを入力し、**アクションを実行** を押します。

![開発者ツールのアクション](../../assets/images/tools_action_notify.png){width=600}

```yaml title="全員へのメッセージ"
action: supernotify.notify
data:
  message: Something went off in the basement
```

通知に必要なのはメッセージだけです。ほかに何も指定しなければ、家にいる全員の、Home Assistant アプリが入ったすべてのスマートフォンとタブレットに届きます。

## 2. 1人に通知する { #2-notify-one-person }

おそらく、届けたい相手より多すぎるはずです。絞り込むには、`person` エンティティ、または個別のモバイルデバイスを**ターゲット**（target）として選びます。

![1人のすべてのモバイルデバイスに通知する](../../assets/images/person_notify.png){width=400}

```yaml title="1人へのメッセージ"
action: supernotify.notify
data:
  message: Something went off in the basement
  target: person.john_mcdoe
```

これで John のデバイスだけに届きます。スマートフォンではなく人を選んでおけば、John が機種変更しても通知は届き続けます。

## 3. 送り方を選ぶ { #3-choose-how-its-sent }

**Delivery** 欄には、Supernotify が見つけた通知の送り方が並びます。指定しなければ Supernotify が選び、ここで選べば選んだものだけが使われます。

![Delivery の選択](../../assets/images/delivery_choice.png)

Alexa デバイスがある場合は、`alexa_devices_announce_all` か `alexa_devices_speak_all` を使います（announce は冒頭にチャイムが鳴り、speak は鳴りません）。これらは、メールやモバイルアプリの通知と1つの通知の中で組み合わせられます。

```yaml title="スピーカーとスマートフォンを同時に"
action: supernotify.notify
data:
  message: Someone is at the front door
  delivery:
    - alexa_devices_announce_all
    - mobile_push
```

それぞれに合った通知が届くので、スピーカーはメッセージを読み上げ、スマートフォンはそれを表示します。

ここまで動いたら、次は[オートメーションに通知を追加](next_steps.md#add-a-notification-to-an-automation)します。

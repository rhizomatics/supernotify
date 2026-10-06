---
title: 基本コンセプト
tags:
  - quickstart
  - delivery
  - target
  - recipient
  - priority
description: 使い始めるのに必要な Supernotify の少数のコンセプト - ターゲット、recipient、delivery、優先度と、その関係
---
# 基本コンセプト

## 全体の仕組み { #how-it-fits-together }

オートメーションからの1つの通知は、送り方に合わせて形を整えた、複数の異なる通知になることがあります。

![オートメーションからの1つの通知が、メール、2つのプッシュ通知、SMS、スピーカーでのアナウンスになる様子](../../assets/images/concepts_flow.svg)

図を左から右へ読むと、次のようになります。

1. **誰に通知するか** - [ターゲット](#target)です。人は、[recipient](#recipient) の情報をもとに、連絡可能な手段に変換されます
2. **Delivery** - 該当する [delivery](#delivery) が、既定で、またはあなたの指定によって選ばれます
3. **通知** - 各 delivery は使えるターゲットを取り出し、それに適した通知を送ります。そのため、メールは画像付きの本格的な HTML レイアウトにでき、キッチンのスピーカーには短い音声メッセージが届きます

UI だけで使う場合、3つの言葉でほぼすべてを説明できます。

## ターゲット (Target) { #target }

ターゲットは、**誰に、または何に通知するか**です。人、スマートフォン、スピーカー、メールアドレスのほか、複数のデバイスを表すエリア、フロア、ラベルも指定できます。

ターゲットを指定しなければ、通知は全員に届きます。

## 受信者 (Recipient) { #recipient }

recipient は、**Supernotify が把握している人**です。その人のスマートフォンやタブレットと、必要に応じてメールアドレスや電話番号を持ちます。recipient は Home Assistant の *Person* エンティティから自動的に見つかります。

recipient は別の種類のターゲットではありません。人はターゲットになれるもののひとつで、Supernotify はその人への連絡方法を recipient から調べます。だから `person.joe_mctest` がターゲットとして使え、Joe のメールアドレスをすべてのオートメーションに書く必要がないのです。

## 配信 (Delivery) { #delivery }

delivery は、**通知を送る1つの方法**で、`mobile_push`、`email`、`alexa_devices_announce_all` のような名前が付いています。Supernotify は Home Assistant で見つけたものに合わせて delivery を作成し、それらが `supernotify.notify` アクションの **Delivery** 欄に表示されます。

delivery を指定しなければ、モバイルプッシュやメールのように、送り先を自分で判断できる delivery が使われます。

## 優先度 (Priority) { #priority }

優先度は、**通知がどれだけ緊急か**を表し、`minimum`、`low`、`medium`、`high`、`critical` の5段階があります。指定は任意で、省略すると `medium` になります。優先度は、スマートフォンやメールソフトなど、それを理解できるものに引き渡されます。

## あとで知ればよい、もう2つ { #two-more-for-later }

どちらもドキュメントのあちこちに出てきますが、使い始めるのに必要ではありません。

- **transport** は delivery の背後にある技術的な手段で、通常はモバイルアプリ、SMTP、Alexa Devices などの Home Assistant 統合です。delivery は transport にその設定を組み合わせたものなので、1つの transport に、通常の `email` と `html_email` のように複数の delivery を持たせられます。
- **scenario** は名前の付いた設定のまとまりで、どの delivery を使うか、どう動作するかを変えます。たとえば夜間は控えめにする、といった使い方です。scenario は YAML で設定します。

この2つと、YAML 設定でできるその他のことは、[高度なコンセプト](advanced_concepts.md)で扱っています。

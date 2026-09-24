---
tags:
  - transport
  - delivery
  - scenario
  - target
  - recipient
  - principles
description: Home Assistant用Supernotifyのコアコンセプト（Transport、Delivery、Scenario、Recipientなど）
---
# コアコンセプト

## 全体の仕組み { #how-it-fits-together }

オートメーションからの1つの通知が、送信方法に合わせて形を変えた、複数の異なる通知になります。

![オートメーションからの1つの通知が、メール、2つのプッシュ通知、SMS、スピーカーでのアナウンスになる様子](../assets/images/concepts_flow.svg)

1. **ターゲット** - 人は、[Recipient](#recipient)の情報をもとに、連絡可能な手段に変換されます
2. **Deliveries** - 該当する[Deliveries](#delivery)が、デフォルトまたは[Scenarios](#scenario)によって選ばれます
3. **通知** - 各deliveryは使えるターゲットを取り出し、それに適した通知を送ります。
   そのため、メールは画像付きの本格的なHTMLレイアウトにでき、キッチンのスピーカーには短い音声メッセージが届きます

## ターゲット (Target) { #target }
- 誰に、または何に、どのように通知するか
  - *直接*ターゲット
    - メールアドレス
    - 電話番号
    - `entity_id` または `device_id`（例：Alexaデバイスでアナウンスする場合）
    - Telegramなどの専用transport向けのカスタムID
  - 直接ターゲットに変換できる*間接*ターゲット
    - *Recipient*機能を使うための `person_id`
    - Home Assistant標準のターゲットセレクター `label_id`、`floor_id`、`area_id`
    - *グループ*ターゲット（Home Assistantの新旧両方のグループ）
- ターゲットには `discord_channel:839439434` のように特定の**ターゲットカテゴリ**を指定できます。詳しくは[カテゴリ接頭辞](../usage/targets.md#category-prefixes)をご覧ください
- 各ターゲットは、それを最もうまく扱えるインテグレーションがリストから取り出します
  - たとえば、Alexa DevicesのNotifyエンティティはAlexa Devices transportが処理し、一般的なNotifyエンティティは機能の少ないNotify Entity transportが処理します
- 詳しくは[Targets](../usage/targets.md)をご覧ください

## 受信者 (Recipient) { #recipient }
- 人。メールアドレス、電話番号、モバイルデバイス、カスタムターゲットを任意で持てます
  - デフォルトでは、Home Assistantに既にあるユーザーアカウントとPersonエンティティから自動検出されます
- オートメーションで人を指定しやすくなります。すべての通知でJoeのメールアドレスを覚えておく代わりに `person.joe_mctest` を使えます。対応するSMSインテグレーションがあれば電話番号にも、TelegramやDiscordなどのカスタム識別子にも使えます
- 各受信者にはHome Assistantの `switch` エンティティもあり、特定の人への通知を簡単に止められます
- 詳しくは[People](../configuration/people.md)と[Recipes](../recipes/index.md)をご覧ください

## トランスポート (Transport) { #transport }

- *Transport*は実際に通知を行う技術的な手段で、通常は既にインストールされているHome Assistantのインテグレーションを使います
- *Transportアダプター*こそが、通常のNotifyグループとSupernotifyの違いです
  - Notifyグループは複数チャネルへの通知を簡単にできるように見えますが、実際にはtransportごとに `data` の構造（`data` の中の `data` も！）やアドレス指定などが異なるため、結局 `message` だけのような最小限の共通属性に絞らざるを得ません
- Supernotifyには、メール、モバイルプッシュ、SMS、Alexaなど一般的なtransport用のアダプターが標準で用意されており、他のあらゆるHome Assistantアクションをラップできる*Generic*アダプターもあります
- Transportアダプターにより、インターフェースが互いに異なり互換性がない複数のプラットフォームにも、1つの通知を送れます
- 通知をtransportに合わせて調整し、受け付けない属性を除き、`data` 構造を組み替え、適切なターゲットだけを選び、可能な場合はさらに細かな調整もできます
- 各transportにはデフォルト設定があり、多くの調整やデフォルト値を設定できるので、同じ値をすべての通知に書く必要がありません
- 詳しくは[Transports](../transports/index.md)をご覧ください

## 配信 (Delivery) { #delivery }

- **Delivery**は、使いたい各通知チャネルを定義します
  - 標準で、各transportには同じ名前のdeliveryがあります（例：`email`、`mobile_push`）
  - 一部のtransportは、`alexa_devices_announce_all` や `chime_siren_all` のような追加のdeliveryを自動作成します
  - YAMLを使えば、プレーンテキストの `email` に加えて `html_email` を作ったり、特定の音声アシスタント用のdeliveryを作ったりできます
- メール、モバイルプッシュ、SMS、Alexa Devices、Notify Entityのように、ターゲットを明確に選べるtransportは、デフォルトでターゲット処理に含まれます
  - その他は、設定、Scenarios、または通知での指定によって含めることができます
- 好きな名前で独自のdeliveryを定義でき、1つのtransportに複数のdeliveryを持たせることもできます（例：`plain_email` と `html_email`）
- [Generic Transport](../transports/generic.md)は、標準transportでまだ対応していない、Home Assistantでできるほぼすべてのことにdeliveryを作るための*ツールボックス*です
- 詳しくは[Deliveries](../configuration/deliveries.md)と[Recipes](../recipes/index.md)をご覧ください

## シナリオ (Scenario) { #scenario }
- 名前で、またはHome Assistantの条件によって自動的に有効にできる設定のパッケージ
- Scenariosは、通知の `data` ブロックの `apply_scenarios` 値で手動選択するか、Home Assistant標準の `conditions` ブロックで自動選択できます
  - 条件にはメッセージのテキストも含まれるため、テラスの鳥に関するFrigateの通知と、窓辺の不審者とで扱いを変えられます
- Scenariosを使えば、夜間は通知を控えめに、祝日は華やかに、または特定のメッセージを優先することができます
- 多くのdeliveryや通知に対する変更を1か所で適用でき、オートメーションでの通知呼び出しを大幅にシンプルにする鍵となります
- 詳しくは[Scenarios](../configuration/scenarios.md)と[Recipes](../recipes/index.md)をご覧ください

## 優先度 (Priority) { #priority }
- 通知の緊急度
   - Home Assistantの内外を問わず、通知の優先度付けに標準的な方法はありません
   - Supernotifyには、一般的な慣習に沿った独自の5段階の方式があり、`minimum` から `critical` まであります
   - 優先度はscenarioやdeliveryのルールに使え、対応するnotifyインテグレーションにも渡せます
   - Supernotifyには独自のメールインテグレーションがあり、優先度をOutlookやApple Mailなどが理解できる形に変換します

!!! info
    技術的な詳細に興味がある方向けに、これらのコンセプトに対応するコアクラスの[クラス図](../developer/class_diagram.md)があります。

# 基本原則 { #core-principles }

1. 通知に必要なのはメッセージだけです。すべてのターゲットを含め、それ以外はすべてデフォルトにできます
2. アクション呼び出しで指定したものは、デフォルトより優先されます
   - これは `target_usage` などのオプションで調整できます
   - 人物レジストリがターゲット生成に使われるのは、ターゲットが指定されていない場合だけです
3. 設定とデフォルトの優先順位は Action > Scenario > Delivery > Transport
4. 設定方法や呼び出し方にできるだけこだわらない
   - ターゲットはサブカテゴリに分けても、エンティティID、デバイスID、メールアドレス、電話番号の大きなリストでも構いません
   - `delivery` などのアクション `data` オプションは、単一の値、リスト、辞書のいずれでも指定できます

## 開発者向け { #developers }

通知がdelivery、ターゲット、*Envelope*をどう流れるかは[Developer Concepts](../developer/concepts.md)を、あわせて[Design Principles](../developer/design/principles.md)もご覧ください。

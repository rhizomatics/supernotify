![Supernotify](../assets/images/dark_icon.png){ align=left }

# Supernotify

[![Rhizomatics Open Source](https://img.shields.io/badge/rhizomatics%20open%20source-lightseagreen)](https://github.com/rhizomatics) [![hacs][hacsbadge]][hacs]

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/supernotify)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/supernotify/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/supernotify/main)
![Coverage](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/coverage.svg)
![Tests](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/tests.svg)
[![Github Deploy](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates)

 <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=rhizomatics&repository=supernotify" target="_blank" rel="noopener noreferrer">
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="HACSに追加">
   </a>
<br/>
<br/>
<br/>

**Home Assistant向け統合通知システム**

### 重要な変更 v2.0.0

>> SuperNotify の `2.0.0` は、ネイティブの Home Assistant UI 設定（「ConfigFlow」）に移行します。既存のシンプルな設定がある場合、すべて自動的に移行され、YAML は不要になります。

>> 高度な設定（配信、シナリオ、カメラ、人物、アクションなど）がある場合は、それらを新しい `supernotify.yaml` ファイルに移動し、`configuration.yaml` に `include` ステートメントを追加するための*修正*が発行されます。または、`notify` ブロックから設定を好きな方法で手動で移動することもできます。

>> いずれの場合も、何も削除やコメントアウトはされないため、変更を簡単に元に戻せます。新しいバージョンが問題なく動作していると確信できたら、古い設定を削除してください。これにより、古いnotify実装由来のログ警告 `[homeassistant.components.notify] Failed to initialize notification service supernotify` も削除されます。

Home Assistantの組み込み`notify`プラットフォームの上に構築された**統合通知インターフェース**で、複数の通知チャネルや複雑なシナリオを大幅に簡素化します。マルチチャネル通知、条件付き通知、モバイルアクション、カメラスナップショット、チャイム、テンプレートベースのHTMLメールに対応しています。

Supernotifyの目標はひとつ——**コードなし、最小限の設定で、できる限りシンプルな通知から必要なだけ多くの通知を送ること**。

これにより、オートメーション、スクリプト、AppDaemonアプリがシンプルで保守しやすくなります。最小の通知——メッセージだけ——で必要なすべてを動かすことができます。メールアドレスを一箇所で変更するだけで、Supernotifyがどのモバイルアプリを使うか判断します。

UI設定だけで、モバイルアプリ名を設定することなく、家全員へのモバイルプッシュ通知を開始できます。

![通知アクションの例](../assets/images/notification.png){width=500}

## 配布

SupernotifyはHACS（[Home Assistant Community Shop](https://hacs.xyz)）経由で利用可能なカスタムコンポーネントです。[Apache 2.0ライセンス](https://www.apache.org/licenses/LICENSE-2.0)のもと、無料・オープンソースで提供されています。

## ドキュメント

[はじめに](https://supernotify.rhizomatics.org.uk/getting_started/)、[コアコンセプト](https://supernotify.rhizomatics.org.uk/concepts/)の解説、利用可能な[トランスポートアダプター](https://supernotify.rhizomatics.org.uk/transports/)をご覧ください。[通知の送信](https://supernotify.rhizomatics.org.uk/usage/notifying/)では、オートメーションや開発者ツールからSupernotifyを呼び出す方法を説明しています。

サンプル設定を含む多くの[レシピ](https://supernotify.rhizomatics.org.uk/recipes/)もあります。[タグ](https://supernotify.rhizomatics.org.uk/tags/)で絞り込むこともできます。


## 機能

* 1つのアクション -> 複数の通知
    * オートメーションから繰り返しの設定とコードを削除
    * アダプターが各インテグレーション向けに通知データを自動調整
    * 例：[Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints)と組み合わせてカメラスナップショットをメールで受信
* 自動セットアップ
    * モバイルプッシュ、メール（SMTP）、通知エンティティの配信設定が自動的に構成
    * モバイルアプリが自動検出（メーカー・機種情報含む）
    * チャイム用のAlexaデバイスが自動検出
* `notify`インテグレーションを超えた機能
    * チャイム、サイレン、SMS、TTS、Alexaアナウンス・サウンド、APIコール、MQTTデバイス
    * 標準的な`notify`・`notify.group`実装すべてに対応
    * iPhoneなどのモバイルプッシュ通知を大幅に簡素化
* 条件付き通知
    * Home Assistantの標準`conditions`を使用
    * メッセージや優先度を含む追加の条件変数
    * 在室検知と組み合わせ、誰がいるか・メッセージの優先度・内容に基づいて通知を最適化
* シンプルな設定のための**シナリオ**機能
    * 共通の設定と条件ロジックをパッケージ化
    * オンデマンド（`red_alert`、`nerdy`）または条件に基づいて自動適用
* 統合人物モデル
    * メール、SMS番号、またはモバイルデバイスを定義し、通知アクションで`person`エンティティを使用
    * 人物はモバイルアプリと合わせて自動設定
* 簡単な**HTMLメールテンプレート**
    * YAML設定・アクションコール・スタンドアロンファイルで定義できる標準Jinja2
    * デフォルト汎用テンプレート付属
* **モバイルアクション**
    * 複数の通知に対して一貫したモバイルアクションのセットを設定
    * 条件に基づいてミュートする*スヌーズ*アクションを含む
* 柔軟な**画像スナップショット**
    * カメラ、MQTT画像、画像URLに対応
    * スナップショット前後にカメラをPTZプリセットに移動
* 設定レベルの選択
    * トランスポート、配信、アクションの各レベルでデフォルトを設定可能
* **重複通知**の抑制
    * 再許可するまでの待機時間を調整
* 通知の**アーカイブ**と**デバッグサポート**
    * ファイルシステムやMQTTトピックへのオプションのアーカイブ
    * 完全なデバッグ情報を含む
    * 配信、トランスポート、受信者、シナリオをHome Assistant UIのエンティティとして公開


## 高度な用途のみYAMLが必要

Supernotifyは現在、基本設定には標準のHome Assistant UI設定、高度な機能には[YAML設定](https://supernotify.rhizomatics.org.uk/configuration/yaml/)をサポートしています。大規模なルールベースを扱いやすくするため、YAMLは今後も維持されます。

モバイルプッシュ設定の自動化を含め、シンプルな非YAML設定だけで多くのことができます。ドキュメント内の[レシピ](recipes/index.md)と、このモバイルプッシュの例をご覧ください：

```yaml title="YAMLゼロ、すべてUI設定"
  - action: supernotify.notify
    data:
        message: こんにちは！全員のモバイルアプリに送信するSupernotifyのテストです
```


##  Home Assistant向けRhizomatics Open Source

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - 物理ボタン、在室状況、カレンダー等を使ってHome Assistantの警報コントロールパネルを自動的に設定/解除
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - Home Assistant用OpenTelemetry（OTLP）およびSyslogイベントキャプチャ


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - ファイルシステム経由でANPR/ALPRナンバープレートカメラとMQTTを連携
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - DockerイメージのアップデートをMQTT経由で自動通知

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg

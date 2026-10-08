---
title: インストール
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Home Assistant 用 Supernotify を HACS からインストールし、YAML なしで UI から設定します
---

# インストール

## HACS からインストールする { #install-from-hacs }

まず、**HACS** がインストールされていることを確認します。

まだの場合は [HACS の手順](https://hacs.xyz/docs/use/)を参照してください。Supernotify は HACS の標準リポジトリのひとつなので、カスタムリポジトリの設定は不要です。

Home Assistant の HACS ページで、利用可能な統合の一覧から **Supernotify** を選んでダウンロードし、Home Assistant を再起動します。

![HACS での選択](../../assets/images/hacs_select.png){width=400}

## 統合を追加する { #add-the-integration }

**設定 → デバイスとサービス → 統合を追加** を開き、**Supernotify** を検索します。既定値のまま進めてください。

![統合の追加](../../assets/images/new_integration.png)

## 自動検出と既定値 { #discovery-and-defaults }

通知を動かすために必要な作業は、ここまでですべてです。

Supernotify は Home Assistant にすでにあるものを調べ、次のものを見つけます。

- **人** - Home Assistant に *Person* または *ユーザー* がある全員と、その人が Home Assistant アプリを使っているスマートフォンやタブレット
- **通知の手段** - モバイルプッシュ、既存の SMTP メール統合、すべての notify エンティティ、そして Alexa スピーカーやチャイムなどのデバイス（ある場合）

見つかった通知手段ごとに *delivery* が作られます。該当するデバイスがあれば、`chime_siren_all` や `alexa_devices_announce_all` のような便利な delivery も追加されます。

アーカイブ、重複検出、ハウスキーピングの設定は、あとから統合の **設定** オプションで変更できます。

では、[最初の通知を送りましょう](first_notification.md)。

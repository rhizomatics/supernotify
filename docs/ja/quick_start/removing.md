---
title: 削除
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Home Assistant 用 Supernotify を削除し、残ったものを片付けます
---

# Supernotify を削除する

HACS のメニューで `Supernotify` を選び、`...` メニューから `削除` を選びます。

### 設定の後片付け { #cleaning-up-config }

1. `config` ディレクトリに手動で作成した YAML ファイルはそのまま残ります。今後不要だと確信できる場合は、手動で削除してください。
2. アーカイブされた通知は残ります。別の設定をしていなければ、既定では `/config/archive/supernotify` ディレクトリにあります。必要に応じてこのディレクトリを削除してください。
3. カメラや画像の添付を使っていた場合、メディアファイルが残ることがあります。別の設定をしていなければ、既定では `/config/media/supernotify` ディレクトリにあります。必要に応じてこのディレクトリを削除してください。
4. テンプレートが残ることがあります。別の設定をしていなければ、既定では Home Assistant の設定ディレクトリ配下の `supernotify/templates` ディレクトリにあります。必要に応じてこのディレクトリを削除してください。

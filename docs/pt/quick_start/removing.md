---
title: Remoção
tags:
  - installation
  - marketplace
  - configuration
  - quickstart
description: Remova o Supernotify para Home Assistant e limpe o que ficar
---

# Remover o Supernotify

Vá a **Configurações → Marketplace**, abra o **Supernotify** e escolha **Desinstalar** no menu de três pontos. Ele não pode ser desinstalado enquanto ainda estiver configurado, então primeiro remova-o em **Configurações → Dispositivos e serviços**, ou escolha **Excluir e desinstalar**, que também exclui seus dispositivos e entidades.

Antes do Home Assistant 2026.11: No menu do HACS, selecione `Supernotify` e escolha `Remover` no menu `...`.

### Limpar a configuração { #cleaning-up-config }

1. Os arquivos YAML criados manualmente no diretório `config` não são alterados; remova-os se tiver certeza de que não serão mais necessários.
2. As notificações arquivadas permanecem, por padrão no diretório `/config/archive/supernotify`, salvo configuração em contrário. Remova este diretório se necessário.
3. Se você usar câmeras ou imagens anexadas, podem ficar arquivos de mídia, por padrão no diretório `/config/media/supernotify`, salvo configuração em contrário. Remova este diretório se necessário.
4. Podem ficar modelos, por padrão em um diretório `supernotify/templates` dentro do diretório de configuração do Home Assistant, salvo configuração em contrário. Remova este diretório se necessário.

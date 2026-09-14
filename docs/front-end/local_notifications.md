# Notificações locais por polling (Flutter)

> **Não é push de servidor.** Não há FCM no app (ver
> [firebase_setup.md](firebase_setup.md), documento histórico). O
> `notification-service` só **grava** as notificações no Postgres; ninguém as
> envia ao aparelho. O que o app faz é consultar `GET /notifications` a cada
> 10 segundos e mostrar na bandeja do sistema, com `flutter_local_notifications`,
> o que chegou desde a consulta anterior. Por isso **só funciona enquanto o
> processo do app está vivo** — em primeiro plano ou em segundo plano ainda não
> encerrado pelo sistema. App fechado não recebe nada.

## Como funciona

```
login / troca de sessão ──► irParaTelaDoPapel ──► NotificationsPoller.iniciar()
                                                    │  pede POST_NOTIFICATIONS (1x por processo)
                                                    │  consulta na hora
                                                    ▼
                         a cada 10 s: relê o token ──► GET /notifications
                                                    │
               ┌────────────────────────────────────┼───────────────────────────────┐
               ▼                                    ▼                               ▼
   notificação nova e não lida          naoLidas ──► NotificationBell     versao ──► NotificationsScreen
   ──► bandeja (canal "Pedidos")        (contador no sino da TopBar)      aberta recarrega sozinha
```

- **Primeira consulta de um usuário no processo só semeia.** O histórico
  existente conta como visto: logar não despeja notificações antigas na
  bandeja.
- **O que foi visto fica guardado por usuário** enquanto o processo vive. A
  apresentação alterna os quatro perfis no mesmo aparelho; ao voltar para a
  Ana, o que o separador fez nesse meio-tempo é novo para ela e aparece na
  bandeja logo depois da troca. No máximo 5 por consulta (as mais recentes); o
  resto fica na lista e no contador.
- **Fim de sessão sem gancho.** Cada ciclo relê o access token; sem token
  (logout, sessão expirada) o polling para sozinho. Token de carregamento
  (`role: carregamento`) não é consultado — o backend responde 403 a ele.
- **Falha é silenciosa.** Rede fora, 5xx ou canal de notificação indisponível
  não derrubam nada: o último estado bom fica, o próximo ciclo tenta de novo, e
  só a primeira falha de uma sequência vai para o log (`debugPrint`).
- **Toque na notificação** abre a lista de notificações; uma notificação de
  ocorrência (falta de estoque, atraso) abre direto a tela de resolução, com a
  lista por baixo — o mesmo destino do toque dentro da lista. Sem sessão ativa,
  o toque só traz o app para a frente. Com o processo morto, o toque abre o app
  no login.

## Onde está

| Arquivo | Papel |
|---|---|
| `lib/features/notifications/presentation/notifications_poller.dart` | `NotificationsPoller` (`ChangeNotifier`): ciclo, semeadura, memória por usuário, contador |
| `lib/features/notifications/domain/local_notifier.dart` | `LocalNotifier` (abstração) e `LocalNotifierInerte` |
| `lib/features/notifications/data/plugin_local_notifier.dart` | adaptador do plugin (Android): canal, permissão, `show`, toque |
| `lib/features/notifications/domain/notification_payload.dart` | payload da notificação: só o `occurrence_id` |
| `lib/features/notifications/presentation/system_notification_tap.dart` | para onde o toque leva |
| `lib/features/notifications/presentation/widgets/notification_bell.dart` | sino com contador de não lidas |
| `lib/core/session/session_switcher.dart` | `irParaTelaDoPapel` chama `iniciar()` |
| `lib/main.dart` | registra o poller no `MultiProvider` |

## Plataformas

- **Android**: canal `pedidos` ("Pedidos"), importância alta, ícone
  `@mipmap/ic_launcher` (o Android o desenha como silhueta monocromática).
  `POST_NOTIFICATIONS` já está no `AndroidManifest.xml`, e o desugaring que o
  plugin exige já estava no `build.gradle.kts` — nenhuma mudança de Gradle.
- **iOS, Linux desktop, web**: notificador inerte. Sino e lista funcionam; a
  bandeja do sistema não. Ligar no iOS pede configuração no `AppDelegate`.

## Limites conhecidos

- **Segundo plano depende do fabricante.** O timer do Dart segue rodando com o
  app em segundo plano enquanto o sistema não mata o processo nem corta a rede.
  Economia de bateria agressiva (Samsung: "Suspender apps em segundo plano";
  Doze em geral) pode encerrar o processo ou atrasar a rede, e então nada
  chega até o app voltar para a frente. Não verificado em aparelho.
- **O contador só cresce.** O app ainda não marca notificação como lida
  (`PATCH /notifications/{id}/read` existe sem chamador), então `naoLidas` é o
  total de não lidas que o backend devolve.
- **Só o sino da `TopBar` tem contador** (home, quiz, revisão). Os sinos do
  admin, da logística e das telas de pedido ainda são `IconButton` simples;
  trocar por `const NotificationBell()` é uma linha em cada.
- **Latência de até ~10 s** entre a notificação ser gravada e aparecer.

## Como testar

Automatizado:

```bash
cd front-end-flutter
flutter test test/features/notifications/ test/core/session/session_switcher_test.dart
```

No aparelho (Android 13+):

1. Entrar como aluno e aceitar o pedido de permissão de notificação.
2. Com a sessão do aluno ativa, provocar uma transição do pedido por outro
   caminho (o perfil de staff em outro aparelho, ou o avanço automático de
   [order-flow.md](../back-end/order-flow.md)). Em até ~10 s a
   notificação aparece na bandeja — com o app aberto ou depois de apertar Home
   — e o contador do sino sobe.
3. Na demonstração de um aparelho só: aluno faz o pedido, troca para o
   separador, separa, volta para o aluno — as transições aparecem na bandeja
   logo depois da troca.
4. Tocar na notificação: abre a lista; numa de falta de estoque, abre a tela
   de resolução.
5. Sair da conta e provocar outra transição: nada chega enquanto ninguém
   está logado. Ao entrar de novo como o mesmo aluno, no mesmo processo, ela
   aparece — é a memória por usuário, não um vazamento.

Para ver o pedido de permissão de novo: Configurações > Apps > Edu IA >
Notificações (ou reinstalar o app).

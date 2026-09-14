import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../notifications_poller.dart';

/// Sino que abre as notificações, com o contador de não lidas vindo do
/// [NotificationsPoller] — o mesmo ciclo que manda para a bandeja do sistema,
/// então o número muda sem a tela recarregar.
///
/// O poller é lido como opcional: uma tela montada sem ele na árvore (os
/// testes de outras features, por exemplo) desenha o sino sem contador em vez
/// de quebrar com `ProviderNotFoundException`.
class NotificationBell extends StatelessWidget {
  const NotificationBell({super.key});

  @override
  Widget build(BuildContext context) {
    final naoLidas = context.watch<NotificationsPoller?>()?.naoLidas ?? 0;

    return IconButton(
      onPressed: () => Navigator.pushNamed(context, '/notifications'),
      tooltip: 'Notificações',
      icon: Badge.count(
        count: naoLidas,
        maxCount: 99,
        isLabelVisible: naoLidas > 0,
        child: const Icon(Icons.notifications_none, size: 28),
      ),
    );
  }
}

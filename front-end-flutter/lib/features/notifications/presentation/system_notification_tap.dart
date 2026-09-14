import 'package:flutter/material.dart';

import '../../marketplace/presentation/incident_resolution_screen.dart';
import '../domain/notification_payload.dart';

/// Leva o usuário para onde o toque numa notificação da bandeja aponta.
///
/// Mesmo destino do toque na `NotificationsScreen`: uma notificação de
/// ocorrência (falta de estoque, atraso) abre a tela de resolução — com a
/// lista por baixo, para o "voltar" cair nela —, e as demais abrem a lista.
///
/// Sem sessão ativa (o usuário saiu depois de a notificação ser mostrada) o
/// toque só traz o app para a frente: a lista pediria um token que não existe
/// e mostraria "Sessão expirada" no lugar da tela de login.
void abrirNotificacaoDoSistema({
  required NavigatorState? navigator,
  required bool sessaoAtiva,
  required String? payload,
}) {
  if (navigator == null || !sessaoAtiva) return;

  navigator.pushNamed('/notifications');

  final ocorrenciaId = ocorrenciaDoPayload(payload);
  if (ocorrenciaId == null) return;
  navigator.push(
    MaterialPageRoute(
      builder: (_) => OcorrenciaResolucaoScreen(ocorrenciaId: ocorrenciaId),
    ),
  );
}

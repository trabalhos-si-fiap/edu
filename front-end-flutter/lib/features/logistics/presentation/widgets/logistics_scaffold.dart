import 'package:flutter/material.dart';

import '../../../../core/network/token_store.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../auth/data/auth_api.dart';

/// Scaffold base para as telas de Separador e Entregador. Diferente do
/// [NavBar] do app do aluno (5 abas), o staff tem um fluxo linear e mais
/// simples: fila -> detalhe -> ação -> volta pra fila. Por isso usa uma
/// AppBar simples com botão de logout, em vez de bottom navigation.
class LogisticsScaffold extends StatelessWidget {
  const LogisticsScaffold({
    super.key,
    required this.titulo,
    required this.body,
    this.showLogout = false,
    this.floatingActionButton,
  });

  final String titulo;
  final Widget body;
  final bool showLogout;
  final Widget? floatingActionButton;

  Future<void> _logout(BuildContext context) async {
    await AuthApi(tokenStore: TokenStore()).logout();
    if (!context.mounted) return;
    Navigator.pushNamedAndRemoveUntil(context, '/login', (_) => false);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          automaticallyImplyLeading: Navigator.canPop(context),
          title: Text(
            titulo,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          actions: [
            if (showLogout)
              IconButton(
                onPressed: () => _logout(context),
                icon: const Icon(Icons.logout, color: AppColors.textSecondary),
                tooltip: 'Sair',
              ),
            const SizedBox(width: 8),
          ],
        ),
        body: SafeArea(child: body),
        floatingActionButton: floatingActionButton,
      ),
    );
  }
}

/// Estado vazio reutilizado quando uma fila não tem pedidos.
class FilaVaziaState extends StatelessWidget {
  const FilaVaziaState({
    super.key,
    required this.mensagem,
    this.icon = Icons.inbox_outlined,
  });

  final String mensagem;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 64, color: AppColors.textSecondary),
            const SizedBox(height: 16),
            Text(
              mensagem,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 15, color: AppColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

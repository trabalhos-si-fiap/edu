import 'package:flutter/material.dart';

import '../../../../core/network/token_store.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../auth/data/auth_api.dart';
import '../admin_analytics_screen.dart';
import '../admin_dashboard_screen.dart';
import '../admin_shipments_screen.dart';

enum AdminTab { dashboard, painel, carregamentos }

/// Scaffold base das telas de admin: AppBar com sino de notificações +
/// logout, e bottom nav de 3 abas (Dashboard / Painel Analítico /
/// Carregamentos), no estilo do mockup de referência. Trocar de aba troca
/// de tela via [PageRoute] sem animação (são pares, não uma pilha), igual
/// o padrão do restante do app para bottom nav.
class AdminScaffold extends StatelessWidget {
  const AdminScaffold({
    super.key,
    required this.tab,
    required this.titulo,
    required this.body,
  });

  final AdminTab tab;
  final String titulo;
  final Widget body;

  Future<void> _logout(BuildContext context) async {
    await AuthApi(tokenStore: TokenStore()).logout();
    if (!context.mounted) return;
    Navigator.pushNamedAndRemoveUntil(context, '/login', (_) => false);
  }

  void _onTapTab(BuildContext context, AdminTab destino) {
    if (destino == tab) return;
    Navigator.pushReplacement(
      context,
      PageRouteBuilder(
        transitionDuration: Duration.zero,
        reverseTransitionDuration: Duration.zero,
        pageBuilder: (_, __, ___) => switch (destino) {
          AdminTab.dashboard => const AdminDashboardScreen(),
          AdminTab.painel => const AdminAnalyticsScreen(),
          AdminTab.carregamentos => const AdminShipmentsScreen(),
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.inputFill,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        automaticallyImplyLeading: false,
        title: Text(
          titulo,
          style: const TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: AppColors.textPrimary,
          ),
        ),
        actions: [
          // Mesmo ponto de entrada que a task 11 deu às duas telas de staff
          // de logística (`LogisticsScaffold.showNotifications`): o admin é
          // a terceira superfície de staff, e os pushes da spec C também
          // chegam para quem tem papel admin.
          IconButton(
            onPressed: () => Navigator.pushNamed(context, '/notifications'),
            icon: const Icon(
              Icons.notifications_outlined,
              color: AppColors.textPrimary,
            ),
            tooltip: 'Notificações',
          ),
          IconButton(
            onPressed: () => _logout(context),
            icon: const Icon(Icons.logout, color: AppColors.textPrimary),
            tooltip: 'Sair',
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(child: body),
      bottomNavigationBar: SafeArea(
        child: SizedBox(
          height: 64,
          child: Row(
            children: [
              _NavItem(
                icon: Icons.dashboard_outlined,
                label: 'Dashboard',
                selected: tab == AdminTab.dashboard,
                onTap: () => _onTapTab(context, AdminTab.dashboard),
              ),
              _NavItem(
                icon: Icons.query_stats_outlined,
                label: 'Painel',
                selected: tab == AdminTab.painel,
                onTap: () => _onTapTab(context, AdminTab.painel),
              ),
              _NavItem(
                icon: Icons.local_shipping_outlined,
                label: 'Carregamentos',
                selected: tab == AdminTab.carregamentos,
                onTap: () => _onTapTab(context, AdminTab.carregamentos),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppColors.purple : AppColors.textSecondary;
    return Expanded(
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 12,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';

/// Layout de abas exibido pela [NavBar].
///
/// [main] é o app de estudos; [store] é o contexto de loja/pedidos.
enum NavBarMode { main, store }

/// Barra de navegação principal do app.
///
/// Centraliza itens, rotas e a navegação em si — cada tela informa qual layout
/// usar via [mode] e qual item está ativo via [currentIndex]. Telas que não são
/// uma aba (ex.: perfil) podem passar `currentIndex: -1`.
class NavBar extends StatelessWidget {
  final int currentIndex;
  final NavBarMode mode;

  const NavBar({
    super.key,
    required this.currentIndex,
    this.mode = NavBarMode.main,
  });

  /// Destinos por layout. `route == null` marca tela ainda não implementada.
  static const Map<NavBarMode, List<({IconData icon, String label, String? route})>>
  _layouts = {
    NavBarMode.main: [
      (icon: Icons.home_rounded, label: 'Home', route: '/home'),
      (icon: Icons.quiz_outlined, label: 'Quiz', route: '/quiz'),
      (icon: Icons.assignment_turned_in_outlined, label: 'Revisão', route: null),
      (icon: Icons.menu_book_outlined, label: 'Estudo', route: null),
      (
        icon: Icons.store_mall_directory_outlined,
        label: 'Loja',
        route: '/marketplace',
      ),
    ],
    NavBarMode.store: [
      (icon: Icons.home_rounded, label: 'Home', route: '/home'),
      (
        icon: Icons.receipt_long_outlined,
        label: 'Meus Pedidos',
        route: '/orders',
      ),
      (icon: Icons.support_agent_outlined, label: 'Suporte', route: '/support'),
      (
        icon: Icons.store_mall_directory_outlined,
        label: 'Loja',
        route: '/marketplace',
      ),
    ],
  };

  List<({IconData icon, String label, String? route})> get _destinations =>
      _layouts[mode]!;

  void _onTap(BuildContext context, int index) {
    if (index == currentIndex) return;
    final route = _destinations[index].route;
    if (route == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Em breve')),
      );
      return;
    }
    Navigator.pushReplacementNamed(context, route);
  }

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      child: BottomNavigationBar(
        // BottomNavigationBar exige um índice válido; telas fora das abas
        // (currentIndex < 0) não destacam nenhum item de forma efetiva.
        currentIndex: currentIndex < 0 ? 0 : currentIndex,
        onTap: (index) => _onTap(context, index),
        backgroundColor: AppColors.white,
        selectedItemColor: AppColors.purple,
        unselectedItemColor: AppColors.textSecondary,
        type: BottomNavigationBarType.fixed,
        items: [
          for (final d in _destinations)
            BottomNavigationBarItem(icon: Icon(d.icon), label: d.label),
        ],
      ),
    );
  }
}

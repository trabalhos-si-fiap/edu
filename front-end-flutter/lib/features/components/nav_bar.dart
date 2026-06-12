import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';

/// Barra de navegação principal do app.
///
/// Centraliza itens, rotas e a navegação em si — cada tela só informa qual
/// item está ativo via [currentIndex]. Telas que não são uma aba (ex.: perfil)
/// podem passar `currentIndex: -1`.
class NavBar extends StatelessWidget {
  final int currentIndex;

  const NavBar({super.key, required this.currentIndex});

  /// Destinos das abas. `route == null` marca tela ainda não implementada.
  static const List<({IconData icon, String label, String? route})>
  _destinations = [
    (icon: Icons.home_rounded, label: 'Home', route: '/home'),
    (icon: Icons.quiz_outlined, label: 'Quiz', route: '/quiz'),
    (icon: Icons.assignment_turned_in_outlined, label: 'Revisão', route: null),
    (icon: Icons.menu_book_outlined, label: 'Estudo', route: null),
    (
      icon: Icons.store_mall_directory_outlined,
      label: 'Loja',
      route: '/marketplace',
    ),
  ];

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

import 'package:flutter/material.dart';

class TopBar extends StatelessWidget implements PreferredSizeWidget {
  const TopBar({super.key});

   @override
  Widget build(BuildContext context) {
    return AppBar(
      backgroundColor: Colors.transparent,
      elevation: 0,
      automaticallyImplyLeading: false,
      title: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            IconButton(
              onPressed: () {},
              icon: const Icon(Icons.notifications_none, size: 28),
            ),
            IconButton(
              onPressed: () => Navigator.pushNamed(context, '/profile'),
              icon: const Icon(Icons.person_outline, size: 28),
            ),
          ],
        ),
      ),
    );
  }


  // obrigatório para implementar PreferredSizeWidget
  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}

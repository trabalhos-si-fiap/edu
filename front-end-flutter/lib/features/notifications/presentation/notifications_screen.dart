import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/features/components/nav_bar.dart';
import 'package:flutter/material.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {

    final List<Map<String, String>> notifications = [
      {
        'title': 'Notificação 1',
        'description': 'Descrição da notificação 1',
        'type': 'estudo',
      },
      {
        'title': 'Notificação 2',
        'description': 'Descrição da notificação 2',
        'type': 'entrega',
      },
    ];

    @override
    Widget build(BuildContext context) {
        return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          title: Row(
            mainAxisAlignment: MainAxisAlignment.center,
          ),
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 12),
                const Text(
                  "Notificações",
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w700,
                    color: AppColors.purple,
                  ),
                ),
                const SizedBox(height: 16),
                Column(
                  children: notifications
                      .map((notification) => _NotificationCard(
                            title: notification['title']!,
                            description: notification['description']!,
                            type: notification['type']!,
                          ))
                      .toList(),
                ),
              ],
            ),
          ),
        ),
        bottomNavigationBar: const NavBar(currentIndex: -1),
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  final String title;
  final String description;
  final String type;

  const _NotificationCard({required this.title, required this.description, required this.type});

  IconData get _getIcon {
    switch (type.toLowerCase()) {
      case 'estudo':
        return Icons.book;
      case 'entrega':
        return Icons.assignment_turned_in;
      default:
        return Icons.notifications;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(_getIcon, color: AppColors.purple, size: 24),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: const TextStyle(
                          fontWeight: FontWeight.bold, fontSize: 16)),
                  const SizedBox(height: 4),
                  Text(description, style: const TextStyle(fontSize: 14)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}


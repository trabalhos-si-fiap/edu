import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/features/components/nav_bar.dart';
import 'package:flutter/material.dart';

import '../data/notifications_api.dart';
import '../domain/notification_model.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key, NotificationsApi? api})
    : _api = api;

  final NotificationsApi? _api;

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  late final NotificationsApi _api = widget._api ?? NotificationsApi();
  late Future<List<NotificationModel>> _future;

  @override
  void initState() {
    super.initState();
    _future = _api.list();
  }

  Future<void> _refresh() async {
    setState(() => _future = _api.list());
    await _future.catchError((_) => <NotificationModel>[]);
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
          title: Row(mainAxisAlignment: MainAxisAlignment.center),
        ),
        body: SafeArea(
          child: RefreshIndicator(
            onRefresh: _refresh,
            child: FutureBuilder<List<NotificationModel>>(
              future: _future,
              builder: (context, snapshot) {
                return SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
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
                      _buildBody(snapshot),
                    ],
                  ),
                );
              },
            ),
          ),
        ),
        bottomNavigationBar: const NavBar(currentIndex: -1),
      ),
    );
  }

  Widget _buildBody(AsyncSnapshot<List<NotificationModel>> snapshot) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return const Padding(
        padding: EdgeInsets.only(top: 80),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (snapshot.hasError) {
      return _Placeholder(
        icon: Icons.cloud_off,
        message: snapshot.error.toString(),
      );
    }
    final notifications = snapshot.data ?? const [];
    if (notifications.isEmpty) {
      return const _Placeholder(
        icon: Icons.notifications_none,
        message: 'Você ainda não tem notificações.',
      );
    }
    return Column(
      children: notifications
          .map((n) => _NotificationCard(notification: n))
          .toList(),
    );
  }
}

class _Placeholder extends StatelessWidget {
  const _Placeholder({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 80),
      child: Center(
        child: Column(
          children: [
            Icon(icon, size: 48, color: Colors.white70),
            const SizedBox(height: 12),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white),
            ),
          ],
        ),
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  const _NotificationCard({required this.notification});

  final NotificationModel notification;

  IconData get _icon {
    switch (notification.type) {
      case 'order_status':
        return Icons.local_shipping;
      case 'estudo':
        return Icons.book;
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
            Icon(_icon, color: AppColors.purple, size: 24),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    notification.title,
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(notification.body, style: const TextStyle(fontSize: 14)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

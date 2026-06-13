import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../../components/nav_bar.dart';
import '../domain/order_model.dart';
import 'order_provider.dart';
import 'widgets/arrival_estimate_card.dart';
import 'widgets/kit_content_card.dart';
import 'widgets/location_card.dart';
import 'widgets/order_error_view.dart';
import 'widgets/support_card.dart';
import 'widgets/tracking_timeline.dart';

/// Tela de Acompanhamento de Pedido (Order Tracking).
///
/// Recebe o id do pedido via `Navigator.pushNamed(arguments: '<id>')` e
/// delega todo o estado ao [OrderProvider]. A UI não contém regra de negócio:
/// apenas observa o provider e desenha loading / success / error.
class OrderTrackingScreen extends StatelessWidget {
  const OrderTrackingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final orderId =
        ModalRoute.of(context)?.settings.arguments as String? ?? 'ED-99420';

    return ChangeNotifierProvider(
      create: (_) => OrderProvider()..load(orderId),
      child: Container(
        decoration: const BoxDecoration(gradient: AppColors.headerGradient),
        child: Scaffold(
          backgroundColor: Colors.transparent,
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            leading: IconButton(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
            ),
            actions: [
              IconButton(
                onPressed: () => Navigator.pushNamed(context, '/profile'),
                icon: const Icon(Icons.person_outline, size: 28),
              ),
              IconButton(
                onPressed: () => Navigator.pushNamed(context, '/notifications'),
                icon: const Icon(Icons.notifications_none, size: 28),
              ),
              const SizedBox(width: 8),
            ],
          ),
          body: SafeArea(
            child: Consumer<OrderProvider>(
              builder: (context, provider, _) {
                switch (provider.state) {
                  case OrderViewState.loading:
                    return const _LoadingView();
                  case OrderViewState.error:
                    return OrderErrorView(
                      message: provider.errorMessage ?? 'Erro desconhecido.',
                      onRetry: provider.retry,
                    );
                  case OrderViewState.success:
                    return _OrderContent(order: provider.order!);
                }
              },
            ),
          ),
          bottomNavigationBar: const NavBar(currentIndex: 4),
        ),
      ),
    );
  }
}

/// Estado de carregamento.
class _LoadingView extends StatelessWidget {
  const _LoadingView();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(color: AppColors.purple),
          SizedBox(height: 16),
          Text(
            'Buscando seu rastreio...',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}

/// Estado de sucesso: interface principal do rastreio.
class _OrderContent extends StatelessWidget {
  final OrderModel order;

  const _OrderContent({required this.order});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'PEDIDO #${order.id}',
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: AppColors.textSecondary,
              letterSpacing: 1.5,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            order.headline,
            style: const TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
              letterSpacing: -0.5,
              height: 1.1,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            order.description,
            style: const TextStyle(
              fontSize: 15,
              color: AppColors.textSecondary,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 20),
          ArrivalEstimateCard(estimatedArrival: order.estimatedArrival),
          const SizedBox(height: 24),
          TrackingTimeline(steps: order.steps),
          const SizedBox(height: 24),
          LocationCard(
            location: order.location,
            onOpenMap: () => Navigator.pushNamed(
              context,
              '/order-map',
              arguments: order.id,
            ),
          ),
          const SizedBox(height: 24),
          KitContentCard(kit: order.kit, carrier: order.carrier),
          const SizedBox(height: 24),
          SupportCard(onContactSupport: () {}),
        ],
      ),
    );
  }
}

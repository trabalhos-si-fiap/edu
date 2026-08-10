import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/features/components/nav_bar.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../domain/order_summary.dart';
import 'orders_provider.dart';

/// Entrada de rota da tela "Seus pedidos". Cria o [OrdersProvider] e dispara o
/// carregamento inicial; a UI vive em [OrdersView] para facilitar testes.
class OrdersScreen extends StatelessWidget {
  const OrdersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => OrdersProvider()..load(),
      child: const OrdersView(),
    );
  }
}

/// Corpo da tela "Seus pedidos". Espera um [OrdersProvider] já disponível.
class OrdersView extends StatelessWidget {
  const OrdersView({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        bottomNavigationBar: const NavBar(
          mode: NavBarMode.store,
          currentIndex: 1,
        ),
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
              onPressed: () =>
                  Navigator.pushNamed(context, '/notifications'),
              icon: const Icon(Icons.notifications_none, size: 28),
            ),
            const SizedBox(width: 8),
          ],
        ),
        body: SafeArea(
          child: Consumer<OrdersProvider>(
            builder: (context, provider, _) {
              switch (provider.state) {
                case OrdersViewState.loading:
                  return const Center(
                    child: CircularProgressIndicator(color: AppColors.purple),
                  );
                case OrdersViewState.error:
                  return _ErrorView(
                    message: provider.errorMessage ?? 'Erro desconhecido.',
                    onRetry: provider.load,
                  );
                case OrdersViewState.success:
                  return _OrdersList(provider: provider);
              }
            },
          ),
        ),
      ),
    );
  }
}

class _OrdersList extends StatelessWidget {
  const _OrdersList({required this.provider});

  final OrdersProvider provider;

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      color: AppColors.purple,
      onRefresh: provider.load,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Seus pedidos',
              style: TextStyle(
                fontSize: 32,
                fontWeight: FontWeight.w800,
                color: AppColors.textPrimary,
                letterSpacing: -0.5,
              ),
            ),
            const SizedBox(height: 20),
            if (provider.isEmpty)
              const _EmptyState()
            else ...[
              for (final order in provider.activeOrders) ...[
                _ActiveOrderCard(order: order),
                const SizedBox(height: 20),
              ],
              for (final order in provider.finishedOrders) ...[
                _FinishedOrderCard(order: order),
                const SizedBox(height: 20),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

/// Identificador curto e legível derivado do UUID do pedido.
String _shortId(String id) {
  final trimmed = id.replaceAll('-', '');
  final slice = trimmed.length >= 8 ? trimmed.substring(0, 8) : trimmed;
  return slice.toUpperCase();
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            'Não foi possível carregar seus pedidos.',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 16),
          TextButton(
            onPressed: onRetry,
            child: const Text(
              'Tentar novamente',
              style: TextStyle(color: AppColors.purple),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 48),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: const BoxDecoration(
                color: Color(0xFFEDE0FF),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.shopping_bag_outlined,
                color: AppColors.purple,
                size: 30,
              ),
            ),
            const SizedBox(height: 16),
            const Text(
              'Você ainda não tem pedidos',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Quando você comprar na loja, seus pedidos aparecerão aqui.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () =>
                  Navigator.pushReplacementNamed(context, '/marketplace'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.purple,
                foregroundColor: AppColors.white,
                elevation: 0,
                padding:
                    const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text(
                'Ir para a loja',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActiveOrderCard extends StatelessWidget {
  const _ActiveOrderCard({required this.order});

  final OrderSummary order;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: const Color(0xFFEDE0FF),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Text(
              'Pedido ativo',
              style: TextStyle(
                color: AppColors.purple,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Pedido #${_shortId(order.id)}',
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textPrimary,
                        height: 1.15,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Compra realizada em ${formatOrderDate(order.createdAt)}',
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  const Text(
                    'Valor total',
                    style: TextStyle(
                      fontSize: 13,
                      color: AppColors.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    formatOrderTotal(order.total),
                    style: const TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.w800,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 24),
          _OrderStepper(currentIdx: order.stepIndex),
          const SizedBox(height: 20),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.inputFill,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(
                  Icons.info_outline,
                  size: 20,
                  color: AppColors.purple,
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Status atual',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppColors.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        order.statusLabel,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
                          color: AppColors.textPrimary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () => Navigator.pushNamed(
                context,
                '/order-tracking',
                arguments: order.id,
              ),
              icon: const Icon(Icons.local_shipping_outlined, size: 20),
              label: const Text(
                'Rastrear pedido',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.purple,
                foregroundColor: AppColors.white,
                elevation: 0,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () => Navigator.pushNamed(context, '/order-details'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.inputFill,
                foregroundColor: AppColors.textPrimary,
                elevation: 0,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text(
                'Detalhes do pedido',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _OrderStepper extends StatelessWidget {
  const _OrderStepper({required this.currentIdx});

  /// Índice da etapa atual: 0 = Separação, 1 = Trânsito, 2 = Entregue.
  final int currentIdx;

  @override
  Widget build(BuildContext context) {
    final steps = [
      ('Separação', Icons.check),
      ('Trânsito', Icons.local_shipping),
      ('Entregue', Icons.home_outlined),
    ];

    return Row(
      children: [
        for (var i = 0; i < steps.length; i++) ...[
          Expanded(
            child: Column(
              children: [
                Row(
                  children: [
                    if (i > 0)
                      Expanded(
                        child: Container(
                          height: 3,
                          color: i <= currentIdx
                              ? AppColors.purple
                              : const Color(0xFFEDE0FF),
                        ),
                      )
                    else
                      const Spacer(),
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: i <= currentIdx
                            ? AppColors.purple
                            : AppColors.inputFill,
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        steps[i].$2,
                        size: 18,
                        color: i <= currentIdx
                            ? AppColors.white
                            : AppColors.textSecondary,
                      ),
                    ),
                    if (i < steps.length - 1)
                      Expanded(
                        child: Container(
                          height: 3,
                          color: i < currentIdx
                              ? AppColors.purple
                              : const Color(0xFFEDE0FF),
                        ),
                      )
                    else
                      const Spacer(),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  steps[i].$1.toUpperCase(),
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1,
                    color: i <= currentIdx
                        ? AppColors.purple
                        : AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

/// Card de um pedido que já saiu do fluxo — entregue OU cancelado (a lista
/// que alimenta este widget é `OrdersProvider.finishedOrders`, que junta os
/// dois; ver `isFinished` em `order_summary.dart`). O selo e as ações mudam
/// por status: revisão de correção 1 achou que um pedido cancelado
/// renderizava com o selo verde "ENTREGUE" fixo, porque o texto e a cor eram
/// literais, não derivados de `order.status`.
class _FinishedOrderCard extends StatelessWidget {
  const _FinishedOrderCard({required this.order});

  final OrderSummary order;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.inputFill,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Pedido #${_shortId(order.id)}',
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      formatOrderDate(order.createdAt),
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  // Cancelado não é sucesso: badge vermelho (AppColors.danger),
                  // não o verde de entregue. Os únicos dois status que chegam
                  // aqui são delivered/cancelled (OrdersProvider.finishedOrders
                  // filtra por isFinished), então o ternário cobre os dois casos.
                  color: order.status == OrderSummaryStatus.cancelled
                      ? AppColors.danger
                      : AppColors.success,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  order.statusLabel.toUpperCase(),
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: AppColors.white,
                    letterSpacing: 1,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              ..._buildThumbs(order.items),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${order.totalQuantity} itens no pedido',
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Total: ${formatOrderTotal(order.total)}',
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: ElevatedButton(
                  onPressed: () {},
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFEDE0FF),
                    foregroundColor: AppColors.purple,
                    elevation: 0,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text(
                    'Comprar novamente',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
              // "Avaliar itens" pressupõe que o pedido chegou. Um pedido
              // cancelado nunca chegou — a ação some, "Comprar novamente"
              // continua (recomprar um pedido cancelado é legítimo).
              if (order.status != OrderSummaryStatus.cancelled) ...[
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    onPressed: () {},
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.white,
                      foregroundColor: AppColors.textPrimary,
                      elevation: 0,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text(
                      'Avaliar itens',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  /// Até 3 miniaturas dos itens; um chip "+N" cobre o excedente.
  List<Widget> _buildThumbs(List<OrderItemSummary> items) {
    const maxThumbs = 3;
    final visible = items.take(maxThumbs).toList();
    final overflow = items.length - visible.length;

    final thumbs = <Widget>[];
    for (var i = 0; i < visible.length; i++) {
      if (i > 0) thumbs.add(const SizedBox(width: 6));
      thumbs.add(_ItemThumb(item: visible[i]));
    }
    if (overflow > 0) {
      thumbs.add(const SizedBox(width: 6));
      thumbs.add(
        Container(
          width: 44,
          height: 44,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: const Color(0xFFE5E7EB),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            '+$overflow',
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
        ),
      );
    }
    return thumbs;
  }
}

class _ItemThumb extends StatelessWidget {
  const _ItemThumb({required this.item});

  final OrderItemSummary item;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: const Color(0xFFE5E7EB),
        borderRadius: BorderRadius.circular(8),
      ),
      child: item.imageUrl.isEmpty
          ? const Icon(
              Icons.menu_book,
              size: 20,
              color: AppColors.textSecondary,
            )
          : Image.network(
              item.imageUrl,
              fit: BoxFit.cover,
              errorBuilder: (_, _, _) => const Icon(
                Icons.menu_book,
                size: 20,
                color: AppColors.textSecondary,
              ),
            ),
    );
  }
}

import 'dart:math';

import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/core/utils/currency.dart';
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/cart/domain/cart_item.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/product_visuals.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/rating_stars.dart';
import 'package:edu_ia/features/payment/data/payment_store.dart';
import 'package:edu_ia/features/payment/domain/payment_method.dart';
import 'package:edu_ia/features/profile/data/mock_addresses.dart';
import 'package:edu_ia/features/profile/domain/address.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

/// Checkout: revisão do carrinho + endereço + pagamento + finalização.
/// Portado de edu-kt `CheckoutScreen` (carrinho e pagamento juntos).
class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  String? _selectedPaymentId;
  String? _selectedAddressId;

  final List<Address> _addresses = mockAddresses;

  @override
  void initState() {
    super.initState();
    if (_addresses.isNotEmpty) {
      final favorite = _addresses.where((a) => a.isFavorite);
      _selectedAddressId =
          (favorite.isNotEmpty ? favorite.first : _addresses.first).id;
    }
  }

  Address? get _selectedAddress {
    for (final a in _addresses) {
      if (a.id == _selectedAddressId) return a;
    }
    return null;
  }

  /// Id de pagamento efetivo: o selecionado pelo usuário se ainda existir,
  /// senão o padrão, senão o primeiro.
  String? _effectivePaymentId(List<PaymentMethod> methods) {
    if (methods.any((m) => m.id == _selectedPaymentId)) {
      return _selectedPaymentId;
    }
    if (methods.isEmpty) return null;
    return methods
        .firstWhere((m) => m.isDefault, orElse: () => methods.first)
        .id;
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
          leading: IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          ),
          centerTitle: true,
          title: const Text(
            'Finalizar Pedido',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        body: Builder(
          builder: (context) {
            final cart = context.watch<CartStore>();
            final methods = context.watch<PaymentStore>().methods;
            final effectivePaymentId = _effectivePaymentId(methods);

            return Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Revisão do Carrinho',
                          style: TextStyle(
                            fontSize: 26,
                            fontWeight: FontWeight.w800,
                            color: AppColors.textPrimary,
                            letterSpacing: -0.5,
                          ),
                        ),
                        const SizedBox(height: 6),
                        const Text(
                          'Confirme os itens selecionados',
                          style: TextStyle(
                            fontSize: 15,
                            color: AppColors.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 20),
                        _CartSection(cart: cart),
                        const SizedBox(height: 32),
                        const _SectionTitle('Endereço de Entrega'),
                        const SizedBox(height: 16),
                        _AddressSection(
                          addresses: _addresses,
                          selectedId: _selectedAddressId,
                          onSelect: (id) =>
                              setState(() => _selectedAddressId = id),
                        ),
                        const SizedBox(height: 32),
                        const _SectionTitle('Método de Pagamento'),
                        const SizedBox(height: 16),
                        _PaymentSection(
                          methods: methods,
                          selectedId: effectivePaymentId,
                          onSelect: (id) =>
                              setState(() => _selectedPaymentId = id),
                          onEdit: (id) => Navigator.pushNamed(
                            context,
                            '/add-payment-method',
                            arguments: id,
                          ),
                          onDelete: _confirmDelete,
                          onToggleDefault: (m) {
                            if (!m.isDefault) {
                              context.read<PaymentStore>().setDefault(m.id);
                            }
                          },
                          onAdd: () => Navigator.pushNamed(
                            context,
                            '/add-payment-method',
                          ),
                        ),
                        const SizedBox(height: 24),
                      ],
                    ),
                  ),
                ),
                _BottomBar(
                  total: cart.total,
                  showTotal: !cart.isEmpty,
                  enabled: _canFinalize(cart, effectivePaymentId),
                  onFinalize: () =>
                      _onFinalizePressed(cart, methods, effectivePaymentId),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  bool _addressOk() => _addresses.isEmpty || _selectedAddressId != null;

  bool _canFinalize(CartStore cart, String? paymentId) =>
      !cart.isEmpty && paymentId != null && _addressOk();

  void _onFinalizePressed(
    CartStore cart,
    List<PaymentMethod> methods,
    String? paymentId,
  ) {
    if (cart.isEmpty) {
      _snack('Adicione itens ao carrinho.');
      return;
    }
    if (paymentId == null) {
      _snack('Selecione um método de pagamento.');
      return;
    }
    final method = methods.firstWhere((m) => m.id == paymentId);
    _showFinalizeDialog(cart, method);
  }

  void _showFinalizeDialog(CartStore cart, PaymentMethod method) {
    final address = _selectedAddress;
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Confirmar pedido'),
        content: Text(
          'Total: ${formatBRL(cart.total)}\n'
          'Pagamento: ${_paymentTitle(method)}'
          '${address != null ? '\nEntrega: ${address.summary}' : ''}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              _placeOrder(method);
            },
            child: const Text(
              'Confirmar',
              style: TextStyle(color: AppColors.purple),
            ),
          ),
        ],
      ),
    );
  }

  void _placeOrder(PaymentMethod method) {
    context.read<CartStore>().clear();
    switch (method.type) {
      case PaymentMethodType.pix:
        _showCopyCodeDialog(
          title: 'Pague com PIX',
          description:
              'Copie o código abaixo e cole no app do seu banco para concluir o pagamento.',
          code: _generatePixCode(),
          copiedMessage: 'Código PIX copiado',
        );
        break;
      case PaymentMethodType.boleto:
        _showCopyCodeDialog(
          title: 'Pague com Boleto',
          description:
              'Copie a linha digitável abaixo e pague no app do seu banco. Compensação em até 2 dias úteis.',
          code: _generateBoletoCode(),
          copiedMessage: 'Linha digitável copiada',
        );
        break;
      case PaymentMethodType.creditCard:
        _snack('Pedido finalizado com sucesso!');
        Navigator.pop(context);
        break;
    }
  }

  void _showCopyCodeDialog({
    required String title,
    required String description,
    required String code,
    required String copiedMessage,
  }) {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: Text(title),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              description,
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 14,
              ),
            ),
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.inputFill,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                code,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 12,
                ),
              ),
            ),
            const SizedBox(height: 12),
            GestureDetector(
              onTap: () async {
                await Clipboard.setData(ClipboardData(text: code));
                _snack(copiedMessage);
              },
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.content_copy, size: 18, color: AppColors.purple),
                  SizedBox(width: 8),
                  Text(
                    'Copiar código',
                    style: TextStyle(
                      color: AppColors.purple,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              Navigator.pop(context);
            },
            child: const Text(
              'Concluir',
              style: TextStyle(color: AppColors.purple),
            ),
          ),
        ],
      ),
    );
  }

  void _confirmDelete(PaymentMethod method) {
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Remover método'),
        content: Text('Deseja remover ${_paymentTitle(method)}?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () {
              context.read<PaymentStore>().delete(method.id);
              Navigator.pop(dialogContext);
            },
            child: const Text(
              'Remover',
              style: TextStyle(color: AppColors.danger),
            ),
          ),
        ],
      ),
    );
  }

  void _snack(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}

// ---------------------------------------------------------------------------
// Geração de códigos (mock). Portado de generatePixCopyPasteCode /
// generateBoletoLinhaDigitavel do edu-kt.
// ---------------------------------------------------------------------------

String _generatePixCode() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  final rng = Random();
  final txid = List.generate(
    25,
    (_) => chars[rng.nextInt(chars.length)],
  ).join();
  return '00020126360014BR.GOV.BCB.PIX0114+55119999999995204000053039865802BR5909EDU STORE6009SAO PAULO62290525${txid}6304ABCD';
}

String _generateBoletoCode() {
  final rng = Random();
  final d = List.generate(47, (_) => rng.nextInt(10).toString()).join();
  return '${d.substring(0, 5)}.${d.substring(5, 10)} '
      '${d.substring(10, 15)}.${d.substring(15, 21)} '
      '${d.substring(21, 26)}.${d.substring(26, 32)} '
      '${d.substring(32, 33)} '
      '${d.substring(33, 47)}';
}

String _paymentTitle(PaymentMethod m) {
  switch (m.type) {
    case PaymentMethodType.creditCard:
      return '${m.cardBrand ?? 'Cartão'} •••• ${m.cardLast4 ?? '----'}';
    case PaymentMethodType.pix:
      return 'PIX';
    case PaymentMethodType.boleto:
      return 'Boleto';
  }
}

String _paymentSubtitle(PaymentMethod m) {
  switch (m.type) {
    case PaymentMethodType.creditCard:
      final parts = <String>[
        if ((m.cardholderName ?? '').trim().isNotEmpty) m.cardholderName!,
        if ((m.cardExpiry ?? '').length == 4)
          'Validade ${m.cardExpiry!.substring(0, 2)}/${m.cardExpiry!.substring(2)}',
      ];
      return parts.isEmpty ? 'Cartão de crédito' : parts.join(' • ');
    case PaymentMethodType.pix:
      return 'Código gerado na finalização • Aprovação imediata';
    case PaymentMethodType.boleto:
      return 'Compensação em até 2 dias úteis';
  }
}

// ---------------------------------------------------------------------------
// Seções
// ---------------------------------------------------------------------------

class _SectionTitle extends StatelessWidget {
  final String text;

  const _SectionTitle(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 22,
        fontWeight: FontWeight.w800,
        color: AppColors.textPrimary,
        letterSpacing: -0.3,
      ),
    );
  }
}

class _CartSection extends StatelessWidget {
  final CartStore cart;

  const _CartSection({required this.cart});

  @override
  Widget build(BuildContext context) {
    if (cart.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 16),
        child: Text(
          'Seu carrinho está vazio.',
          style: TextStyle(fontSize: 15, color: AppColors.textSecondary),
        ),
      );
    }
    final items = cart.items;
    return Column(
      children: [
        for (var i = 0; i < items.length; i++) ...[
          if (i > 0) const SizedBox(height: 16),
          _CartItemCard(item: items[i]),
        ],
        const SizedBox(height: 16),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text(
              'Total',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
            Text(
              formatBRL(cart.total),
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _CartItemCard extends StatelessWidget {
  final CartItem item;

  const _CartItemCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final product = item.product;
    final colors = categoryColorsFor(product.type);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: Container(
                  width: 88,
                  height: 88,
                  color: AppColors.cartImageBlue,
                  child: Icon(
                    iconForProduct(product.type),
                    size: 36,
                    color: AppColors.white.withValues(alpha: 0.9),
                  ),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: colors.background,
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            product.categoryLabel,
                            style: TextStyle(
                              color: colors.foreground,
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        const Spacer(),
                        GestureDetector(
                          onTap: () =>
                              context.read<CartStore>().removeAll(product.id),
                          child: const Icon(
                            Icons.close,
                            size: 18,
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      product.name,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        height: 1.2,
                      ),
                    ),
                    const SizedBox(height: 4),
                    RatingStars(
                      rating: product.ratingAvg,
                      count: product.ratingCount,
                      starSize: 12,
                      showCount: false,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${formatBRL(product.price)} cada',
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _QuantityStepper(
                quantity: item.quantity,
                onIncrement: () => context.read<CartStore>().add(product),
                onDecrement: () =>
                    context.read<CartStore>().decrement(product.id),
              ),
              Text(
                formatBRL(item.subtotal),
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _QuantityStepper extends StatelessWidget {
  final int quantity;
  final VoidCallback onIncrement;
  final VoidCallback onDecrement;

  const _QuantityStepper({
    required this.quantity,
    required this.onIncrement,
    required this.onDecrement,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.inputFill,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _StepButton(
            icon: Icons.remove,
            color: AppColors.danger,
            onTap: onDecrement,
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Text(
              '$quantity',
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 14,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          _StepButton(
            icon: Icons.add,
            color: AppColors.purple,
            onTap: onIncrement,
          ),
        ],
      ),
    );
  }
}

class _StepButton extends StatelessWidget {
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  const _StepButton({
    required this.icon,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      customBorder: const CircleBorder(),
      child: SizedBox(
        width: 36,
        height: 36,
        child: Icon(icon, size: 18, color: color),
      ),
    );
  }
}

class _AddressSection extends StatelessWidget {
  final List<Address> addresses;
  final String? selectedId;
  final ValueChanged<String> onSelect;

  const _AddressSection({
    required this.addresses,
    required this.selectedId,
    required this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    if (addresses.isEmpty) {
      return const Text(
        'Você ainda não cadastrou nenhum endereço. Cadastre em Perfil > Endereços.',
        style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
      );
    }
    return Column(
      children: [
        for (var i = 0; i < addresses.length; i++) ...[
          if (i > 0) const SizedBox(height: 12),
          _SelectableCard(
            selected: selectedId == addresses[i].id,
            onTap: () => onSelect(addresses[i].id),
            leadingIcon: Icons.location_on_outlined,
            leadingColor: AppColors.purple,
            title: addresses[i].label.isEmpty ? 'Endereço' : addresses[i].label,
            badge: addresses[i].isFavorite ? 'FAVORITO' : null,
            subtitle: addresses[i].summary,
          ),
        ],
      ],
    );
  }
}

class _PaymentSection extends StatelessWidget {
  final List<PaymentMethod> methods;
  final String? selectedId;
  final ValueChanged<String> onSelect;
  final ValueChanged<String> onEdit;
  final ValueChanged<PaymentMethod> onDelete;
  final ValueChanged<PaymentMethod> onToggleDefault;
  final VoidCallback onAdd;

  const _PaymentSection({
    required this.methods,
    required this.selectedId,
    required this.onSelect,
    required this.onEdit,
    required this.onDelete,
    required this.onToggleDefault,
    required this.onAdd,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        if (methods.isEmpty)
          const Align(
            alignment: Alignment.centerLeft,
            child: Padding(
              padding: EdgeInsets.only(bottom: 12),
              child: Text(
                'Você ainda não cadastrou nenhum método de pagamento.',
                style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
              ),
            ),
          )
        else
          for (var i = 0; i < methods.length; i++) ...[
            if (i > 0) const SizedBox(height: 12),
            _PaymentMethodCard(
              method: methods[i],
              selected: selectedId == methods[i].id,
              onTap: () => onSelect(methods[i].id),
              onEdit: () => onEdit(methods[i].id),
              onDelete: () => onDelete(methods[i]),
              onToggleDefault: () => onToggleDefault(methods[i]),
            ),
          ],
        const SizedBox(height: 12),
        _AddPaymentButton(onTap: onAdd),
      ],
    );
  }
}

class _PaymentMethodCard extends StatelessWidget {
  final PaymentMethod method;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onToggleDefault;

  const _PaymentMethodCard({
    required this.method,
    required this.selected,
    required this.onTap,
    required this.onEdit,
    required this.onDelete,
    required this.onToggleDefault,
  });

  ({IconData icon, Color color}) get _visual {
    switch (method.type) {
      case PaymentMethodType.creditCard:
        return (icon: Icons.credit_card, color: AppColors.purple);
      case PaymentMethodType.pix:
        return (icon: Icons.pix, color: AppColors.greenDark);
      case PaymentMethodType.boleto:
        return (
          icon: Icons.receipt_long_outlined,
          color: AppColors.textSecondary,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final visual = _visual;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: selected ? AppColors.white : AppColors.inputFill,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected ? AppColors.purple : Colors.transparent,
            width: 2,
          ),
        ),
        child: Column(
          children: [
            Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: AppColors.white,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.inputBorder),
                  ),
                  child: Icon(visual.icon, color: visual.color),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              _paymentTitle(method),
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 16,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          if (method.isDefault) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.purpleSoft,
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: const Text(
                                'PADRÃO',
                                style: TextStyle(
                                  color: AppColors.purple,
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        _paymentSubtitle(method),
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
                if (selected)
                  Container(
                    width: 24,
                    height: 24,
                    decoration: const BoxDecoration(
                      color: AppColors.purple,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.check,
                      size: 16,
                      color: AppColors.white,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                _ActionIcon(
                  icon: method.isDefault ? Icons.star : Icons.star_border,
                  color: method.isDefault
                      ? AppColors.purple
                      : AppColors.textSecondary,
                  tooltip: 'Definir como padrão',
                  onTap: onToggleDefault,
                ),
                _ActionIcon(
                  icon: Icons.edit_outlined,
                  color: AppColors.textSecondary,
                  tooltip: 'Editar',
                  onTap: onEdit,
                ),
                _ActionIcon(
                  icon: Icons.delete_outline,
                  color: AppColors.danger,
                  tooltip: 'Remover',
                  onTap: onDelete,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionIcon extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String tooltip;
  final VoidCallback onTap;

  const _ActionIcon({
    required this.icon,
    required this.color,
    required this.tooltip,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return IconButton(
      onPressed: onTap,
      tooltip: tooltip,
      iconSize: 20,
      constraints: const BoxConstraints.tightFor(width: 36, height: 36),
      padding: EdgeInsets.zero,
      icon: Icon(icon, color: color),
    );
  }
}

class _SelectableCard extends StatelessWidget {
  final bool selected;
  final VoidCallback onTap;
  final IconData leadingIcon;
  final Color leadingColor;
  final String title;
  final String? badge;
  final String subtitle;

  const _SelectableCard({
    required this.selected,
    required this.onTap,
    required this.leadingIcon,
    required this.leadingColor,
    required this.title,
    required this.badge,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: selected ? AppColors.white : AppColors.inputFill,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected ? AppColors.purple : Colors.transparent,
            width: 2,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: AppColors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.inputBorder),
              ),
              child: Icon(leadingIcon, color: leadingColor),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Flexible(
                        child: Text(
                          title,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      if (badge != null) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.purpleSoft,
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            badge!,
                            style: const TextStyle(
                              color: AppColors.purple,
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            if (selected)
              Container(
                width: 24,
                height: 24,
                decoration: const BoxDecoration(
                  color: AppColors.purple,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.check,
                  size: 16,
                  color: AppColors.white,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _AddPaymentButton extends StatelessWidget {
  final VoidCallback onTap;

  const _AddPaymentButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: DottedBorderBox(
        child: Container(
          padding: const EdgeInsets.all(16),
          alignment: Alignment.center,
          child: const Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.add, color: AppColors.textSecondary),
              SizedBox(width: 8),
              Text(
                'Outro método',
                style: TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BottomBar extends StatelessWidget {
  final double total;
  final bool showTotal;
  final bool enabled;
  final VoidCallback onFinalize;

  const _BottomBar({
    required this.total,
    required this.showTotal,
    required this.enabled,
    required this.onFinalize,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.white,
      elevation: 12,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (showTotal) ...[
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Total',
                      style: TextStyle(
                        fontSize: 14,
                        color: AppColors.textSecondary,
                      ),
                    ),
                    Text(
                      formatBRL(total),
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
              ],
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: enabled ? onFinalize : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.purple,
                    foregroundColor: AppColors.white,
                    disabledBackgroundColor: AppColors.purple.withValues(
                      alpha: 0.4,
                    ),
                    disabledForegroundColor: AppColors.white.withValues(
                      alpha: 0.8,
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: const Text(
                    'Finalizar Pedido',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Borda tracejada usada no botão "Outro método". Mantido do checkout original.
class DottedBorderBox extends StatelessWidget {
  final Widget child;

  const DottedBorderBox({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _DashedBorderPainter(),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Container(color: AppColors.white, child: child),
      ),
    );
  }
}

class _DashedBorderPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.textSecondary.withValues(alpha: 0.5)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;

    final rrect = RRect.fromRectAndRadius(
      Rect.fromLTWH(0, 0, size.width, size.height),
      const Radius.circular(16),
    );
    final path = Path()..addRRect(rrect);

    const dashWidth = 6.0;
    const dashSpace = 4.0;
    for (final metric in path.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        final next = distance + dashWidth;
        canvas.drawPath(
          metric.extractPath(distance, next.clamp(0, metric.length)),
          paint,
        );
        distance = next + dashSpace;
      }
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

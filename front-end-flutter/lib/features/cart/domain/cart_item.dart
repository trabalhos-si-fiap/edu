import '../../marketplace/domain/product.dart';

/// Item do carrinho. Portado de edu-kt `CartItem`, simplificado para referenciar
/// o `Product` diretamente e calcular o subtotal a partir dele.
class CartItem {
  final Product product;
  final int quantity;

  const CartItem({required this.product, required this.quantity});

  double get price => product.price;
  double get subtotal => product.price * quantity;

  CartItem copyWith({int? quantity}) =>
      CartItem(product: product, quantity: quantity ?? this.quantity);
}

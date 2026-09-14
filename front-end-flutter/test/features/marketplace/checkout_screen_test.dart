import 'package:edu_ia/features/cart/domain/cart_item.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/checkout_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/product_image.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/product_visuals.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

CartItem _item({String imageUrl = ''}) => CartItem(
      product: Product(
        id: 'p1',
        name: 'Mesa de estudo 120 cm',
        type: 'mobiliario',
        subtype: '',
        description: '',
        price: 399.90,
        imageUrl: imageUrl,
      ),
      quantity: 1,
    );

Widget _harness(CartItem item) => MaterialApp(
      home: Scaffold(body: CartItemCard(item: item)),
    );

void main() {
  testWidgets('the cart review shows the product photo from image_url',
      (tester) async {
    const url = 'https://cdn.example.com/mesa.jpg';
    await tester.pumpWidget(_harness(_item(imageUrl: url)));

    // A mesma foto do card e do detalhe do produto — não um ícone genérico.
    expect(
      find.byWidgetPredicate((w) => w is ProductImage && w.imageUrl == url),
      findsOneWidget,
    );
  });

  testWidgets('without an image the cart review keeps the type placeholder',
      (tester) async {
    await tester.pumpWidget(_harness(_item()));

    expect(find.byIcon(iconForProduct('mobiliario')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

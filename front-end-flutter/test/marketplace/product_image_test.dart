import 'package:edu_ia/features/marketplace/presentation/widgets/product_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows icon placeholder when imageUrl is empty', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: ProductImage(imageUrl: '', type: 'apostila')),
      ),
    );
    expect(find.byType(Icon), findsOneWidget);
  });
}

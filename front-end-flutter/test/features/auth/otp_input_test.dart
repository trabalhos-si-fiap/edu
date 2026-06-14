import 'package:edu_ia/features/auth/presentation/widgets/otp_input.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Widget _harness(ValueChanged<String> onChanged) => MaterialApp(
      home: Scaffold(body: OtpInput(onChanged: onChanged)),
    );

void main() {
  testWidgets('renders six single-digit boxes', (tester) async {
    await tester.pumpWidget(_harness((_) {}));
    expect(find.byType(TextField), findsNWidgets(6));
  });

  testWidgets('emits the concatenated code as digits are typed',
      (tester) async {
    var code = '';
    await tester.pumpWidget(_harness((v) => code = v));

    final boxes = find.byType(TextField);
    for (var i = 0; i < 6; i++) {
      await tester.enterText(boxes.at(i), '${i + 1}');
    }
    await tester.pump();

    expect(code, '123456');
  });

  testWidgets('auto-advances focus to the next box after a digit',
      (tester) async {
    await tester.pumpWidget(_harness((_) {}));

    final boxes = find.byType(TextField);
    await tester.enterText(boxes.at(0), '1');
    await tester.pump();

    final second = tester.widget<TextField>(boxes.at(1));
    expect(second.focusNode!.hasFocus, isTrue);
  });
}

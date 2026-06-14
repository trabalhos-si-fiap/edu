import 'package:edu_ia/features/auth/presentation/widgets/otp_input.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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

  testWidgets('does not overflow on a narrow (360dp-equivalent) width',
      (tester) async {
    // On a 360dp-wide device the card's inner width is ~280px. Fixed-width
    // boxes overflow here; the layout must adapt to the available width.
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 280,
              child: OtpInput(onChanged: (_) {}),
            ),
          ),
        ),
      ),
    );

    expect(tester.takeException(), isNull);
    expect(find.byType(TextField), findsNWidgets(6));
  });

  testWidgets('backspace on an empty box clears and focuses the previous box',
      (tester) async {
    final emitted = <String>[];
    await tester.pumpWidget(_harness(emitted.add));

    final boxes = find.byType(TextField);

    // Type '1' into box 0 — focus auto-advances to box 1.
    await tester.enterText(boxes.at(0), '1');
    await tester.pump();

    // Type '2' into box 1 — focus auto-advances to box 2.
    await tester.enterText(boxes.at(1), '2');
    await tester.pump();

    // Box 2 is currently focused and empty. Send backspace.
    await tester.sendKeyEvent(LogicalKeyboardKey.backspace);
    await tester.pump();

    // Box 1 should now have focus and its text should be cleared.
    final box1 = tester.widget<TextField>(boxes.at(1));
    expect(box1.focusNode!.hasFocus, isTrue);
    expect(box1.controller!.text, isEmpty);

    // The last onChanged emission should reflect only the digit in box 0.
    expect(emitted.last, '1');
  });
}

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../../core/theme/app_colors.dart';

/// A six-box single-use-code input. Each box accepts one digit; typing a digit
/// advances focus to the next box, and backspace on an empty box returns to the
/// previous one. [onChanged] receives the concatenated value (0–6 digits).
class OtpInput extends StatefulWidget {
  const OtpInput({super.key, required this.onChanged});

  final ValueChanged<String> onChanged;

  @override
  State<OtpInput> createState() => _OtpInputState();
}

class _OtpInputState extends State<OtpInput> {
  static const _length = 6;
  late final List<TextEditingController> _controllers;
  late final List<FocusNode> _focusNodes;

  @override
  void initState() {
    super.initState();
    _controllers = List.generate(_length, (_) => TextEditingController());
    _focusNodes = List.generate(_length, (_) => FocusNode());
  }

  @override
  void dispose() {
    for (final c in _controllers) {
      c.dispose();
    }
    for (final f in _focusNodes) {
      f.dispose();
    }
    super.dispose();
  }

  void _emit() => widget.onChanged(_controllers.map((c) => c.text).join());

  void _onChanged(int index, String value) {
    if (value.isNotEmpty && index < _length - 1) {
      _focusNodes[index + 1].requestFocus();
    }
    _emit();
  }

  KeyEventResult _onKey(int index, KeyEvent event) {
    if (event is KeyDownEvent &&
        event.logicalKey == LogicalKeyboardKey.backspace &&
        _controllers[index].text.isEmpty &&
        index > 0) {
      _controllers[index - 1].clear();
      _focusNodes[index - 1].requestFocus();
      _emit();
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }

  @override
  Widget build(BuildContext context) {
    // Boxes share the available width evenly (with a small gap between them)
    // instead of a fixed width, so the row never overflows on narrow screens.
    return Row(
      children: List.generate(_length, (index) {
        return Expanded(
          child: Padding(
            padding: EdgeInsets.only(left: index == 0 ? 0 : 8),
            child: Focus(
              skipTraversal: true,
              canRequestFocus: false,
              onKeyEvent: (node, event) => _onKey(index, event),
              child: TextField(
                controller: _controllers[index],
                focusNode: _focusNodes[index],
                textAlign: TextAlign.center,
                keyboardType: TextInputType.number,
                maxLength: 1,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                ),
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                decoration: const InputDecoration(counterText: ''),
                onChanged: (value) => _onChanged(index, value),
              ),
            ),
          ),
        );
      }),
    );
  }
}

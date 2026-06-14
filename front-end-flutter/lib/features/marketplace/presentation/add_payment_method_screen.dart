import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/features/payment/data/payment_methods_api.dart';
import 'package:edu_ia/features/payment/domain/payment_method.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Cadastra um método de pagamento. Portado de edu-kt `AddPaymentMethodScreen`.
/// Persiste em `POST /payment-methods` e retorna `true` ao chamador (checkout)
/// para que ele recarregue a lista. O backend não suporta editar campos de um
/// método existente — apenas criar, definir padrão e remover.
class AddPaymentMethodScreen extends StatefulWidget {
  const AddPaymentMethodScreen({super.key});

  @override
  State<AddPaymentMethodScreen> createState() => _AddPaymentMethodScreenState();
}

enum _PaymentType { creditCard, pix, boleto }

class _AddPaymentMethodScreenState extends State<AddPaymentMethodScreen> {
  final _api = PaymentMethodsApi();

  _PaymentType _selected = _PaymentType.creditCard;

  final _cardNumberController = TextEditingController();
  final _cardNameController = TextEditingController();
  final _expiryController = TextEditingController();
  final _cvvController = TextEditingController();
  final _taxIdController = TextEditingController();

  bool _saveAsDefault = false;
  bool _saving = false;

  @override
  void dispose() {
    _cardNumberController.dispose();
    _cardNameController.dispose();
    _expiryController.dispose();
    _cvvController.dispose();
    _taxIdController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_saving) return;
    final error = _validate();
    if (error != null) {
      _snack(error);
      return;
    }

    setState(() => _saving = true);
    try {
      await _api.create(_buildInput());
    } on PaymentMethodException catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      _snack(e.message);
      return;
    }

    if (!mounted) return;
    Navigator.pop(context, true);
    _snack('Método de pagamento adicionado');
  }

  PaymentMethodInput _buildInput() {
    switch (_selected) {
      case _PaymentType.creditCard:
        final digits = _cardNumberController.text.replaceAll(' ', '');
        return PaymentMethodInput(
          type: PaymentMethodType.creditCard,
          isDefault: _saveAsDefault,
          cardLast4: digits.substring(digits.length - 4),
          cardBrand: brandFromNumber(digits),
          cardholderName: _cardNameController.text.trim(),
          cardExpiry: _expiryController.text.replaceAll('/', ''),
        );
      case _PaymentType.pix:
        return PaymentMethodInput(
          type: PaymentMethodType.pix,
          isDefault: _saveAsDefault,
        );
      case _PaymentType.boleto:
        return PaymentMethodInput(
          type: PaymentMethodType.boleto,
          isDefault: _saveAsDefault,
        );
    }
  }

  String? _validate() {
    switch (_selected) {
      case _PaymentType.creditCard:
        return _validateCard();
      case _PaymentType.pix:
      case _PaymentType.boleto:
        return null;
    }
  }

  /// Validação portada de `validateCreditCardForm` do edu-kt. O número completo
  /// e o CVV são validados localmente e nunca enviados ao backend (apenas os
  /// últimos 4 dígitos e a bandeira persistem).
  String? _validateCard() {
    final numberDigits = _cardNumberController.text.replaceAll(' ', '');
    if (numberDigits.length < 13 || numberDigits.length > 19) {
      return 'Número de cartão inválido';
    }
    if (_cvvController.text.length < 3) return 'CVV inválido';
    if (_cardNameController.text.trim().isEmpty) return 'Informe o nome';
    if (!_isValidExpiry(_expiryController.text)) return 'Validade inválida';
    final tax = _taxIdController.text.replaceAll(RegExp(r'\D'), '');
    if (tax.length != 11 && tax.length != 14) return 'CPF/CNPJ inválido';
    return null;
  }

  void _snack(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  bool _isValidExpiry(String text) {
    final digits = text.replaceAll('/', '');
    if (digits.length != 4) return false;
    final month = int.tryParse(digits.substring(0, 2)) ?? 0;
    return month >= 1 && month <= 12;
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
            'Adicionar Método',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Tipo de pagamento',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 12),
                _TypeSelector(
                  selected: _selected,
                  onChanged: (type) => setState(() => _selected = type),
                ),
                const SizedBox(height: 28),
                if (_selected == _PaymentType.creditCard) ..._cardFields(),
                if (_selected == _PaymentType.pix) ..._pixInfo(),
                if (_selected == _PaymentType.boleto) ..._boletoInfo(),
                const SizedBox(height: 12),
                _DefaultCheckbox(
                  value: _saveAsDefault,
                  onChanged: (v) => setState(() => _saveAsDefault = v),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _saving ? null : _submit,
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
                    child: _saving
                        ? const SizedBox(
                            height: 20,
                            width: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: AppColors.white,
                            ),
                          )
                        : const Text(
                            'Salvar método',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                  ),
                ),
                const SizedBox(height: 12),
                const Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.lock_outline,
                      size: 14,
                      color: AppColors.textSecondary,
                    ),
                    SizedBox(width: 6),
                    Text(
                      'Pagamentos protegidos com criptografia',
                      style: TextStyle(
                        fontSize: 12,
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _cardFields() {
    return [
      _LabeledField(
        label: 'Número do cartão',
        child: TextField(
          controller: _cardNumberController,
          keyboardType: TextInputType.number,
          inputFormatters: [
            FilteringTextInputFormatter.digitsOnly,
            LengthLimitingTextInputFormatter(19),
            _CardNumberFormatter(),
          ],
          decoration: _inputDecoration(hint: '0000 0000 0000 0000'),
        ),
      ),
      _LabeledField(
        label: 'Nome impresso no cartão',
        child: TextField(
          controller: _cardNameController,
          textCapitalization: TextCapitalization.characters,
          decoration: _inputDecoration(hint: 'NOME COMPLETO'),
        ),
      ),
      Row(
        children: [
          Expanded(
            child: _LabeledField(
              label: 'Validade',
              child: TextField(
                controller: _expiryController,
                keyboardType: TextInputType.number,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(4),
                  _ExpiryFormatter(),
                ],
                decoration: _inputDecoration(hint: 'MM/AA'),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _LabeledField(
              label: 'CVV',
              child: TextField(
                controller: _cvvController,
                keyboardType: TextInputType.number,
                obscureText: true,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(4),
                ],
                decoration: _inputDecoration(hint: '•••'),
              ),
            ),
          ),
        ],
      ),
      _LabeledField(
        label: 'CPF/CNPJ do titular',
        child: TextField(
          controller: _taxIdController,
          keyboardType: TextInputType.number,
          inputFormatters: [
            FilteringTextInputFormatter.digitsOnly,
            LengthLimitingTextInputFormatter(14),
            _TaxIdFormatter(),
          ],
          decoration: _inputDecoration(hint: '000.000.000-00'),
        ),
      ),
    ];
  }

  List<Widget> _pixInfo() {
    return [
      _InfoBox(
        background: AppColors.greenSoft.withValues(alpha: 0.5),
        contentColor: AppColors.greenDark,
        icon: Icons.info_outline,
        message:
            'Ao finalizar o pedido, geramos um código PIX copia e cola para você pagar no app do seu banco. Aprovação imediata.',
      ),
    ];
  }

  List<Widget> _boletoInfo() {
    return [
      _InfoBox(
        background: AppColors.inputFill,
        contentColor: AppColors.textSecondary,
        icon: Icons.schedule,
        message:
            'O boleto será gerado na finalização do pedido. Compensação em até 2 dias úteis.',
      ),
    ];
  }

  InputDecoration _inputDecoration({required String hint}) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: AppColors.textSecondary, fontSize: 14),
      filled: true,
      fillColor: AppColors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.inputBorder),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.inputBorder),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.purple, width: 1.5),
      ),
    );
  }
}

class _TypeSelector extends StatelessWidget {
  final _PaymentType selected;
  final ValueChanged<_PaymentType> onChanged;

  const _TypeSelector({required this.selected, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    const options = [
      (_PaymentType.creditCard, Icons.credit_card, 'Cartão'),
      (_PaymentType.pix, Icons.pix, 'PIX'),
      (_PaymentType.boleto, Icons.receipt_long_outlined, 'Boleto'),
    ];

    return Row(
      children: [
        for (var i = 0; i < options.length; i++) ...[
          if (i > 0) const SizedBox(width: 10),
          Expanded(
            child: _TypeOption(
              icon: options[i].$2,
              label: options[i].$3,
              selected: selected == options[i].$1,
              onTap: () => onChanged(options[i].$1),
            ),
          ),
        ],
      ],
    );
  }
}

class _TypeOption extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _TypeOption({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          color: selected ? AppColors.white : AppColors.inputFill,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? AppColors.purple : Colors.transparent,
            width: 2,
          ),
        ),
        child: Column(
          children: [
            Icon(
              icon,
              color: selected ? AppColors.purple : AppColors.textSecondary,
            ),
            const SizedBox(height: 6),
            Text(
              label,
              style: TextStyle(
                color: selected
                    ? AppColors.textPrimary
                    : AppColors.textSecondary,
                fontWeight: FontWeight.w700,
                fontSize: 13,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LabeledField extends StatelessWidget {
  final String label;
  final Widget child;

  const _LabeledField({required this.label, required this.child});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          child,
        ],
      ),
    );
  }
}

class _InfoBox extends StatelessWidget {
  final Color background;
  final Color contentColor;
  final IconData icon;
  final String message;

  const _InfoBox({
    required this.background,
    required this.contentColor,
    required this.icon,
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18, color: contentColor),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                fontSize: 13,
                color: contentColor,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DefaultCheckbox extends StatelessWidget {
  final bool value;
  final ValueChanged<bool> onChanged;

  const _DefaultCheckbox({required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onChanged(!value),
      child: Row(
        children: [
          SizedBox(
            width: 24,
            height: 24,
            child: Checkbox(
              value: value,
              onChanged: (v) => onChanged(v ?? false),
              activeColor: AppColors.purple,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(4),
              ),
            ),
          ),
          const SizedBox(width: 10),
          const Text(
            'Definir como método padrão',
            style: TextStyle(
              fontSize: 14,
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _CardNumberFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = newValue.text.replaceAll(' ', '');
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && i % 4 == 0) buffer.write(' ');
      buffer.write(digits[i]);
    }
    final text = buffer.toString();
    return TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }
}

class _ExpiryFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = newValue.text.replaceAll('/', '');
    var text = digits;
    if (digits.length >= 3) {
      text = '${digits.substring(0, 2)}/${digits.substring(2)}';
    }
    return TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }
}

class _TaxIdFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = newValue.text.replaceAll(RegExp(r'\D'), '');
    final buffer = StringBuffer();
    // Até 11 dígitos formata como CPF; acima, como CNPJ.
    final cpf = digits.length <= 11;
    final separators = cpf
        ? const {3: '.', 6: '.', 9: '-'}
        : const {2: '.', 5: '.', 8: '/', 12: '-'};
    for (var i = 0; i < digits.length; i++) {
      if (separators.containsKey(i)) buffer.write(separators[i]);
      buffer.write(digits[i]);
    }
    final text = buffer.toString();
    return TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }
}

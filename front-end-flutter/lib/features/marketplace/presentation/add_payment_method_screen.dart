import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class AddPaymentMethodScreen extends StatefulWidget {
  const AddPaymentMethodScreen({super.key});

  @override
  State<AddPaymentMethodScreen> createState() => _AddPaymentMethodScreenState();
}

enum _PaymentType { creditCard, pix, boleto }

class _AddPaymentMethodScreenState extends State<AddPaymentMethodScreen> {
  final _formKey = GlobalKey<FormState>();
  _PaymentType _selected = _PaymentType.creditCard;

  final _cardNumberController = TextEditingController();
  final _cardNameController = TextEditingController();
  final _expiryController = TextEditingController();
  final _cvvController = TextEditingController();
  final _pixKeyController = TextEditingController();

  bool _saveAsDefault = false;

  @override
  void dispose() {
    _cardNumberController.dispose();
    _cardNameController.dispose();
    _expiryController.dispose();
    _cvvController.dispose();
    _pixKeyController.dispose();
    super.dispose();
  }

  void _submit() {
    if (_selected == _PaymentType.creditCard) {
      if (!_formKey.currentState!.validate()) return;
    }
    Navigator.pop(context);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Método de pagamento adicionado')),
    );
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
          child: Form(
            key: _formKey,
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
                  if (_selected == _PaymentType.pix) ..._pixFields(),
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
                      onPressed: _submit,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.purple,
                        foregroundColor: AppColors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text(
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
      ),
    );
  }

  List<Widget> _cardFields() {
    return [
      _LabeledField(
        label: 'Número do cartão',
        child: TextFormField(
          controller: _cardNumberController,
          keyboardType: TextInputType.number,
          inputFormatters: [
            FilteringTextInputFormatter.digitsOnly,
            LengthLimitingTextInputFormatter(19),
            _CardNumberFormatter(),
          ],
          decoration: _inputDecoration(hint: '0000 0000 0000 0000'),
          validator: (v) {
            final digits = (v ?? '').replaceAll(' ', '');
            if (digits.length < 13) return 'Número de cartão inválido';
            return null;
          },
        ),
      ),
      _LabeledField(
        label: 'Nome impresso no cartão',
        child: TextFormField(
          controller: _cardNameController,
          textCapitalization: TextCapitalization.characters,
          decoration: _inputDecoration(hint: 'NOME COMPLETO'),
          validator: (v) =>
              (v == null || v.trim().isEmpty) ? 'Informe o nome' : null,
        ),
      ),
      Row(
        children: [
          Expanded(
            child: _LabeledField(
              label: 'Validade',
              child: TextFormField(
                controller: _expiryController,
                keyboardType: TextInputType.number,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(4),
                  _ExpiryFormatter(),
                ],
                decoration: _inputDecoration(hint: 'MM/AA'),
                validator: (v) =>
                    (v == null || v.length < 5) ? 'Inválida' : null,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: _LabeledField(
              label: 'CVV',
              child: TextFormField(
                controller: _cvvController,
                keyboardType: TextInputType.number,
                obscureText: true,
                inputFormatters: [
                  FilteringTextInputFormatter.digitsOnly,
                  LengthLimitingTextInputFormatter(4),
                ],
                decoration: _inputDecoration(hint: '•••'),
                validator: (v) =>
                    (v == null || v.length < 3) ? 'Inválido' : null,
              ),
            ),
          ),
        ],
      ),
    ];
  }

  List<Widget> _pixFields() {
    return [
      _LabeledField(
        label: 'Chave PIX',
        child: TextFormField(
          controller: _pixKeyController,
          decoration: _inputDecoration(
            hint: 'CPF, e-mail, telefone ou chave aleatória',
          ),
        ),
      ),
      Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFFD1F4DD).withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Row(
          children: [
            Icon(Icons.info_outline, size: 18, color: Color(0xFF15803D)),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'Aprovação imediata após o pagamento.',
                style: TextStyle(
                  fontSize: 13,
                  color: Color(0xFF15803D),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    ];
  }

  List<Widget> _boletoInfo() {
    return [
      Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.inputFill,
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Row(
          children: [
            Icon(
              Icons.schedule,
              size: 18,
              color: AppColors.textSecondary,
            ),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'O boleto será gerado na finalização do pedido. Compensação em até 2 dias úteis.',
                style: TextStyle(
                  fontSize: 13,
                  color: AppColors.textSecondary,
                ),
              ),
            ),
          ],
        ),
      ),
    ];
  }

  InputDecoration _inputDecoration({required String hint}) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: AppColors.textSecondary, fontSize: 14),
      filled: true,
      fillColor: AppColors.white,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: 16,
        vertical: 16,
      ),
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
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: Color(0xFFDC2626)),
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
    final options = [
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
                color: selected ? AppColors.textPrimary : AppColors.textSecondary,
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
    String text = digits;
    if (digits.length >= 3) {
      text = '${digits.substring(0, 2)}/${digits.substring(2)}';
    }
    return TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }
}

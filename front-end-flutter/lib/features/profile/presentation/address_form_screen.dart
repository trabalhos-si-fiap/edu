import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/theme/app_colors.dart';
import '../data/addresses_api.dart';
import '../domain/address.dart';

/// Formulário de criação/edição de endereço. O [Address] a editar chega via
/// route arguments; ausente significa criação. Retorna `true` ao salvar para
/// que a lista recarregue.
class AddressFormScreen extends StatefulWidget {
  const AddressFormScreen({super.key});

  @override
  State<AddressFormScreen> createState() => _AddressFormScreenState();
}

class _AddressFormScreenState extends State<AddressFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _api = AddressesApi();

  final _label = TextEditingController();
  final _zipCode = TextEditingController();
  final _street = TextEditingController();
  final _number = TextEditingController();
  final _complement = TextEditingController();
  final _neighborhood = TextEditingController();
  final _city = TextEditingController();
  final _state = TextEditingController();

  bool _isFavorite = false;
  bool _submitting = false;
  bool _prefilled = false;
  Address? _editing;

  bool get _isEditing => _editing != null;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_prefilled) return;
    _prefilled = true;
    final arg = ModalRoute.of(context)?.settings.arguments;
    if (arg is! Address) return;
    _editing = arg;
    _label.text = arg.label;
    _zipCode.text = arg.zipCode;
    _street.text = arg.street;
    _number.text = arg.number;
    _complement.text = arg.complement;
    _neighborhood.text = arg.neighborhood;
    _city.text = arg.city;
    _state.text = arg.state;
    _isFavorite = arg.isFavorite;
  }

  @override
  void dispose() {
    for (final c in [
      _label,
      _zipCode,
      _street,
      _number,
      _complement,
      _neighborhood,
      _city,
      _state,
    ]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    if (_submitting) return;
    if (!_formKey.currentState!.validate()) return;

    final input = AddressInput(
      label: _label.text.trim(),
      zipCode: _zipCode.text.trim(),
      street: _street.text.trim(),
      number: _number.text.trim(),
      complement: _complement.text.trim(),
      neighborhood: _neighborhood.text.trim(),
      city: _city.text.trim(),
      state: _state.text.trim().toUpperCase(),
      isFavorite: _isFavorite,
    );

    setState(() => _submitting = true);
    try {
      if (_isEditing) {
        await _api.update(_editing!.id, input);
      } else {
        await _api.create(input);
      }
      if (!mounted) return;
      Navigator.pop(context, true);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(_isEditing ? 'Endereço atualizado' : 'Endereço adicionado'),
        ),
      );
    } on AddressException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
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
          title: Text(
            _isEditing ? 'Editar endereço' : 'Novo endereço',
            style: const TextStyle(
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
                  _Field(
                    label: 'Identificação',
                    controller: _label,
                    hint: 'Casa, Trabalho…',
                    maxLength: 60,
                    required: false,
                  ),
                  _Field(
                    label: 'CEP',
                    controller: _zipCode,
                    hint: '00000-000',
                    keyboardType: TextInputType.number,
                    maxLength: 9,
                    inputFormatters: [_CepFormatter()],
                  ),
                  _Field(
                    label: 'Rua',
                    controller: _street,
                    hint: 'Av. Paulista',
                    maxLength: 160,
                  ),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: _Field(
                          label: 'Número',
                          controller: _number,
                          hint: '1000',
                          maxLength: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        flex: 2,
                        child: _Field(
                          label: 'Complemento',
                          controller: _complement,
                          hint: 'Apto 52',
                          maxLength: 120,
                          required: false,
                        ),
                      ),
                    ],
                  ),
                  _Field(
                    label: 'Bairro',
                    controller: _neighborhood,
                    hint: 'Bela Vista',
                    maxLength: 120,
                  ),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        flex: 3,
                        child: _Field(
                          label: 'Cidade',
                          controller: _city,
                          hint: 'São Paulo',
                          maxLength: 120,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _Field(
                          label: 'UF',
                          controller: _state,
                          hint: 'SP',
                          maxLength: 2,
                          capitalize: true,
                          validator: (v) {
                            final t = (v ?? '').trim();
                            if (t.length != 2) return 'UF';
                            return null;
                          },
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  _FavoriteSwitch(
                    value: _isFavorite,
                    onChanged: (v) => setState(() => _isFavorite = v),
                  ),
                  const SizedBox(height: 20),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: _submitting ? null : _submit,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.purple,
                        foregroundColor: AppColors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: _submitting
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: AppColors.white,
                              ),
                            )
                          : Text(
                              _isEditing ? 'Salvar alterações' : 'Salvar endereço',
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Field extends StatelessWidget {
  const _Field({
    required this.label,
    required this.controller,
    required this.hint,
    this.maxLength,
    this.keyboardType,
    this.inputFormatters,
    this.required = true,
    this.capitalize = false,
    this.validator,
  });

  final String label;
  final TextEditingController controller;
  final String hint;
  final int? maxLength;
  final TextInputType? keyboardType;
  final List<TextInputFormatter>? inputFormatters;
  final bool required;
  final bool capitalize;
  final String? Function(String?)? validator;

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
          const SizedBox(height: 6),
          TextFormField(
            controller: controller,
            keyboardType: keyboardType,
            maxLength: maxLength,
            inputFormatters: inputFormatters,
            textCapitalization: capitalize
                ? TextCapitalization.characters
                : TextCapitalization.sentences,
            validator: validator ??
                (required
                    ? (v) => (v == null || v.trim().isEmpty) ? 'Obrigatório' : null
                    : null),
            decoration: InputDecoration(
              counterText: '',
              hintText: hint,
              hintStyle:
                  const TextStyle(color: AppColors.textSecondary, fontSize: 14),
              filled: true,
              fillColor: AppColors.white,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
            ),
          ),
        ],
      ),
    );
  }
}

class _FavoriteSwitch extends StatelessWidget {
  const _FavoriteSwitch({required this.value, required this.onChanged});

  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.inputBorder),
      ),
      child: Row(
        children: [
          const Icon(Icons.star_outline, color: AppColors.star, size: 20),
          const SizedBox(width: 12),
          const Expanded(
            child: Text(
              'Definir como endereço favorito',
              style: TextStyle(fontSize: 14, color: AppColors.textPrimary),
            ),
          ),
          Switch(
            value: value,
            activeThumbColor: AppColors.purple,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}

/// Formata o CEP enquanto o usuário digita: 00000-000.
class _CepFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = newValue.text.replaceAll(RegExp(r'\D'), '');
    final trimmed = digits.length > 8 ? digits.substring(0, 8) : digits;
    final text = trimmed.length > 5
        ? '${trimmed.substring(0, 5)}-${trimmed.substring(5)}'
        : trimmed;
    return TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }
}

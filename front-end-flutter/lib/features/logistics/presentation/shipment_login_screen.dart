import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../../../core/theme/app_colors.dart';
import '../data/logistics_api.dart';
import 'delivery_queue_screen.dart';

/// Ponto de entrada de quem opera um carregamento sem credencial de
/// funcionário: o entregador digita o código do lote (recebido do
/// separador) e a senha própria dele, mais nome e contato para
/// identificação. `LogisticsApi.entrarNoCarregamento` faz
/// `POST /shipments/login`, sem header de autorização — ver o comentário
/// daquele método sobre por que esta tela usa um `http.Client()` simples em
/// vez do `appAuthClient` compartilhado.
class ShipmentLoginScreen extends StatefulWidget {
  const ShipmentLoginScreen({super.key});

  @override
  State<ShipmentLoginScreen> createState() => _ShipmentLoginScreenState();
}

class _ShipmentLoginScreenState extends State<ShipmentLoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _codigoController = TextEditingController();
  final _senhaController = TextEditingController();
  final _nomeController = TextEditingController();
  final _contatoController = TextEditingController();
  final _api = LogisticsApi(client: http.Client());

  bool _submitting = false;
  String? _erro;

  @override
  void dispose() {
    _codigoController.dispose();
    _senhaController.dispose();
    _nomeController.dispose();
    _contatoController.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    if (_submitting) return;
    if (!(_formKey.currentState?.validate() ?? false)) return;

    setState(() {
      _submitting = true;
      _erro = null;
    });
    try {
      final sessao = await _api.entrarNoCarregamento(
        codigo: _codigoController.text.trim(),
        senha: _senhaController.text,
        nome: _nomeController.text.trim(),
        contato: _contatoController.text.trim(),
      );
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => EntregadorFilaScreen(
            codigoCarregamento: sessao.codigo,
            origemRotulo: sessao.origemRotulo,
          ),
        ),
      );
    } on LogisticsException catch (e) {
      if (!mounted) return;
      setState(() => _erro = e.message);
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
          backgroundColor: Colors.transparent,
          elevation: 0,
          foregroundColor: AppColors.textPrimary,
          title: const Text('Código de carregamento'),
        ),
        body: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: _ShipmentLoginCard(
              formKey: _formKey,
              codigoController: _codigoController,
              senhaController: _senhaController,
              nomeController: _nomeController,
              contatoController: _contatoController,
              submitting: _submitting,
              erro: _erro,
              onSubmit: _handleLogin,
            ),
          ),
        ),
      ),
    );
  }
}

class _ShipmentLoginCard extends StatelessWidget {
  const _ShipmentLoginCard({
    required this.formKey,
    required this.codigoController,
    required this.senhaController,
    required this.nomeController,
    required this.contatoController,
    required this.submitting,
    required this.erro,
    required this.onSubmit,
  });

  final GlobalKey<FormState> formKey;
  final TextEditingController codigoController;
  final TextEditingController senhaController;
  final TextEditingController nomeController;
  final TextEditingController contatoController;
  final bool submitting;
  final String? erro;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.fromLTRB(24, 28, 24, 28),
      child: Form(
        key: formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _CampoCarregamento(
              label: 'Código do carregamento',
              controller: codigoController,
              maxLength: 12,
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Informe o código' : null,
            ),
            const SizedBox(height: 16),
            _CampoCarregamento(
              label: 'Senha do carregamento',
              controller: senhaController,
              maxLength: 128,
              obscureText: true,
              validator: (v) => (v == null || v.isEmpty) ? 'Informe a senha' : null,
            ),
            const SizedBox(height: 16),
            _CampoCarregamento(
              label: 'Seu nome',
              controller: nomeController,
              maxLength: 120,
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Informe seu nome' : null,
            ),
            const SizedBox(height: 16),
            _CampoCarregamento(
              label: 'Contato (telefone)',
              controller: contatoController,
              maxLength: 120,
              validator: (v) =>
                  (v == null || v.trim().isEmpty) ? 'Informe um contato' : null,
            ),
            if (erro != null) ...[
              const SizedBox(height: 14),
              _ErroBox(erro!),
            ],
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: submitting ? null : onSubmit,
              child: submitting
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: AppColors.white,
                      ),
                    )
                  : const Text('Entrar'),
            ),
          ],
        ),
      ),
    );
  }
}

class _CampoCarregamento extends StatelessWidget {
  const _CampoCarregamento({
    required this.label,
    required this.controller,
    required this.maxLength,
    required this.validator,
    this.obscureText = false,
  });

  final String label;
  final TextEditingController controller;
  final int maxLength;
  final bool obscureText;
  final String? Function(String?) validator;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: controller,
          obscureText: obscureText,
          maxLength: maxLength,
          validator: validator,
        ),
      ],
    );
  }
}

class _ErroBox extends StatelessWidget {
  const _ErroBox(this.mensagem);

  final String mensagem;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFDECEC),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: Colors.red, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              mensagem,
              style: const TextStyle(fontSize: 13, color: Colors.red),
            ),
          ),
        ],
      ),
    );
  }
}

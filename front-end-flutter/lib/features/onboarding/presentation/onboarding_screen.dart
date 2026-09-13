import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../tracker/data/tracker_api.dart';

/// Onboarding de estudo: o objetivo do aluno e a data em que ele quer
/// chegar lá. Um formulário só, e pulável.
///
/// Duas portas chegam aqui: o cadastro (logo depois de criar a conta) e o
/// item "Metas e objetivos" do perfil, que antes não levava a lugar nenhum.
/// Com objetivo já cadastrado a tela abre preenchida e salva com PUT.
///
/// Pular não grava nada: aluno sem objetivo é caso previsto, e a tela
/// inicial simplesmente não desenha o cartão de meta.
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key, this.api});

  final TrackerApi? api;

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  late final TrackerApi _api = widget.api ?? TrackerApi();
  final _tituloController = TextEditingController();

  // Sem valor por padrão: uma data pré-preenchida seria indistinguível de
  // uma data escolhida pelo aluno, e essa tela existe para acabar com
  // números que ninguém escolheu.
  DateTime? _dataAlvo;
  bool _carregando = true;
  bool _salvando = false;
  bool _edicao = false;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregarObjetivo();
  }

  @override
  void dispose() {
    _tituloController.dispose();
    super.dispose();
  }

  Future<void> _carregarObjetivo() async {
    try {
      final objetivo = await _api.fetchGoal();
      if (!mounted) return;
      if (objetivo != null) {
        _tituloController.text = objetivo.title;
        _dataAlvo = objetivo.targetDate;
        _edicao = true;
      }
    } on TrackerException {
      // Sem objetivo legível, a tela abre vazia — é o mesmo estado de quem
      // nunca preencheu, e insistir num erro aqui bloquearia o cadastro.
    }
    if (mounted) setState(() => _carregando = false);
  }

  Future<void> _escolherData() async {
    final hoje = DateTime.now();
    final atual = _dataAlvo;
    // O calendário precisa abrir em algum mês: sem data ainda, ou com uma
    // data que já passou, ele sugere hoje. Sugerir onde abrir não é o mesmo
    // que preencher o campo — o valor do campo continua vazio até o aluno
    // confirmar algo no picker.
    final inicial = (atual == null || atual.isBefore(hoje)) ? hoje : atual;
    final escolhida = await showDatePicker(
      context: context,
      initialDate: inicial,
      firstDate: hoje,
      lastDate: DateTime(hoje.year + 10),
    );
    if (escolhida != null && mounted) setState(() => _dataAlvo = escolhida);
  }

  Future<void> _salvar() async {
    final titulo = _tituloController.text.trim();
    if (titulo.isEmpty) {
      setState(() => _erro = 'Diga o que você quer conquistar');
      return;
    }
    final dataAlvo = _dataAlvo;
    if (dataAlvo == null) {
      setState(() => _erro = 'Escolha uma data-alvo');
      return;
    }
    setState(() {
      _salvando = true;
      _erro = null;
    });
    try {
      await _api.saveGoal(title: titulo, targetDate: dataAlvo, update: _edicao);
      if (!mounted) return;
      Navigator.pushReplacementNamed(
        context,
        '/home',
        arguments: ModalRoute.of(context)?.settings.arguments,
      );
    } on TrackerException catch (e) {
      if (!mounted) return;
      setState(() {
        _erro = e.message;
        _salvando = false;
      });
    }
  }

  // Repassa os argumentos com que esta tela foi aberta (ex.: o
  // `justRegistered` do cadastro) — quem chega aqui vindo do cadastro
  // precisa que a home ainda veja a flag depois do pulo/salvar, senão a
  // saudação de conta criada nunca aparece (decisão D16 do plano).
  void _pular() => Navigator.pushReplacementNamed(
    context,
    '/home',
    arguments: ModalRoute.of(context)?.settings.arguments,
  );

  @override
  Widget build(BuildContext context) {
    if (_carregando) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return Scaffold(
      backgroundColor: AppColors.white,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Qual é o seu objetivo?',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Ele guia o seu percurso de estudo até a data da prova.',
                style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
              ),
              const SizedBox(height: 24),
              _OnboardingForm(
                tituloController: _tituloController,
                dataAlvo: _dataAlvo,
                erro: _erro,
                onEscolherData: _escolherData,
              ),
              const SizedBox(height: 24),
              _OnboardingActions(
                edicao: _edicao,
                salvando: _salvando,
                onSalvar: _salvar,
                onPular: _pular,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Objetivo, data-alvo e o erro inline dos dois. Sem estado próprio: quem
/// decide o que aparece é a tela, este widget só desenha.
class _OnboardingForm extends StatelessWidget {
  const _OnboardingForm({
    required this.tituloController,
    required this.dataAlvo,
    required this.erro,
    required this.onEscolherData,
  });

  final TextEditingController tituloController;
  final DateTime? dataAlvo;
  final String? erro;
  final VoidCallback onEscolherData;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: tituloController,
          maxLength: 120,
          decoration: const InputDecoration(
            labelText: 'Objetivo',
            hintText: 'Ex.: Medicina pelo ENEM',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 8),
        InkWell(
          onTap: onEscolherData,
          child: InputDecorator(
            decoration: const InputDecoration(
              labelText: 'Data-alvo',
              border: OutlineInputBorder(),
            ),
            child: Text(
              // Sem data ainda, o campo mostra uma dica — igual ao hintText
              // do título — nunca um valor que o aluno não escolheu.
              dataAlvo == null ? 'Escolha a data da prova' : _formatarData(dataAlvo!),
              style: dataAlvo == null ? const TextStyle(color: AppColors.textSecondary) : null,
            ),
          ),
        ),
        if (erro != null) ...[
          const SizedBox(height: 12),
          Text(erro!, style: const TextStyle(color: Colors.red, fontSize: 13)),
        ],
      ],
    );
  }
}

/// O botão principal (Começar/Salvar conforme o modo) e o "Pular por
/// enquanto". Sem estado próprio, só reage ao que a tela manda.
class _OnboardingActions extends StatelessWidget {
  const _OnboardingActions({
    required this.edicao,
    required this.salvando,
    required this.onSalvar,
    required this.onPular,
  });

  final bool edicao;
  final bool salvando;
  final VoidCallback onSalvar;
  final VoidCallback onPular;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          width: double.infinity,
          child: ElevatedButton(
            onPressed: salvando ? null : onSalvar,
            child: Text(edicao ? 'Salvar' : 'Começar'),
          ),
        ),
        const SizedBox(height: 8),
        Center(
          child: TextButton(
            onPressed: salvando ? null : onPular,
            child: const Text('Pular por enquanto'),
          ),
        ),
      ],
    );
  }
}

String _formatarData(DateTime data) =>
    '${data.day.toString().padLeft(2, '0')}/'
    '${data.month.toString().padLeft(2, '0')}/'
    '${data.year}';

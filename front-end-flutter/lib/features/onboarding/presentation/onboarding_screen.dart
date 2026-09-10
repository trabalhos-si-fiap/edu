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

  DateTime _dataAlvo = DateTime.now().add(const Duration(days: 180));
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
    final escolhida = await showDatePicker(
      context: context,
      initialDate: _dataAlvo.isBefore(hoje) ? hoje : _dataAlvo,
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
    setState(() {
      _salvando = true;
      _erro = null;
    });
    try {
      await _api.saveGoal(title: titulo, targetDate: _dataAlvo, update: _edicao);
      if (!mounted) return;
      Navigator.pushReplacementNamed(context, '/home');
    } on TrackerException catch (e) {
      if (!mounted) return;
      setState(() {
        _erro = e.message;
        _salvando = false;
      });
    }
  }

  void _pular() => Navigator.pushReplacementNamed(context, '/home');

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
              TextField(
                controller: _tituloController,
                maxLength: 120,
                decoration: const InputDecoration(
                  labelText: 'Objetivo',
                  hintText: 'Ex.: Medicina na USP',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              InkWell(
                onTap: _escolherData,
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Data-alvo',
                    border: OutlineInputBorder(),
                  ),
                  child: Text(
                    '${_dataAlvo.day.toString().padLeft(2, '0')}/'
                    '${_dataAlvo.month.toString().padLeft(2, '0')}/'
                    '${_dataAlvo.year}',
                  ),
                ),
              ),
              if (_erro != null) ...[
                const SizedBox(height: 12),
                Text(_erro!, style: const TextStyle(color: Colors.red, fontSize: 13)),
              ],
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _salvando ? null : _salvar,
                  child: Text(_edicao ? 'Salvar' : 'Começar'),
                ),
              ),
              const SizedBox(height: 8),
              Center(
                child: TextButton(
                  onPressed: _salvando ? null : _pular,
                  child: const Text('Pular por enquanto'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

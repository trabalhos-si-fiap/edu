import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../components/nav_bar.dart';
import '../data/quiz_api.dart';
import '../domain/quiz_models.dart';
import 'report_screen.dart';

/// Argumentos esperados na rota `/questions` (ver `Navigator.pushNamed`
/// em `quiz_subjets_screen.dart`).
class QuizScreenArgs {
  const QuizScreenArgs({
    required this.materiaNome,
    required this.temaId,
    required this.temaNome,
  });

  final String materiaNome;
  final int temaId;
  final String temaNome;
}

/// Questionário de diagnóstico de um tema inteiro. Diferente da versão
/// anterior (mock local com `correctIndex`), aqui:
/// - As questões vêm de `GET /topics/{tema_id}/quiz`, sem gabarito.
/// - Não há feedback de certo/errado por questão — o backend só calcula
///   o resultado depois que TODAS as respostas são enviadas juntas via
///   `POST /diagnostic/answer` (o domínio é calculado por subtema, não
///   questão a questão).
class QuizScreen extends StatefulWidget {
  const QuizScreen({super.key});

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  final _api = QuizApi();
  late Future<List<QuestaoQuiz>> _questoesFuture;
  QuizScreenArgs? _args;

  int _currentQuestion = 0;
  final Map<int, String> _respostas = {}; // questaoId -> letra escolhida
  bool _enviando = false;
  late Stopwatch _stopwatch;

  @override
  void initState() {
    super.initState();
    _stopwatch = Stopwatch()..start();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Só carrega uma vez — didChangeDependencies pode rodar de novo em
    // situações que não envolvem uma nova navegação (ex: MediaQuery
    // mudando), e recarregar reiniciaria o questionário no meio da prova.
    if (_args == null) {
      final raw = ModalRoute.of(context)?.settings.arguments as Map?;
      _args = QuizScreenArgs(
        materiaNome: raw?['materiaNome'] as String? ?? 'Matéria',
        temaId: raw?['temaId'] as int? ?? 0,
        temaNome: raw?['temaNome'] as String? ?? 'Tema',
      );
      _questoesFuture = _api.fetchQuestoesDoTema(_args!.temaId);
    }
  }

  Future<void> _finalizar(List<QuestaoQuiz> questoes) async {
    setState(() => _enviando = true);
    try {
      final resultado = await _api.enviarDiagnostico(
        temaId: _args!.temaId,
        respostas: _respostas.entries
            .map((e) => RespostaItem(questaoId: e.key, alternativaEscolhida: e.value))
            .toList(),
      );
      _stopwatch.stop();
      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => ReportScreen(
            temaNome: _args!.temaNome,
            resultado: resultado,
            totalTime: _stopwatch.elapsed,
          ),
        ),
      );
    } on QuizApiException catch (e) {
      if (!mounted) return;
      setState(() => _enviando = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
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
            icon: const Icon(Icons.arrow_back, color: Colors.black),
            onPressed: () {
              showModalBottomSheet(
                context: context,
                shape: const RoundedRectangleBorder(
                  borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
                ),
                builder: (context) => const ExitQuizModal(),
              );
            },
          ),
        ),
        body: SafeArea(
          child: FutureBuilder<List<QuestaoQuiz>>(
            future: _questoesFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return Padding(
                  padding: const EdgeInsets.all(32),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.error_outline, size: 40, color: AppColors.textSecondary),
                      const SizedBox(height: 12),
                      Text(
                        'Não foi possível carregar o questionário.\n${snapshot.error}',
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: AppColors.textSecondary),
                      ),
                      const SizedBox(height: 16),
                      OutlinedButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Voltar'),
                      ),
                    ],
                  ),
                );
              }
              final questoes = snapshot.data ?? const [];
              if (questoes.isEmpty) {
                return const Center(
                  child: Text(
                    'Nenhuma questão disponível para este tema.',
                    style: TextStyle(color: AppColors.textSecondary),
                  ),
                );
              }
              return _buildQuestionario(questoes);
            },
          ),
        ),
        bottomNavigationBar: const NavBar(currentIndex: 1),
      ),
    );
  }

  Widget _buildQuestionario(List<QuestaoQuiz> questoes) {
    final totalQuestions = questoes.length;
    final progress = (_currentQuestion + 1) / totalQuestions;
    final atual = questoes[_currentQuestion];
    final letraSelecionada = _respostas[atual.id];
    final ehUltima = _currentQuestion == totalQuestions - 1;
    final respondeuTudo = _respostas.length == totalQuestions;

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _args!.materiaNome.toUpperCase(),
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppColors.purple,
            ),
          ),
          Text(
            _args!.temaNome,
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Questão ${_currentQuestion + 1}/$totalQuestions',
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 10,
              backgroundColor: const Color(0xFFE5E7EB),
              valueColor: const AlwaysStoppedAnimation<Color>(AppColors.purple),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            atual.enunciado,
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
            softWrap: true,
          ),
          const SizedBox(height: 20),
          Column(
            children: atual.alternativas.entries.map((entry) {
              final letra = entry.key;
              final texto = entry.value;
              final isSelected = letraSelecionada == letra;
              return GestureDetector(
                onTap: () => setState(() => _respostas[atual.id] = letra),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  margin: const EdgeInsets.symmetric(vertical: 8),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    color: isSelected
                        ? AppColors.purple.withValues(alpha: 0.2)
                        : Colors.white,
                    border: Border.all(
                      color: isSelected ? AppColors.purple : Colors.grey[300]!,
                      width: 2,
                    ),
                  ),
                  child: Row(
                    children: [
                      CircleAvatar(
                        backgroundColor: isSelected ? AppColors.purple : Colors.grey[300],
                        child: Text(letra, style: const TextStyle(color: Colors.white)),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(texto, style: const TextStyle(fontSize: 16), softWrap: true),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 30),
          Row(
            children: [
              Expanded(
                child: ElevatedButton(
                  onPressed: _currentQuestion > 0 && !_enviando
                      ? () => setState(() => _currentQuestion--)
                      : null,
                  child: const Text('Voltar'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton(
                  onPressed: _enviando
                      ? null
                      : letraSelecionada == null
                      ? null // precisa responder a questão atual pra avançar
                      : ehUltima
                      ? (respondeuTudo ? () => _finalizar(questoes) : null)
                      : () => setState(() => _currentQuestion++),
                  child: _enviando
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : Text(ehUltima ? 'Finalizar' : 'Avançar'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class ExitQuizModal extends StatelessWidget {
  const ExitQuizModal({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.warning, size: 48, color: Colors.red),
          const SizedBox(height: 12),
          const Text(
            'Tem certeza que deseja sair do questionário?',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w600,
              color: Colors.black,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              Expanded(
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.grey[300]),
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Não', style: TextStyle(color: Colors.black)),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
                  onPressed: () {
                    Navigator.pop(context);
                    Navigator.pushReplacementNamed(context, '/home');
                  },
                  child: const Text('Sim'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

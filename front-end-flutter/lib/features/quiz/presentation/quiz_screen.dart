import 'package:edu_ia/features/components/nav_bar.dart';
import 'package:edu_ia/features/quiz/presentation/report_screen.dart';
import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';

class QuizScreen extends StatefulWidget {
  const QuizScreen({super.key});

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  int _currentQuestion = 0;
  int? _selectedOption;
  int _correctAnswers = 0;
  late Stopwatch _stopwatch;

  // Mock de perguntas
  final List<Map<String, dynamic>> mockQuestions = [
    {
      "question": "Qual é a capital da França?",
      "options": ["Paris", "Londres", "Roma", "Berlim"],
      "correctIndex": 0,
    },
    {
      "question": "Qual é o resultado de 2 + 2?",
      "options": ["3", "4", "5", "6"],
      "correctIndex": 1,
    },
    {
      "question": "Quem formulou as Leis de Newton?",
      "options": ["Einstein", "Newton", "Galileu", "Tesla"],
      "correctIndex": 1,
    },
    {
      "question": "Qual é o maior planeta do Sistema Solar?",
      "options": ["Terra", "Marte", "Júpiter", "Saturno"],
      "correctIndex": 2,
    },
    {
      "question": "Qual é a fórmula da água?",
      "options": ["CO2", "H2O", "O2", "NaCl"],
      "correctIndex": 1,
    },
  ];

  @override
  void initState() {
    super.initState();
    _stopwatch = Stopwatch()..start();
  }

  @override
  Widget build(BuildContext context) {
    final args = ModalRoute.of(context)?.settings.arguments as Map<String, String>?;
    final subject = args?['subject']?.toUpperCase() ?? 'MATÉRIA';
    final topic = args?['topic'] ?? 'ASSUNTO';

    final totalQuestions = mockQuestions.length;
    final progress = (_currentQuestion + 1) / totalQuestions;
    final currentData = mockQuestions[_currentQuestion];
    final options = currentData["options"] as List<String>;

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
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Matéria e assunto
                Text(
                  subject,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: AppColors.purple,
                  ),
                ),
                Text(
                  topic,
                  style: const TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 12),

                // Progresso
                Text(
                  "Questão ${_currentQuestion + 1}/$totalQuestions",
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: LinearProgressIndicator(
                    value: progress,
                    minHeight: 10,
                    backgroundColor: const Color(0xFFE5E7EB),
                    valueColor: AlwaysStoppedAnimation<Color>(AppColors.purple),
                  ),
                ),
                const SizedBox(height: 24),

                // Enunciado
                Text(
                  currentData["question"],
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                  ),
                  softWrap: true,
                ),
                const SizedBox(height: 20),

                // Alternativas
                Column(
                  children: List.generate(options.length, (index) {
                    final isSelected = _selectedOption == index;
                    return GestureDetector(
                      onTap: () {
                        setState(() {
                          _selectedOption = index;
                          if (index == currentData["correctIndex"]) {
                            _correctAnswers++;
                          }
                        });
                      },
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 300),
                        margin: const EdgeInsets.symmetric(vertical: 8),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(12),
                          color: isSelected ? AppColors.purple.withOpacity(0.2) : Colors.white,
                          border: Border.all(
                            color: isSelected ? AppColors.purple : Colors.grey[300]!,
                            width: 2,
                          ),
                        ),
                        child: Row(
                          children: [
                            CircleAvatar(
                              backgroundColor: isSelected ? AppColors.purple : Colors.grey[300],
                              child: Text(
                                String.fromCharCode(65 + index),
                                style: const TextStyle(color: Colors.white),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                options[index],
                                style: const TextStyle(fontSize: 16),
                                softWrap: true,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  }),
                ),

                const SizedBox(height: 30),

                // Botões
                Row(
                  children: [
                    Expanded(
                      child: ElevatedButton(
                        onPressed: _currentQuestion > 0
                            ? () {
                                setState(() {
                                  _currentQuestion--;
                                  _selectedOption = null;
                                });
                              }
                            : null,
                        child: const Text("Voltar"),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () {
                          if (_currentQuestion < totalQuestions - 1) {
                            setState(() {
                              _currentQuestion++;
                              _selectedOption = null;
                            });
                          } else {
                            _stopwatch.stop();
                            Navigator.pushReplacement(
                              context,
                              MaterialPageRoute(
                                builder: (_) => ReportScreen(
                                  subject: subject,
                                  topic: topic,
                                  correctAnswers: _correctAnswers,
                                  totalQuestions: totalQuestions,
                                  totalTime: _stopwatch.elapsed,
                                ),
                              ),
                            );
                          }
                        },
                        child: const Text("Avançar"),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        bottomNavigationBar: const NavBar(currentIndex: 1),
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
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.grey[300],
                  ),
                  onPressed: () {
                    Navigator.pop(context);
                  },
                  child: const Text('Não', style: TextStyle(color: Colors.black)),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red,
                  ),
                  onPressed: () {
                    Navigator.pop(context);
                    Navigator.pushReplacementNamed(context, '/home');
                  },
                  child: const Text('Sim'),
                ),
              ),
            ],
          )
        ],
      ),
    );
  }
}
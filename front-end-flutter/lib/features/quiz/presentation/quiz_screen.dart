import 'package:estuda_app/features/components/nav_bar.dart';
import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';

class QuizScreen extends StatefulWidget {
  const QuizScreen({super.key});

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  int _currentTabIndex = 1;
  int _currentQuestion = 1;
  final int _totalQuestions = 5;
  int? _selectedOption;

  @override
  Widget build(BuildContext context) {
    final args = ModalRoute.of(context)?.settings.arguments as Map<String, String>?;
    final subject = args?['subject']?.toUpperCase() ?? '';
    final topic = args?['topic'] ?? '';

    double progress = _currentQuestion / _totalQuestions;
    final options = ["Opção 1", "Opção 2", "Opção 3", "Opção 4"];

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
                  "Questão $_currentQuestion/$_totalQuestions",
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

                // Enunciado adaptável
                Text(
                  "Enunciado - TESTE",
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                  ),
                  softWrap: true,
                ),
                const SizedBox(height: 20),

                // Alternativas adaptáveis (sem rolagem própria)
                Column(
                  children: List.generate(options.length, (index) {
                    final isSelected = _selectedOption == index;
                    return GestureDetector(
                      onTap: () {
                        setState(() {
                          _selectedOption = index;
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
                                String.fromCharCode(65 + index), // A, B, C, D
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

                const SizedBox(height: 30), // espaçamento antes dos botões

                // Botões adaptáveis
                Row(
                  children: [
                    Expanded(
                      child: ElevatedButton(
                        onPressed: _currentQuestion > 1
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
                          if (_currentQuestion < _totalQuestions) {
                            setState(() {
                              _currentQuestion++;
                              _selectedOption = null;
                            });
                          } else {
                            // chegou ao fim → vai para outra página
                            Navigator.pushReplacementNamed(context, '/results'); 
                            // você pode trocar '/results' pela rota que quiser
                          }
                        },
                        child: const Text("Avançar"),
                      ),
                    ),
                  ],
                )
              ],
            ),
          ),
        ),
        bottomNavigationBar: NavBar(
          currentIndex: _currentTabIndex,
          onTap: (index) {
            setState(() => _currentTabIndex = index);
            switch (index) {
              case 0:
                Navigator.pushReplacementNamed(context, '/home');
                break;
              case 1:
                Navigator.pushReplacementNamed(context, '/quiz');
                break;
              case 2:
                Navigator.pushReplacementNamed(context, '/study');
                break;
              case 3:
                Navigator.pushReplacementNamed(context, '/review');
                break;
              case 4:
                Navigator.pushReplacementNamed(context, '/status');
                break;
            }
          },
        ),
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
                    Navigator.pop(context); // fecha a modal
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
                    Navigator.pop(context); // fecha a modal
                    Navigator.pushReplacementNamed(context, '/home'); // vai para home
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

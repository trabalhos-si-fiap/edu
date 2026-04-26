import 'package:estuda_app/core/theme/app_colors.dart';
import 'package:estuda_app/features/components/nav_bar.dart';
import 'package:flutter/material.dart';

class ReportScreen extends StatefulWidget {
  final String subject;
  final String topic;
  final int correctAnswers;
  final int totalQuestions;
  final Duration totalTime;

  const ReportScreen({
    super.key,
    required this.subject,
    required this.topic,
    required this.correctAnswers,
    required this.totalQuestions,
    required this.totalTime,
  });

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  int _currentTabIndex = 1;

  @override
  Widget build(BuildContext context) {
    double scorePercent = widget.correctAnswers / widget.totalQuestions;

    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          title: Row(
            children: const [
              Icon(Icons.check_circle, color: AppColors.purple),
              SizedBox(width: 8),
              Text(
                "QUESTIONÁRIO CONCLUÍDO",
                style: TextStyle(
                  color: AppColors.purple,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                const SizedBox(height: 12),
                const Text(
                  "Excelente progresso, Amanda",
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  "Você completou o questionário sobre ${widget.subject} - ${widget.topic}. "
                  "Seus dados já foram analisados pela nossa IA.",
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 16),
                ),
                const SizedBox(height: 24),

                // Card de desempenho
                Card(
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      children: [
                        SizedBox(
                          height: 120,
                          width: 120,
                          child: CircularProgressIndicator(
                            value: scorePercent,
                            strokeWidth: 12,
                            color: AppColors.purple,
                            backgroundColor: Colors.grey[200],
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          "${widget.correctAnswers} / ${widget.totalQuestions}",
                          style: const TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          "Taxa de assertividade: ${(scorePercent * 100).toStringAsFixed(0)}%",
                          style: const TextStyle(fontSize: 16),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Card de tempo
                Card(
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  child: ListTile(
                    leading: const Icon(Icons.access_time, color: AppColors.purple),
                    title: Text("Tempo total levado: ${widget.totalTime.inMinutes} min"),
                  ),
                ),
                const SizedBox(height: 16),

                // Card de recomendações
                Card(
                  color: AppColors.purple,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: const [
                        Row(
                          children: [
                            Icon(Icons.lightbulb, color: Colors.white),
                            SizedBox(width: 8),
                            Text(
                              "Recomendações do Edu IA",
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        SizedBox(height: 16),
                        _RecommendationCard(
                          title: "Estudo: Teste Assunto",
                          description: "Reveja os conceitos básicos e exercícios práticos.",
                        ),
                        _RecommendationCard(
                          title: "Vídeo sugerido: Assunto",
                          description: "Assista ao vídeo explicativo para reforçar o conteúdo.",
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                // Botão finalizar
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.purple,
                    minimumSize: const Size(double.infinity, 48),
                  ),
                  onPressed: () {
                    Navigator.pushReplacementNamed(context, '/home');
                  },
                  child: const Text("Finalizar simulado"),
                ),
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

class _RecommendationCard extends StatelessWidget {
  final String title;
  final String description;

  const _RecommendationCard({required this.title, required this.description});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: const TextStyle(
                    fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(height: 4),
            Text(description, style: const TextStyle(fontSize: 14)),
          ],
        ),
      ),
    );
  }
}

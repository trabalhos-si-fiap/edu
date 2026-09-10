import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../domain/roadmap_step.dart';

import 'tracker_provider.dart';

/// A rota `/tracker`: cria o provider e dispara a carga.
class TrackerScreen extends StatelessWidget {
  const TrackerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => TrackerProvider()..load(),
      child: const TrackerView(),
    );
  }
}

/// O corpo da tela, sem criar dependência — é o que os testes montam.
class TrackerView extends StatelessWidget {
  const TrackerView({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<TrackerProvider>();

    return Scaffold(
      appBar: AppBar(title: const Text('Meu percurso')),
      body: switch (provider.state) {
        TrackerViewState.loading => const Center(child: CircularProgressIndicator()),
        TrackerViewState.error => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              provider.errorMessage ?? 'Algo deu errado. Tente novamente.',
              textAlign: TextAlign.center,
            ),
          ),
        ),
        TrackerViewState.success => _Conteudo(provider: provider),
      },
    );
  }
}

class _Conteudo extends StatelessWidget {
  const _Conteudo({required this.provider});

  final TrackerProvider provider;

  @override
  Widget build(BuildContext context) {
    final roadmap = provider.roadmap;
    if (roadmap == null || roadmap.steps.isEmpty) {
      // Sem objetivo, a lista vem vazia COM motivo — a tela repete a frase
      // do servidor e oferece o caminho, em vez de mostrar um vazio mudo.
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                roadmap?.reason ?? 'Seu percurso ainda está vazio.',
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 15, color: AppColors.textSecondary),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => Navigator.pushNamed(context, '/onboarding'),
                child: const Text('Definir objetivo'),
              ),
            ],
          ),
        ),
      );
    }

    final grupos = provider.stepsBySubject;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        if (roadmap.tightDeadline)
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: Text(
              'Seu prazo é apertado: várias etapas caem no mesmo dia.',
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
          ),
        for (final entrada in grupos.entries) ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(
              entrada.key,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: AppColors.textPrimary,
              ),
            ),
          ),
          for (final etapa in entrada.value) _EtapaCard(etapa: etapa),
        ],
      ],
    );
  }
}

class _EtapaCard extends StatelessWidget {
  const _EtapaCard({required this.etapa});

  final RoadmapStep etapa;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (etapa.done)
                  const Padding(
                    padding: EdgeInsets.only(right: 8),
                    child: Icon(Icons.check_circle, color: AppColors.purple, size: 20),
                  ),
                Expanded(
                  child: Text(
                    etapa.subtopicName,
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              '${etapa.topicName} · até '
              '${etapa.deadline.day.toString().padLeft(2, '0')}/'
              '${etapa.deadline.month.toString().padLeft(2, '0')}',
              style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            if (!etapa.hasQuestions) ...[
              const SizedBox(height: 8),
              // A etapa aparece mesmo sem questão, dizendo por quê. Esconder
              // a matéria faria o aluno acreditar num percurso menor do que
              // o real.
              const Text(
                'Conteúdo em preparação',
                style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
              ),
            ],
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: etapa.hasQuestions
                    ? () => Navigator.pushNamed(context, '/quiz')
                    : null,
                child: const Text('Praticar'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

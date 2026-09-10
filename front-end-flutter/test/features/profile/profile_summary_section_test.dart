import 'dart:async';

import 'package:edu_ia/features/profile/presentation/profile_screen.dart';
import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:edu_ia/features/tracker/presentation/summary_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeApi extends TrackerApi {
  _FakeApi({this.resumo, this.erro, this.completer});

  final StudySummary? resumo;
  final String? erro;

  /// Quando presente, `fetchSummary` nunca resolve sozinho — é o gancho
  /// que os testes usam pra travar o provider no estado `loading` e
  /// inspecionar a tela antes da resposta chegar.
  final Completer<StudySummary>? completer;

  @override
  Future<StudySummary> fetchSummary() async {
    if (completer != null) return completer!.future;
    if (erro != null) throw TrackerException(erro!);
    return resumo!;
  }
}

StudySummary _resumoComPontos(int total) => StudySummary.fromJson({
  'objetivo': null,
  'roadmap': {'etapas_totais': 0, 'etapas_concluidas': 0, 'progresso': 0.0},
  'pontos': {'total': total, 'nivel': 8, 'streak': 4},
  'estudo': {'questoes_respondidas': 15, 'subtemas_iniciados': 6},
});

Widget _harness(SummaryProvider provider) =>
    MaterialApp(home: Scaffold(body: ProfileSummarySection(provider: provider)));

void main() {
  testWidgets('enquanto carrega, mostra zero — não um valor de exemplo', (tester) async {
    final completer = Completer<StudySummary>();
    final provider = SummaryProvider(api: _FakeApi(completer: completer));
    unawaited(provider.load());

    await tester.pumpWidget(_harness(provider));
    await tester.pump();

    expect(provider.state, SummaryViewState.loading);
    expect(find.text('0'), findsWidgets);
    expect(find.text('3.120'), findsNothing);

    // Libera o completer pra não deixar future pendente ao fim do teste.
    completer.complete(_resumoComPontos(0));
    await tester.pumpAndSettle();
  });

  testWidgets('com sucesso, mostra os números do backend', (tester) async {
    final provider = SummaryProvider(api: _FakeApi(resumo: _resumoComPontos(3120)));
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pumpAndSettle();

    expect(find.text('3.120'), findsOneWidget);
    expect(find.textContaining('Nível 8'), findsOneWidget);
  });

  testWidgets('com erro, mostra a mensagem — não os zeros do estado vazio', (tester) async {
    final provider = SummaryProvider(
      api: _FakeApi(erro: 'Não foi possível conectar ao servidor'),
    );
    await provider.load();

    await tester.pumpWidget(_harness(provider));
    await tester.pumpAndSettle();

    expect(provider.state, SummaryViewState.error);
    expect(find.text('Não foi possível conectar ao servidor'), findsOneWidget);
    // Um aluno com pontos reais e uma falha de rede não pode ver a mesma
    // tela de quem nunca estudou: os cartões zerados não aparecem no erro.
    expect(find.text('Total de pontos'), findsNothing);
    expect(find.text('0'), findsNothing);
  });
}

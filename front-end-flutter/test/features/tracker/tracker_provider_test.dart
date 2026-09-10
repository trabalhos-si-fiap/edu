import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:edu_ia/features/tracker/domain/roadmap_step.dart';
import 'package:edu_ia/features/tracker/presentation/tracker_provider.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeApi extends TrackerApi {
  int? limitRecebido;

  @override
  Future<Roadmap> fetchRoadmap({int limit = 50, int offset = 0}) async {
    limitRecebido = limit;
    return const Roadmap(
      goal: null,
      reason: null,
      tightDeadline: false,
      steps: [],
      total: 0,
    );
  }
}

void main() {
  test('load pede o teto de 200, não o default de 50 do cliente', () async {
    // O seed do ENEM sozinho produz 99 subtemas, mais os 8 da Citologia —
    // 107 etapas por aluno. O default de 50 corta o percurso na metade;
    // 200 é o teto que `GET /roadmap` aceita (`le=200`) e cobre tudo numa
    // chamada só. Se o seed crescer além de 200 essa asserção não pega,
    // mas o corte de 50 nunca mais volta em silêncio.
    final api = _FakeApi();
    final provider = TrackerProvider(api: api);

    await provider.load();

    expect(api.limitRecebido, 200);
  });
}

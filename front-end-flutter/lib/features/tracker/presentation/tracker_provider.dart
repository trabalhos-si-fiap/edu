import 'package:flutter/foundation.dart';

import '../data/tracker_api.dart';
import '../domain/roadmap_step.dart';

enum TrackerViewState { loading, success, error }

/// Estado da tela de percurso: carrega `GET /roadmap` e agrupa as etapas
/// por matéria para a tela desenhar.
class TrackerProvider extends ChangeNotifier {
  TrackerProvider({TrackerApi? api}) : _api = api ?? TrackerApi();

  final TrackerApi _api;

  TrackerViewState _state = TrackerViewState.loading;
  Roadmap? _roadmap;
  String? _errorMessage;

  TrackerViewState get state => _state;
  Roadmap? get roadmap => _roadmap;
  String? get errorMessage => _errorMessage;

  /// Etapas agrupadas por matéria, preservando a ordem do percurso — a
  /// resposta já vem ordenada por `ordem`, então basta não reordenar.
  Map<String, List<RoadmapStep>> get stepsBySubject {
    final agrupado = <String, List<RoadmapStep>>{};
    for (final etapa in _roadmap?.steps ?? const <RoadmapStep>[]) {
      agrupado.putIfAbsent(etapa.subjectName, () => []).add(etapa);
    }
    return agrupado;
  }

  Future<void> load() async {
    _state = TrackerViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      _roadmap = await _api.fetchRoadmap();
      _state = TrackerViewState.success;
    } on TrackerException catch (e) {
      _errorMessage = e.message;
      _state = TrackerViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = TrackerViewState.error;
    }
    notifyListeners();
  }
}

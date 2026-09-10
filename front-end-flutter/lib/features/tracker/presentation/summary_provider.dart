import 'package:flutter/foundation.dart';

import '../data/tracker_api.dart';
import '../domain/study_summary.dart';

enum SummaryViewState { loading, success, error }

/// Estado do resumo de estudo, compartilhado pela tela inicial e pelo
/// perfil: as duas leem `GET /profile/summary`, e uma chamada só serve as
/// duas quando o aluno navega entre elas.
class SummaryProvider extends ChangeNotifier {
  SummaryProvider({TrackerApi? api}) : _api = api ?? TrackerApi();

  final TrackerApi _api;

  SummaryViewState _state = SummaryViewState.loading;
  StudySummary? _summary;
  String? _errorMessage;

  SummaryViewState get state => _state;
  StudySummary? get summary => _summary;
  String? get errorMessage => _errorMessage;

  Future<void> load() async {
    _state = SummaryViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      _summary = await _api.fetchSummary();
      _state = SummaryViewState.success;
    } on TrackerException catch (e) {
      _errorMessage = e.message;
      _state = SummaryViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = SummaryViewState.error;
    }
    notifyListeners();
  }
}

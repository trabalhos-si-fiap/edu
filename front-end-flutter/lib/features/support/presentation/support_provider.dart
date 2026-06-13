import 'package:flutter/foundation.dart';

import '../data/support_service.dart';
import '../domain/support_message.dart';

enum SupportViewState { loading, success, error }

/// Estado do chat de suporte: carrega o histórico e envia novas mensagens.
class SupportProvider extends ChangeNotifier {
  SupportProvider({SupportService? service})
    : _service = service ?? SupportService();

  final SupportService _service;

  SupportViewState _state = SupportViewState.loading;
  List<SupportMessage> _messages = const [];
  String? _errorMessage;
  bool _sending = false;

  SupportViewState get state => _state;
  List<SupportMessage> get messages => _messages;
  String? get errorMessage => _errorMessage;
  bool get sending => _sending;

  Future<void> load() async {
    _state = SupportViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _messages = await _service.fetchMessages();
      _state = SupportViewState.success;
    } on SupportException catch (e) {
      _errorMessage = e.message;
      _state = SupportViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = SupportViewState.error;
    }
    notifyListeners();
  }

  Future<void> send(String body) async {
    final text = body.trim();
    if (text.isEmpty || _sending) return;

    _sending = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _messages = await _service.sendMessage(text);
    } on SupportException catch (e) {
      _errorMessage = e.message;
    } catch (_) {
      _errorMessage = 'Não foi possível enviar a mensagem.';
    } finally {
      _sending = false;
      notifyListeners();
    }
  }
}

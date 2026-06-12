/// Helpers de formatação em PT-BR para a tela de rastreio. Sem dependência de
/// `intl` — o app não a usa — apenas mapeamentos pequenos e auto-contidos.
class OrderFormat {
  const OrderFormat._();

  static const List<String> _months = [
    'Jan',
    'Fev',
    'Mar',
    'Abr',
    'Mai',
    'Jun',
    'Jul',
    'Ago',
    'Set',
    'Out',
    'Nov',
    'Dez',
  ];

  /// "18 Out".
  static String dayMonth(DateTime date) {
    return '${date.day} ${_months[date.month - 1]}';
  }

  /// "12 Out, 09:45".
  static String dayMonthTime(DateTime date) {
    final h = date.hour.toString().padLeft(2, '0');
    final m = date.minute.toString().padLeft(2, '0');
    return '${dayMonth(date)}, $h:$m';
  }

  /// "há 12 min", "há 2 h", "há 3 dias". Relativo ao momento atual.
  static String relativeFromNow(DateTime date) {
    final diff = DateTime.now().difference(date);
    if (diff.inMinutes < 1) return 'agora mesmo';
    if (diff.inMinutes < 60) return 'há ${diff.inMinutes} min';
    if (diff.inHours < 24) return 'há ${diff.inHours} h';
    return 'há ${diff.inDays} ${diff.inDays == 1 ? 'dia' : 'dias'}';
  }
}

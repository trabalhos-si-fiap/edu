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

  /// "18 Out", no dia local (ver [_local]).
  static String dayMonth(DateTime date, {Duration? utcOffset}) {
    return _dayMonth(_local(date, utcOffset));
  }

  /// "12 Out, 09:45", no relógio local (ver [_local]).
  static String dayMonthTime(DateTime date, {Duration? utcOffset}) {
    final local = _local(date, utcOffset);
    final h = local.hour.toString().padLeft(2, '0');
    final m = local.minute.toString().padLeft(2, '0');
    return '${_dayMonth(local)}, $h:$m';
  }

  /// "há 12 min", "há 2 h", "há 3 dias". Relativo ao momento atual.
  static String relativeFromNow(DateTime date) {
    final diff = DateTime.now().difference(date);
    if (diff.inMinutes < 1) return 'agora mesmo';
    if (diff.inMinutes < 60) return 'há ${diff.inMinutes} min';
    if (diff.inHours < 24) return 'há ${diff.inHours} h';
    return 'há ${diff.inDays} ${diff.inDays == 1 ? 'dia' : 'dias'}';
  }

  /// Chegada estimada relativa ao dia: "hoje, ~14:48", "amanhã, ~09:05" ou
  /// "16 Jun, ~14:48". O "~" sinaliza que é uma estimativa. [now] é injetável
  /// para teste.
  static String estimatedArrivalLabel(
    DateTime arrival, {
    DateTime? now,
    Duration? utcOffset,
  }) {
    final ref = _local(now ?? DateTime.now(), utcOffset);
    final local = _local(arrival, utcOffset);
    final today = DateTime(ref.year, ref.month, ref.day);
    final arrivalDay = DateTime(local.year, local.month, local.day);
    final deltaDays = arrivalDay.difference(today).inDays;

    final h = local.hour.toString().padLeft(2, '0');
    final m = local.minute.toString().padLeft(2, '0');
    final time = '~$h:$m';

    if (deltaDays == 0) return 'hoje, $time';
    if (deltaDays == 1) return 'amanhã, $time';
    return '${_dayMonth(local)}, $time';
  }

  /// O instante no fuso de quem olha. O backend manda UTC (`...+00:00`), e
  /// ler `day`/`hour` direto dele mostrava "14 Set, 01:32" a quem viu 22:32
  /// do dia 13 em UTC-3. Sem [utcOffset] vale o fuso do aparelho (uma data
  /// já local passa intacta); com ele, o fuso é fixo — é o gancho dos testes,
  /// que não podem depender do fuso da máquina. O resultado só serve para
  /// ler os campos: não passe de volta por aqui.
  static DateTime _local(DateTime date, Duration? utcOffset) =>
      utcOffset == null ? date.toLocal() : date.toUtc().add(utcOffset);

  static String _dayMonth(DateTime local) {
    return '${local.day} ${_months[local.month - 1]}';
  }
}

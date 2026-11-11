class CalendarEvent {
  final DateTime date;
  final String institutionName;
  final String productName;
  final int installmentRound;

  /// '납입' | '만기'. 예전 서버 응답에는 없어서 회차 0 이면 만기로 본다.
  final String eventType;

  /// 납입이면 그 회차 납입액, 만기면 만기까지 넣은 원금 합계(원). 예전 응답에는 없다.
  final int? amount;

  const CalendarEvent({
    required this.date,
    required this.institutionName,
    required this.productName,
    required this.installmentRound,
    required this.eventType,
    this.amount,
  });

  bool get isMaturity => eventType == '만기';

  factory CalendarEvent.fromJson(Map<String, dynamic> json) {
    final round = json['installment_round'] as int;
    return CalendarEvent(
      date: DateTime.parse(json['date'] as String),
      institutionName: json['institution_name'] as String,
      productName: json['product_name'] as String,
      installmentRound: round,
      eventType: json['event_type'] as String? ?? (round == 0 ? '만기' : '납입'),
      amount: json['amount'] as int?,
    );
  }
}

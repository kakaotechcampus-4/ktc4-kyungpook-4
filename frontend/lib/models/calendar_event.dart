class CalendarEvent {
  final DateTime date;
  final String institutionName;
  final String productName;
  final int installmentRound;

  const CalendarEvent({
    required this.date,
    required this.institutionName,
    required this.productName,
    required this.installmentRound,
  });

  factory CalendarEvent.fromJson(Map<String, dynamic> json) {
    return CalendarEvent(
      date: DateTime.parse(json['date'] as String),
      institutionName: json['institution_name'] as String,
      productName: json['product_name'] as String,
      installmentRound: json['installment_round'] as int,
    );
  }
}

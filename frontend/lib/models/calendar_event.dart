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
}

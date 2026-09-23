import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/calendar_event.dart';

/// 다가오는 납입 일정. 아직 백엔드 API가 없어 임시 데이터를 쓴다 —
/// 실제 API가 생기면 이 provider를 FutureProvider로 바꾸면 된다.
final upcomingEventsProvider = Provider<List<CalendarEvent>>((ref) {
  final today = DateTime.now();
  return [
    CalendarEvent(
      date: DateTime(today.year, today.month, today.day + 6),
      institutionName: '국민은행',
      productName: 'OO적금 납입일',
      installmentRound: 3,
    ),
    CalendarEvent(
      date: DateTime(today.year, today.month, today.day + 8),
      institutionName: '새마을금고',
      productName: 'OO적금 납입일',
      installmentRound: 3,
    ),
  ];
});

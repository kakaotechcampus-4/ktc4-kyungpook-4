import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/calendar_event.dart';
import '../services/api_client.dart';
import 'portfolio_provider.dart';

/// 다가오는 납입·만기 일정. 서버가 지금 사용자의 진행중 안을 찾아 주므로 포트폴리오 번호를
/// 기억하지 않아도 된다 (새로고침·로그인 뒤에도 유지). 아직 확정한 안이 없으면 빈 목록이다.
final upcomingEventsProvider = FutureProvider.autoDispose<List<CalendarEvent>>((ref) async {
  // 방금 확정했으면 다시 불러오도록 지켜본다 (값 자체는 쓰지 않는다)
  ref.watch(selectedPortfolioIdProvider);
  return ApiClient.instance.getMyCalendar();
});

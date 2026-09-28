import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/calendar_event.dart';
import '../services/api_client.dart';
import 'portfolio_provider.dart';

/// 다가오는 납입·만기 일정. 아직 포트폴리오를 확정하지 않았으면 빈 목록이다.
final upcomingEventsProvider = FutureProvider.autoDispose<List<CalendarEvent>>((ref) async {
  final portfolioId = ref.watch(selectedPortfolioIdProvider);
  if (portfolioId == null) {
    return const [];
  }
  return ApiClient.instance.getCalendar(portfolioId);
});

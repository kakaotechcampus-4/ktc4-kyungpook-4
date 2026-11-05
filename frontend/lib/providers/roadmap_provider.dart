import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/roadmap_stats.dart';
import '../services/api_client.dart';

/// 로드맵 숫자. 이 브라우저에서 만든 기록이 없으면(로그인·게스트 쿠키 둘 다 없음) null.
final roadmapProvider = FutureProvider.autoDispose<RoadmapStats?>((ref) {
  return ApiClient.instance.fetchRoadmap();
});

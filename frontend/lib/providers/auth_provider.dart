import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/current_user.dart';
import '../services/auth_client.dart';

/// 현재 로그인한 사용자. 로그인 안 되어 있으면 null (게스트 상태와는 다름 -
/// 서버가 401을 주는, 세션 쿠키 자체가 없는 상태).
final currentUserProvider = FutureProvider<CurrentUser?>((ref) {
  return AuthClient.instance.fetchCurrentUser();
});

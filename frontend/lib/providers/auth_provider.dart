import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/current_user.dart';
import '../services/auth_client.dart';

/// 현재 로그인한 사용자. 로그인 안 되어 있으면 null (게스트 상태와는 다름 -
/// 서버가 401을 주는, 세션 쿠키 자체가 없는 상태).
final currentUserProvider = FutureProvider<CurrentUser?>((ref) {
  return AuthClient.instance.fetchCurrentUser();
});

/// 화면에 "OO님"처럼 보여줄 사용자 이름. 로그인 안 했거나(게스트) 닉네임이
/// 없으면 'OO'로 대체한다.
final userDisplayNameProvider = Provider<String>((ref) {
  final nickname = ref.watch(currentUserProvider).value?.nickname;
  return nickname != null && nickname.isNotEmpty ? nickname : 'OO';
});

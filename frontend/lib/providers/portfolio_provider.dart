import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';
import '../models/portfolio_option.dart';
import '../models/single_plan.dart';
import '../services/api_client.dart';

class RecommendationResult {
  final int profileId;
  final List<PortfolioOption> options;
  final SinglePlan? baseline;

  const RecommendationResult({required this.profileId, required this.options, this.baseline});
}

/// STEP1~3 답변으로 만든 profile_id. 로딩 화면에서 한 번만 생성해서 여기 저장해두고,
/// 결과 화면·챗봇 질문·재추천이 전부 이 값을 계속 쓴다 (매번 새 프로필을 만들면
/// 챗봇이 쌓아온 '기타' 조건 답변과 다른 프로필을 보게 된다).
final currentProfileIdProvider = StateProvider<int?>((ref) => null);

/// 저장된 profile_id로 안정형/단순형/균형형/최대형 4안을 추천받는다.
final recommendationProvider = FutureProvider.autoDispose<RecommendationResult>(
  (ref) async {
    final profileId = ref.watch(currentProfileIdProvider);
    if (profileId == null) {
      throw StateError('프로필이 아직 생성되지 않았습니다');
    }
    final (options, baseline) = await ApiClient.instance.recommendPortfolios(profileId);
    return RecommendationResult(profileId: profileId, options: options, baseline: baseline);
  },
);

/// 4안의 AI 추천 이유. recommendationProvider는 숫자만 빠르게 받아오고, 이유는
/// 이 provider가 따로(느리게) 채운다 - 화면이 숫자 먼저 그리고 이유는 나중에 채워 넣게 하기 위함.
final portfolioReasonsProvider = FutureProvider.autoDispose<Map<String, String>>(
  (ref) async {
    final profileId = ref.watch(currentProfileIdProvider);
    if (profileId == null) {
      throw StateError('프로필이 아직 생성되지 않았습니다');
    }
    return ApiClient.instance.fetchPortfolioReasons(profileId);
  },
);

/// 사용자가 확정 가입한 포트폴리오. 캘린더 화면이 이 값으로 일정을 조회한다.
final selectedPortfolioIdProvider = StateProvider<int?>((ref) => null);

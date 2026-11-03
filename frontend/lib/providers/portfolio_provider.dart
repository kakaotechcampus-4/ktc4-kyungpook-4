import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';
import '../models/portfolio_option.dart';
import '../services/api_client.dart';
import 'onboarding_provider.dart';

class RecommendationResult {
  final int profileId;
  final List<PortfolioOption> options;

  const RecommendationResult({required this.profileId, required this.options});
}

/// STEP1 입력값으로 프로필을 만들고 안정형/단순형/균형형/최대형 4안을 추천받는다.
final recommendationProvider = FutureProvider.autoDispose<RecommendationResult>(
  (ref) async {
    final input = ref.watch(onboardingProvider);
    final client = ApiClient.instance;

    final profileId = await client.createProfile(input);
    final options = await client.recommendPortfolios(profileId);
    return RecommendationResult(profileId: profileId, options: options);
  },
);

/// 사용자가 확정 가입한 포트폴리오. 캘린더 화면이 이 값으로 일정을 조회한다.
final selectedPortfolioIdProvider = StateProvider<int?>((ref) => null);

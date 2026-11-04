import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/portfolio_option.dart';
import '../models/single_plan.dart';
import 'portfolio_provider.dart';

/// 주거래은행 단일 상품 비교 기준. 백엔드 추천 응답의 baseline 필드에서 가져온다.
/// 주거래은행을 입력하지 않았거나 해당 은행 상품이 없으면 null.
final singlePlanProvider = Provider<SinglePlan?>((ref) {
  return ref.watch(recommendationProvider).whenOrNull(data: (r) => r.baseline);
});

/// 지금 펼쳐서 보고 있는 포트폴리오 카드. 기본값은 균형형이고,
/// 펼쳐진 카드를 다시 탭하면(위 화살표) null이 되어 전부 접힌다.
class SelectedTierNotifier extends Notifier<PortfolioTier?> {
  @override
  PortfolioTier? build() => PortfolioTier.balanced;

  void toggle(PortfolioTier tier) {
    state = state == tier ? null : tier;
  }
}

final selectedTierProvider =
    NotifierProvider<SelectedTierNotifier, PortfolioTier?>(
  SelectedTierNotifier.new,
);

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/portfolio_option.dart';
import '../models/single_plan.dart';

/// 주거래은행 단일 상품 비교 기준. 아직 백엔드 계산 API가 없어 임시 데이터를 쓴다.
final singlePlanProvider = Provider<SinglePlan>((ref) {
  return const SinglePlan(
    institutionName: 'KB국민은행',
    productName: 'KB내맘대로적금',
    monthlyAmount: 100000,
    termMonths: 12,
    annualRatePercent: 15.4,
    afterTaxInterest: 240565,
  );
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

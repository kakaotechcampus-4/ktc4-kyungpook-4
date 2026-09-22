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

/// 모아가 선정한 세 가지 포트폴리오. 아직 백엔드 계산 API가 없어 임시 데이터를 쓴다.
final portfolioOptionsProvider = Provider<List<PortfolioOption>>((ref) {
  return [
    const PortfolioOption(
      tier: PortfolioTier.simple,
      vsSingleDiff: 82000,
      newAccountCount: 1,
      branchVisitCount: 0,
      reason: '가장 손이 덜 가는 방법이에요. 신규 계좌 없이 지금 쓰는 은행 앱에서 금리가 더 높은 '
          '상품 하나로만 갈아타는 방식이라, 번거로움 없이 단일안보다 이자를 더 받을 수 있어요.',
      products: [
        PortfolioProduct(
          institutionName: '카카오뱅크',
          productName: '자유적금',
          termMonths: 12,
          interestRate: 4.2,
          afterTaxInterest: 322000,
          amountDescription: '월 10만원 · 연 4.20%',
          conditionDescription: '앱 가입만으로 적용 [확인됨]',
          detailUrl: 'https://www.kakaobank.com',
        ),
      ],
    ),
    const PortfolioOption(
      tier: PortfolioTier.balanced,
      vsSingleDiff: 587000,
      newAccountCount: 2,
      branchVisitCount: 1,
      reason: '신협 비과세 3,000만원 한도를 먼저 채우고, 나머지는 급여이체 우대가 붙는 국민은행 적금에 '
          '넣는 게 세후로 가장 유리했어요.',
      products: [
        PortfolioProduct(
          institutionName: 'OO신협',
          productName: '정기예탁금 12개월',
          termMonths: 12,
          interestRate: 3.40,
          afterTaxInterest: 675000,
          amountDescription: '2,000만원 · 연 3.40% · 비과세',
          conditionDescription: '만기 2027-09-15 [확인됨]',
          detailUrl: 'https://www.cu.co.kr',
        ),
        PortfolioProduct(
          institutionName: '국민은행',
          productName: '정기적금 36개월',
          termMonths: 36,
          interestRate: 3.30,
          afterTaxInterest: 1640000,
          amountDescription: '월 100만원 · 연 3.30%',
          conditionDescription: '급여이체 우대 적용 [확인됨]',
          detailUrl: 'https://www.kbstar.com',
        ),
      ],
    ),
    const PortfolioOption(
      tier: PortfolioTier.max,
      vsSingleDiff: 912000,
      newAccountCount: 3,
      branchVisitCount: 2,
      reason: '비과세·우대금리 한도를 모두 끌어모은 조합이에요. 계좌 개설과 지점 방문이 더 필요하지만, '
          '세후 이자는 세 가지 중 가장 많아요.',
      products: [
        PortfolioProduct(
          institutionName: 'OO신협',
          productName: '정기예탁금 12개월',
          termMonths: 12,
          interestRate: 3.40,
          afterTaxInterest: 675000,
          amountDescription: '2,000만원 · 연 3.40% · 비과세',
          conditionDescription: '만기 2027-09-15 [확인됨]',
          detailUrl: 'https://www.cu.co.kr',
        ),
        PortfolioProduct(
          institutionName: '새마을금고',
          productName: '정기적금 24개월',
          termMonths: 24,
          interestRate: 3.85,
          afterTaxInterest: 520000,
          amountDescription: '월 50만원 · 연 3.85% · 비과세',
          conditionDescription: '출자금 가입 필요 [확인됨]',
          detailUrl: 'https://www.kfcc.co.kr',
        ),
        PortfolioProduct(
          institutionName: '국민은행',
          productName: '정기적금 24개월',
          termMonths: 24,
          interestRate: 3.30,
          afterTaxInterest: 305000,
          amountDescription: '월 50만원 · 연 3.30%',
          conditionDescription: '급여이체 우대 적용 [확인됨]',
          detailUrl: 'https://www.kbstar.com',
        ),
      ],
    ),
  ];
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

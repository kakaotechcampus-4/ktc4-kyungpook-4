import '../utils/currency_formatter.dart';

/// MOCK: 백엔드 API(`/portfolios/recommend`)가 아직 내려주지 않는 필드를 채운다.
///
/// 대상: [PortfolioProduct]의 amountDescription/conditionDescription/detailUrl,
/// [PortfolioOption]의 vsSingleDiff/newAccountCount/branchVisitCount.
/// 백엔드 스키마([backend/app/schemas/portfolio.py])에 이 필드들이 추가되면
/// 이 파일을 지우고 `portfolio_option.dart`의 fromJson에서 실제 값을 매핑하면 된다.
class PortfolioFieldMocks {
  PortfolioFieldMocks._();

  static String productAmountDescription({
    required int allocatedAmount,
    required double interestRate,
  }) {
    return '${CurrencyFormatter.won(allocatedAmount)} · 연 $interestRate%';
  }

  static String productConditionDescription() => '우대조건 확인 필요 (API 연동 전 Mock)';

  static String productDetailUrl({
    required String institutionName,
    required String productName,
  }) {
    final query = Uri.encodeComponent('$institutionName $productName');
    return 'https://www.google.com/search?q=$query';
  }

  static int optionVsSingleDiff() => 0;

  static int optionNewAccountCount(int productCount) => productCount;

  static int optionBranchVisitCount() => 0;
}

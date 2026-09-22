enum PortfolioTier { simple, balanced, max }

extension PortfolioTierLabel on PortfolioTier {
  String get label => switch (this) {
        PortfolioTier.simple => '단순형',
        PortfolioTier.balanced => '균형형',
        PortfolioTier.max => '최대형',
      };
}

class PortfolioProduct {
  final String institutionName;
  final String productName;
  final int termMonths;
  final double interestRate;
  final int afterTaxInterest;

  /// "2,000만원 · 연 3.40% · 비과세" 처럼, 금액/한도 조건을 설명하는 줄.
  final String amountDescription;

  /// "만기 2027-09-15 [확인됨]" 처럼, 확인된 우대조건/만기를 설명하는 줄.
  final String conditionDescription;

  /// 상품 공식 안내 페이지 링크.
  final String detailUrl;

  const PortfolioProduct({
    required this.institutionName,
    required this.productName,
    required this.termMonths,
    required this.interestRate,
    required this.afterTaxInterest,
    required this.amountDescription,
    required this.conditionDescription,
    required this.detailUrl,
  });
}

class PortfolioOption {
  final PortfolioTier tier;
  final List<PortfolioProduct> products;
  final String reason;

  /// 단일안(주거래은행 단일 상품) 대비 세후 이자 차액.
  final int vsSingleDiff;
  final int newAccountCount;
  final int branchVisitCount;

  const PortfolioOption({
    required this.tier,
    required this.products,
    required this.reason,
    required this.vsSingleDiff,
    required this.newAccountCount,
    required this.branchVisitCount,
  });
}

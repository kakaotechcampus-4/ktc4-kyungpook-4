enum PortfolioTier { simple, balanced, max }

extension PortfolioTierLabel on PortfolioTier {
  /// 백엔드 API 가 쓰는 한글 tier 값. (POST /portfolios 의 tier 파라미터 등)
  String get apiValue => switch (this) {
        PortfolioTier.simple => '단순형',
        PortfolioTier.balanced => '균형형',
        PortfolioTier.max => '최대형',
      };

  static PortfolioTier fromApiValue(String value) => switch (value) {
        '단순형' => PortfolioTier.simple,
        '균형형' => PortfolioTier.balanced,
        '최대형' => PortfolioTier.max,
        _ => throw FormatException('알 수 없는 포트폴리오 tier: $value'),
      };
}

class PortfolioProduct {
  final String institutionName;
  final String productName;
  final int termMonths;
  final double interestRate;
  final int allocatedAmount;
  final int afterTaxInterest;

  const PortfolioProduct({
    required this.institutionName,
    required this.productName,
    required this.termMonths,
    required this.interestRate,
    required this.allocatedAmount,
    required this.afterTaxInterest,
  });

  factory PortfolioProduct.fromJson(Map<String, dynamic> json) {
    return PortfolioProduct(
      institutionName: json['institution_name'] as String,
      productName: json['product_name'] as String,
      termMonths: json['term_months'] as int,
      interestRate: (json['interest_rate'] as num).toDouble(),
      allocatedAmount: json['allocated_amount'] as int,
      afterTaxInterest: json['after_tax_interest'] as int,
    );
  }
}

class PortfolioOption {
  final PortfolioTier tier;
  final List<PortfolioProduct> products;
  final int afterTaxTotal;
  final String reason;

  const PortfolioOption({
    required this.tier,
    required this.products,
    required this.afterTaxTotal,
    required this.reason,
  });

  factory PortfolioOption.fromJson(Map<String, dynamic> json) {
    return PortfolioOption(
      tier: PortfolioTierLabel.fromApiValue(json['tier'] as String),
      products: (json['products'] as List<dynamic>)
          .map((p) => PortfolioProduct.fromJson(p as Map<String, dynamic>))
          .toList(),
      afterTaxTotal: json['after_tax_total'] as int,
      reason: json['reason'] as String,
    );
  }
}

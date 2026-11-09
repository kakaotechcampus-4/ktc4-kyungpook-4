/// "단일형"이 어떤 기준인지 한 줄 설명. 포트폴리오 tier 설명들과 나란히 보여준다.
const singlePlanDescription = '주거래은행 상품 하나에 전액을 몰아넣었을 때예요';

/// 주거래은행 단일 상품에 전액을 넣었을 때의 비교 기준값.
class SinglePlan {
  final String institutionName;
  final String productName;

  /// 예금 | 적금. allocatedAmount 가 원금인지 월 납입액인지 이걸로 구분한다.
  final String productType;
  final int allocatedAmount;
  final int termMonths;
  final double annualRatePercent;
  final int afterTaxInterest;
  final String? periodNote;

  const SinglePlan({
    required this.institutionName,
    required this.productName,
    required this.productType,
    required this.allocatedAmount,
    required this.termMonths,
    required this.annualRatePercent,
    required this.afterTaxInterest,
    this.periodNote,
  });

  factory SinglePlan.fromJson(Map<String, dynamic> json) {
    final products = (json['products'] as List<dynamic>? ?? [])
        .cast<Map<String, dynamic>>();
    final first = products.isNotEmpty ? products.first : null;
    return SinglePlan(
      institutionName: json['institution_name'] as String? ?? '',
      productName: json['product_name'] as String? ?? '',
      productType: json['product_type'] as String? ?? '예금',
      allocatedAmount: (first?['allocated_amount'] as num?)?.toInt() ?? 0,
      termMonths: (first?['term_months'] as num?)?.toInt() ?? 0,
      annualRatePercent: (first?['interest_rate'] as num?)?.toDouble() ?? 0.0,
      afterTaxInterest: (json['after_tax_total'] as num?)?.toInt() ?? 0,
      periodNote: json['period_note'] as String?,
    );
  }
}

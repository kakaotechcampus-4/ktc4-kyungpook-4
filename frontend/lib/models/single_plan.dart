/// 주거래은행 단일 상품에 전액을 넣었을 때의 비교 기준값.
class SinglePlan {
  final String institutionName;
  final String productName;
  final int monthlyAmount;
  final int termMonths;
  final double annualRatePercent;
  final int afterTaxInterest;
  final String? periodNote;

  const SinglePlan({
    required this.institutionName,
    required this.productName,
    required this.monthlyAmount,
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
      monthlyAmount: (first?['allocated_amount'] as num?)?.toInt() ?? 0,
      termMonths: (first?['term_months'] as num?)?.toInt() ?? 0,
      annualRatePercent: (first?['interest_rate'] as num?)?.toDouble() ?? 0.0,
      afterTaxInterest: (json['after_tax_total'] as num?)?.toInt() ?? 0,
      periodNote: json['period_note'] as String?,
    );
  }
}

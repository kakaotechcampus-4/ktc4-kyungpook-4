/// 주거래은행 단일 상품에 전액을 넣었을 때의 비교 기준값.
class SinglePlan {
  final String institutionName;
  final String productName;
  final int monthlyAmount;
  final int termMonths;
  final double annualRatePercent;
  final int afterTaxInterest;

  const SinglePlan({
    required this.institutionName,
    required this.productName,
    required this.monthlyAmount,
    required this.termMonths,
    required this.annualRatePercent,
    required this.afterTaxInterest,
  });
}

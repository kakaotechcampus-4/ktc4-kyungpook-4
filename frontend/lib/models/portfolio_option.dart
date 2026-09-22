enum PortfolioTier { simple, balanced, max }

class PortfolioProduct {
  final String institutionName;
  final String productName;
  final int termMonths;
  final double interestRate;
  final int afterTaxInterest;

  const PortfolioProduct({
    required this.institutionName,
    required this.productName,
    required this.termMonths,
    required this.interestRate,
    required this.afterTaxInterest,
  });
}

class PortfolioOption {
  final PortfolioTier tier;
  final List<PortfolioProduct> products;
  final String reason;

  const PortfolioOption({
    required this.tier,
    required this.products,
    required this.reason,
  });
}

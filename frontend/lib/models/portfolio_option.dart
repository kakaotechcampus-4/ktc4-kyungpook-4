import '../services/portfolio_field_mocks.dart';

enum PortfolioTier { simple, balanced, max }

extension PortfolioTierLabel on PortfolioTier {
  String get label => switch (this) {
        PortfolioTier.simple => '단순형',
        PortfolioTier.balanced => '균형형',
        PortfolioTier.max => '최대형',
      };

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
    required this.allocatedAmount,
    required this.afterTaxInterest,
    required this.amountDescription,
    required this.conditionDescription,
    required this.detailUrl,
  });

  // 백엔드 응답에 amountDescription/conditionDescription/detailUrl 이 아직 없어
  // PortfolioFieldMocks 로 채운다 (백엔드 스키마에 필드가 추가되면 그 파일을
  // 지우고 여기서 실제 값을 매핑하면 된다).
  factory PortfolioProduct.fromJson(Map<String, dynamic> json) {
    final institutionName = json['institution_name'] as String;
    final productName = json['product_name'] as String;
    final allocatedAmount = json['allocated_amount'] as int;
    final interestRate = (json['interest_rate'] as num).toDouble();
    return PortfolioProduct(
      institutionName: institutionName,
      productName: productName,
      termMonths: json['term_months'] as int,
      interestRate: interestRate,
      allocatedAmount: allocatedAmount,
      afterTaxInterest: json['after_tax_interest'] as int,
      amountDescription: PortfolioFieldMocks.productAmountDescription(
        allocatedAmount: allocatedAmount,
        interestRate: interestRate,
      ),
      conditionDescription: PortfolioFieldMocks.productConditionDescription(),
      detailUrl: PortfolioFieldMocks.productDetailUrl(
        institutionName: institutionName,
        productName: productName,
      ),
    );
  }
}

class PortfolioOption {
  final PortfolioTier tier;
  final List<PortfolioProduct> products;
  final int afterTaxTotal;
  final String reason;

  /// 단일안(주거래은행 단일 상품) 대비 세후 이자 차액.
  final int vsSingleDiff;
  final int newAccountCount;
  final int branchVisitCount;

  const PortfolioOption({
    required this.tier,
    required this.products,
    required this.afterTaxTotal,
    required this.reason,
    required this.vsSingleDiff,
    required this.newAccountCount,
    required this.branchVisitCount,
  });

  // 백엔드 응답에 vsSingleDiff/newAccountCount/branchVisitCount 가 아직 없어
  // PortfolioFieldMocks 로 채운다 (위 fromJson과 동일한 이유).
  factory PortfolioOption.fromJson(Map<String, dynamic> json) {
    final products = (json['products'] as List<dynamic>)
        .map((p) => PortfolioProduct.fromJson(p as Map<String, dynamic>))
        .toList();
    return PortfolioOption(
      tier: PortfolioTierLabel.fromApiValue(json['tier'] as String),
      products: products,
      afterTaxTotal: json['after_tax_total'] as int,
      reason: json['reason'] as String,
      vsSingleDiff: PortfolioFieldMocks.optionVsSingleDiff(),
      newAccountCount: PortfolioFieldMocks.optionNewAccountCount(products.length),
      branchVisitCount: PortfolioFieldMocks.optionBranchVisitCount(),
    );
  }
}

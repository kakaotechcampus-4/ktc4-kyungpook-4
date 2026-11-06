import '../services/portfolio_field_mocks.dart';

enum PortfolioTier { stable, simple, balanced, max }

extension PortfolioTierLabel on PortfolioTier {
  String get label => switch (this) {
        PortfolioTier.stable => '안정형',
        PortfolioTier.simple => '단순형',
        PortfolioTier.balanced => '균형형',
        PortfolioTier.max => '최대형',
      };

  /// 이 안이 어떤 기준으로 만들어졌는지 한 줄로 설명. 사용자가 포트폴리오별
  /// 차이를 이해할 수 있게 결과 화면에 보여준다.
  String get description => switch (this) {
        PortfolioTier.stable => '1금융권 상품만으로 구성했어요 (신규 가입 등 다른 조건은 고려하지 않아요)',
        PortfolioTier.simple => '지금 이미 충족한 조건만으로 받을 수 있는 최대 실수령액이에요',
        PortfolioTier.balanced => '새 은행 가입·자동이체 등록처럼 약간의 행동 변화로 받을 수 있는 최대 실수령액이에요',
        PortfolioTier.max => '카드 실적 채우기, 보험 가입 등 모든 우대조건을 달성했다고 가정한 최대 실수령액이에요',
      };

  /// 백엔드 API 가 쓰는 한글 tier 값. (POST /portfolios 의 tier 파라미터 등)
  String get apiValue => switch (this) {
        PortfolioTier.stable => '안정형',
        PortfolioTier.simple => '단순형',
        PortfolioTier.balanced => '균형형',
        PortfolioTier.max => '최대형',
      };

  static PortfolioTier fromApiValue(String value) => switch (value) {
        '안정형' => PortfolioTier.stable,
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

  /// AI가 쓴 추천 이유. recommend 를 with_reason=false 로 부르면 null로 오고,
  /// /portfolios/reasons 로 따로 받아와야 한다 (숫자 먼저 보여주기 위함).
  final String? reason;

  /// 단일안(주거래은행 단일 상품) 대비 세후 이자 차액. 주거래은행을 몰라 단일안을
  /// 계산할 수 없으면(baseline 이 null) 이것도 null.
  final int? extraVsBaseline;
  final int newAccountCount;
  final int branchVisitCount;

  const PortfolioOption({
    required this.tier,
    required this.products,
    required this.afterTaxTotal,
    required this.reason,
    required this.extraVsBaseline,
    required this.newAccountCount,
    required this.branchVisitCount,
  });

  // 백엔드 응답에 newAccountCount/branchVisitCount 가 아직 없어 PortfolioFieldMocks 로
  // 채운다 (위 fromJson과 동일한 이유).
  factory PortfolioOption.fromJson(Map<String, dynamic> json) {
    final products = (json['products'] as List<dynamic>)
        .map((p) => PortfolioProduct.fromJson(p as Map<String, dynamic>))
        .toList();
    return PortfolioOption(
      tier: PortfolioTierLabel.fromApiValue(json['tier'] as String),
      products: products,
      afterTaxTotal: json['after_tax_total'] as int,
      reason: json['reason'] as String?,
      extraVsBaseline: (json['extra_vs_baseline'] as num?)?.toInt(),
      newAccountCount: PortfolioFieldMocks.optionNewAccountCount(products.length),
      branchVisitCount: PortfolioFieldMocks.optionBranchVisitCount(),
    );
  }
}

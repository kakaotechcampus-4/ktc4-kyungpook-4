import '../utils/currency_formatter.dart';

enum PortfolioTier { stable, simple, balanced, max }

extension PortfolioTierLabel on PortfolioTier {
  String get label => switch (this) {
        PortfolioTier.stable => '안정형',
        PortfolioTier.simple => '단순형',
        PortfolioTier.balanced => '균형형',
        PortfolioTier.max => '최대형',
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

  /// 예금 | 적금. allocatedAmount 가 원금인지 월 납입액인지 이걸로 구분한다.
  final String productType;
  final int termMonths;
  final double interestRate;
  final int allocatedAmount;
  final int afterTaxInterest;

  /// "1,000,000원 예치 · 연 3.4%" / "월 500,000원 납입 · 연 4.9%" 처럼,
  /// productType 에 따라 원금/월 납입액 여부를 구분해 보여주는 줄.
  final String amountDescription;

  /// applied_conditions 를 사람이 읽을 문장으로 조합한 줄 (우대조건이 없으면 안내 문구).
  final String conditionDescription;

  const PortfolioProduct({
    required this.institutionName,
    required this.productName,
    required this.productType,
    required this.termMonths,
    required this.interestRate,
    required this.allocatedAmount,
    required this.afterTaxInterest,
    required this.amountDescription,
    required this.conditionDescription,
  });

  factory PortfolioProduct.fromJson(Map<String, dynamic> json) {
    final productType = json['product_type'] as String;
    final allocatedAmount = json['allocated_amount'] as int;
    final interestRate = (json['interest_rate'] as num).toDouble();
    final amountLabel = productType == '적금'
        ? '월 ${CurrencyFormatter.won(allocatedAmount)} 납입'
        : '${CurrencyFormatter.won(allocatedAmount)} 예치';
    return PortfolioProduct(
      institutionName: json['institution_name'] as String,
      productName: json['product_name'] as String,
      productType: productType,
      termMonths: json['term_months'] as int,
      interestRate: interestRate,
      allocatedAmount: allocatedAmount,
      afterTaxInterest: json['after_tax_interest'] as int,
      amountDescription: '$amountLabel · 연 $interestRate%',
      conditionDescription: _conditionDescription(
        json['applied_conditions'] as List<dynamic>,
      ),
    );
  }

  static String _conditionDescription(List<dynamic> appliedConditions) {
    if (appliedConditions.isEmpty) return '적용된 우대조건 없음';
    return appliedConditions.map((raw) {
      final condition = raw as Map<String, dynamic>;
      final thresholdValue = condition['threshold_value'] as int?;
      final thresholdUnit = condition['threshold_unit'] as String?;
      final threshold = thresholdValue != null ? '$thresholdValue$thresholdUnit 이상 ' : '';
      final status = (condition['already_met'] as bool) ? '충족' : '미충족';
      return '${condition['condition_type']} $threshold'
          '+${condition['bonus_rate']}%p ($status)';
    }).join(', ');
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

  /// 이 안을 실행하려면 새로 가입해야 하는 기관 수 (상품 개수가 아니라 기관 기준 중복 제거된 값).
  final int newAccountCount;

  const PortfolioOption({
    required this.tier,
    required this.products,
    required this.afterTaxTotal,
    required this.reason,
    required this.extraVsBaseline,
    required this.newAccountCount,
  });

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
      newAccountCount: json['new_bank_count'] as int,
    );
  }
}

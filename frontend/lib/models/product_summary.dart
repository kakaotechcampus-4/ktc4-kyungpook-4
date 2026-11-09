/// `GET /api/v1/products?institution=...&product_type=...` 응답 한 건.
/// 신협·새마을금고는 지점(branch)을 같이 보내야 product_id·금리가 온다.
/// 지점 없이 조회하면 이름으로 묶여 null로 온다.
class ProductSummary {
  final String? productId;
  final String productName;
  final String productType;
  final bool onSale;
  final List<int> periods;
  final double? baseRate;
  final double? maxRate;

  const ProductSummary({
    this.productId,
    required this.productName,
    required this.productType,
    required this.onSale,
    required this.periods,
    this.baseRate,
    this.maxRate,
  });

  factory ProductSummary.fromJson(Map<String, dynamic> json) {
    return ProductSummary(
      productId: json['product_id'] as String?,
      productName: json['product_name'] as String,
      productType: json['product_type'] as String,
      onSale: json['on_sale'] as bool,
      periods: (json['periods'] as List<dynamic>).map((e) => e as int).toList(),
      baseRate: (json['base_rate'] as num?)?.toDouble(),
      maxRate: (json['max_rate'] as num?)?.toDouble(),
    );
  }
}

/// 특정 기관·상품유형으로 검색한 결과 전체.
class ProductSearchResult {
  final String institution;
  final bool groupedByName;
  final List<ProductSummary> items;

  const ProductSearchResult({
    required this.institution,
    required this.groupedByName,
    required this.items,
  });

  factory ProductSearchResult.fromJson(Map<String, dynamic> json) {
    return ProductSearchResult(
      institution: json['institution'] as String,
      groupedByName: json['grouped_by_name'] as bool,
      items: (json['items'] as List<dynamic>)
          .map((e) => ProductSummary.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

/// `GET /api/v1/products/branches?institution=새마을금고` 응답 한 건.
/// [label]은 "가창새마을금고 본점 (대구 달성군)"처럼 지역이 붙어 있어
/// 그대로 보여주고 검색하면 된다.
class BranchSummary {
  final String institutionCode;
  final String label;

  const BranchSummary({required this.institutionCode, required this.label});

  factory BranchSummary.fromJson(Map<String, dynamic> json) {
    return BranchSummary(
      institutionCode: json['institution_code'] as String,
      label: json['label'] as String,
    );
  }
}

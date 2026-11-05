/// 사용자가 캘린더에서 날짜를 눌러 직접 기록한 상품 정보 한 건.
/// `/api/v1/manual-entries` 응답(및 생성 요청) 모양과 1:1로 맞춘다.
class ManualProductEntry {
  final int entryId;
  final DateTime date;
  final String institutionName;
  final String? productId;
  final String productName;
  final int amount;
  final String memo;
  final DateTime createdAt;

  const ManualProductEntry({
    required this.entryId,
    required this.date,
    required this.institutionName,
    this.productId,
    required this.productName,
    required this.amount,
    this.memo = '',
    required this.createdAt,
  });

  factory ManualProductEntry.fromJson(Map<String, dynamic> json) {
    return ManualProductEntry(
      entryId: json['entry_id'] as int,
      date: DateTime.parse(json['entry_date'] as String),
      institutionName: json['institution_name'] as String,
      productId: json['product_id'] as String?,
      productName: json['product_name'] as String,
      amount: json['amount'] as int,
      memo: json['memo'] as String? ?? '',
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

/// 사용자가 캘린더에서 날짜를 눌러 직접 기록한 상품 정보 한 건.
///
/// 백엔드에 수동 등록용 API가 아직 없어 지금은 로컬 상태로만 보관한다
/// (manual_entry_provider.dart 참고). API가 생기면 이 모델을 요청 바디로
/// 직렬화하는 역할만 추가하면 된다.
class ManualProductEntry {
  final String id;
  final DateTime date;
  final String institutionName;
  final String productName;
  final int amount;
  final String memo;

  const ManualProductEntry({
    required this.id,
    required this.date,
    required this.institutionName,
    required this.productName,
    required this.amount,
    this.memo = '',
  });
}

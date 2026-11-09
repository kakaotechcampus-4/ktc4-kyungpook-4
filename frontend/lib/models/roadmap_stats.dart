/// 로드맵 숫자 (GET /users/me/roadmap). 이자는 모두 세후(원).
class RoadmapStats {
  final DateTime startedAt;
  final int elapsedMonths;

  /// 지금까지 고른 모든 안에서 오늘까지 번 이자 (만기·그만둔 안 포함)
  final int totalInterest;

  /// 지금 진행중인 안의 만기 전 상품에서 오늘까지 쌓인 이자
  final int currentInterest;

  /// 지금 진행중인 안에 오늘까지 넣은 원금
  final int currentPrincipal;

  /// 진행 중 안의 누적액(원금+이자, 만기 상품 포함). 목표 경로의 현재 위치는 이걸 쓴다
  /// (current_* 는 만기된 상품이 빠져서 만기 시점에 줄어들기 때문).
  final int activeTotal;

  /// 목표 금액(목돈 + 월저축 x 기간). null 이면 서버가 계산할 근거(진행중인 안)가 없다는
  /// 뜻이라 사용자가 직접 입력해야 한다.
  final int? goalAmount;
  final DateTime? goalDate;
  final int? activePortfolioId;

  const RoadmapStats({
    required this.startedAt,
    required this.elapsedMonths,
    required this.totalInterest,
    required this.currentInterest,
    required this.currentPrincipal,
    required this.activeTotal,
    required this.goalAmount,
    required this.goalDate,
    required this.activePortfolioId,
  });

  factory RoadmapStats.fromJson(Map<String, dynamic> json) {
    return RoadmapStats(
      startedAt: DateTime.parse(json['started_at'] as String),
      elapsedMonths: json['elapsed_months'] as int,
      totalInterest: json['total_interest'] as int,
      currentInterest: json['current_interest'] as int,
      currentPrincipal: json['current_principal'] as int,
      activeTotal: json['active_total'] as int,
      goalAmount: json['goal_amount'] as int?,
      goalDate: json['goal_date'] == null
          ? null
          : DateTime.parse(json['goal_date'] as String),
      activePortfolioId: json['active_portfolio_id'] as int?,
    );
  }
}

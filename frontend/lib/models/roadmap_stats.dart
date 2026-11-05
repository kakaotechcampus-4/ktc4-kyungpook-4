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
  final int? activePortfolioId;

  const RoadmapStats({
    required this.startedAt,
    required this.elapsedMonths,
    required this.totalInterest,
    required this.currentInterest,
    required this.currentPrincipal,
    required this.activePortfolioId,
  });

  factory RoadmapStats.fromJson(Map<String, dynamic> json) {
    return RoadmapStats(
      startedAt: DateTime.parse(json['started_at'] as String),
      elapsedMonths: json['elapsed_months'] as int,
      totalInterest: json['total_interest'] as int,
      currentInterest: json['current_interest'] as int,
      currentPrincipal: json['current_principal'] as int,
      activePortfolioId: json['active_portfolio_id'] as int?,
    );
  }
}

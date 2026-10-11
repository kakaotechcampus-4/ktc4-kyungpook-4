import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/onboarding_input.dart';
import '../../providers/onboarding_provider.dart';
import '../../theme/app_colors.dart';
import '../../utils/app_images.dart';
import '../../utils/currency_formatter.dart';
import '../../widgets/next_step_button.dart';

/// 목표 금액까지 원금+이자가 쌓여가는 과정을 토스뱅크 만보기 스타일의
/// 구불구불한 경로로 보여주는 화면.
///
/// 실제 가입 상품의 금리·가입일을 아직 추적하지 않아서, 금리는 임시
/// 가정값을 쓰고 "지금 몇 개월째인지"는 +/- 로 직접 조절하는 데모 형태로
/// 우선 구현했다. 나중에 실제 포트폴리오 데이터와 연결하면 된다.
class RoadmapScreen extends ConsumerStatefulWidget {
  const RoadmapScreen({super.key});

  @override
  ConsumerState<RoadmapScreen> createState() => _RoadmapScreenState();
}

class _RoadmapScreenState extends ConsumerState<RoadmapScreen> {
  /// 데모용 평균 금리. 실제 가입 상품의 금리 데이터가 연결되면 이 값 대신
  /// 그 상품의 금리를 써야 한다.
  static const _demoAnnualRate = 0.035;

  final _goalController = TextEditingController();
  int _goalAmountWon = 0;
  int _elapsedMonths = 1;

  @override
  void dispose() {
    _goalController.dispose();
    super.dispose();
  }

  void _setGoal() {
    final digits = _goalController.text.replaceAll(',', '');
    final value = int.tryParse(digits);
    if (value == null || value <= 0) return;
    setState(() => _goalAmountWon = value);
    FocusScope.of(context).unfocus();
  }

  @override
  Widget build(BuildContext context) {
    final input = ref.watch(onboardingProvider);
    final periodMonths = input.periodMonths;
    _elapsedMonths = _elapsedMonths.clamp(0, periodMonths == 0 ? 0 : periodMonths);

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          '목표까지 가는 길',
          style: TextStyle(color: Colors.black87, fontWeight: FontWeight.bold),
        ),
        iconTheme: const IconThemeData(color: Colors.black87),
        actions: _goalAmountWon == 0
            ? null
            : [
                TextButton(
                  onPressed: () => setState(() => _goalAmountWon = 0),
                  child: const Text('목표 다시 설정'),
                ),
              ],
      ),
      body: SafeArea(
        top: false,
        child: _goalAmountWon == 0 ? _buildGoalInput() : _buildRoadmap(input),
      ),
    );
  }

  Widget _buildGoalInput() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Image.asset(AppImages.mainpageMascot, width: 96),
            const SizedBox(height: 20),
            const Text(
              '목표 금액을 알려주세요',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              '목표까지 얼마나 모아가고 있는지\n경로로 보여드릴게요.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 13, color: Colors.grey.shade500, height: 1.5),
            ),
            const SizedBox(height: 28),
            TextField(
              controller: _goalController,
              keyboardType: TextInputType.number,
              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              onSubmitted: (_) => _setGoal(),
              decoration: InputDecoration(
                hintText: '0',
                suffixText: '원',
                filled: true,
                fillColor: AppColors.background,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(16),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
            const SizedBox(height: 20),
            NextStepButton(label: '설정하기', enabled: true, onPressed: _setGoal),
          ],
        ),
      ),
    );
  }

  Widget _buildRoadmap(OnboardingInput input) {
    final monthlySavingWon = input.monthlySaving * 1000;
    final lumpSumWon = input.lumpSum * 1000;
    final periodMonths = input.periodMonths;
    const monthlyRate = _demoAnnualRate / 12;

    int principalAt(int months) => lumpSumWon + monthlySavingWon * months;

    double interestUpTo(int months) {
      var runningPrincipal = lumpSumWon;
      var interest = 0.0;
      for (var m = 1; m <= months; m++) {
        runningPrincipal += monthlySavingWon;
        interest += runningPrincipal * monthlyRate;
      }
      return interest;
    }

    final principalSoFar = principalAt(_elapsedMonths);
    final interestSoFar = interestUpTo(_elapsedMonths);
    final totalSoFar = principalSoFar + interestSoFar.round();

    final totalInterestAtMaturity = interestUpTo(periodMonths);
    final diffRounded = (totalInterestAtMaturity - interestSoFar).round();
    // 음수 방지용 하한만 필요해서 단순 비교로 처리한다.
    // (web에서는 int가 JS number로 표현되어 `1 << 62` 같은 큰 시프트가
    // 깨지므로, clamp(0, 아주 큰 수) 패턴은 피한다.)
    final remainingInterest = diffRounded < 0 ? 0 : diffRounded;

    return Column(
      children: [
        Expanded(
          child: _RoadmapPath(goalAmountWon: _goalAmountWon, currentAmountWon: totalSoFar),
        ),
        _buildStatsPanel(
          totalSoFar: totalSoFar,
          remainingInterest: remainingInterest,
          periodMonths: periodMonths,
        ),
      ],
    );
  }

  Widget _buildStatsPanel({
    required int totalSoFar,
    required int remainingInterest,
    required int periodMonths,
  }) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 16),
        ],
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _StatColumn(
                icon: Icons.calendar_today_outlined,
                label: '경과 개월',
                value: '$_elapsedMonths개월',
              ),
              _StatColumn(
                icon: Icons.savings_outlined,
                label: '모은 원금+이자',
                value: CurrencyFormatter.won(totalSoFar),
              ),
              _StatColumn(
                icon: Icons.trending_up,
                label: '만기까지 이자',
                value: CurrencyFormatter.won(remainingInterest),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (periodMonths == 0)
            Text(
              '1단계에서 저축 조건을 먼저 입력하면 더 정확하게 보여드려요.',
              style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
              textAlign: TextAlign.center,
            )
          else
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  '데모: 경과 개월 조정',
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
                ),
                IconButton(
                  onPressed: _elapsedMonths <= 0
                      ? null
                      : () => setState(() => _elapsedMonths--),
                  icon: const Icon(Icons.remove_circle_outline, size: 20),
                ),
                IconButton(
                  onPressed: _elapsedMonths >= periodMonths
                      ? null
                      : () => setState(() => _elapsedMonths++),
                  icon: const Icon(Icons.add_circle_outline, size: 20),
                ),
              ],
            ),
        ],
      ),
    );
  }
}

class _StatColumn extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _StatColumn({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(icon, color: AppColors.labelPurple, size: 22),
        const SizedBox(height: 6),
        Text(label, style: TextStyle(fontSize: 12, color: Colors.grey.shade500)),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
        ),
      ],
    );
  }
}

/// 목표 금액을 100%로 두고 20% 단위 구간마다 체크포인트를 띄우는
/// 구불구불한 경로. 아바타는 현재 누적액 비율에 맞춰 경로 위에 보간되어
/// 올라간다.
class _RoadmapPath extends StatelessWidget {
  static const _fractions = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0];
  static const _anchors = [
    Offset(0.5, 0.92),
    Offset(0.62, 0.74),
    Offset(0.22, 0.58),
    Offset(0.70, 0.40),
    Offset(0.26, 0.22),
    Offset(0.58, 0.06),
  ];

  final int goalAmountWon;
  final int currentAmountWon;

  const _RoadmapPath({required this.goalAmountWon, required this.currentAmountWon});

  @override
  Widget build(BuildContext context) {
    final progress =
        goalAmountWon == 0 ? 0.0 : (currentAmountWon / goalAmountWon).clamp(0.0, 1.0);

    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [AppColors.skyLavender, AppColors.lavender, AppColors.accent],
        ),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final size = Size(constraints.maxWidth, constraints.maxHeight);
          final points = _anchors.map((a) => Offset(a.dx * size.width, a.dy * size.height)).toList();
          final avatarPoint = _pointAtProgress(points, progress);
          final nextMilestoneIndex = _fractions.indexWhere((f) => f > progress);
          final nextMilestoneAmount = nextMilestoneIndex == -1
              ? goalAmountWon
              : (goalAmountWon * _fractions[nextMilestoneIndex]).round();
          final rawRemainingToNext = nextMilestoneAmount - currentAmountWon;
          final remainingToNext = rawRemainingToNext < 0 ? 0 : rawRemainingToNext;

          return Stack(
            children: [
              CustomPaint(size: size, painter: _PathPainter(points)),
              for (var i = 1; i < points.length; i++)
                _buildMilestoneBubble(points[i], goalAmountWon * _fractions[i]),
              Positioned(
                left: avatarPoint.dx - 22,
                top: avatarPoint.dy - 44,
                child: _buildNextBubble(remainingToNext),
              ),
              Positioned(
                left: avatarPoint.dx - 22,
                top: avatarPoint.dy - 22,
                child: _buildAvatar(),
              ),
            ],
          );
        },
      ),
    );
  }

  Offset _pointAtProgress(List<Offset> points, double progress) {
    for (var i = 0; i < _fractions.length - 1; i++) {
      final start = _fractions[i];
      final end = _fractions[i + 1];
      if (progress >= start && progress <= end) {
        final localT = end == start ? 0.0 : (progress - start) / (end - start);
        return Offset.lerp(points[i], points[i + 1], localT)!;
      }
    }
    return points.last;
  }

  Widget _buildMilestoneBubble(Offset point, num amount) {
    return Positioned(
      left: point.dx - 55,
      top: point.dy - 16,
      child: _Bubble(text: '목표 ${CurrencyFormatter.won(amount.round())}'),
    );
  }

  Widget _buildNextBubble(int remainingToNext) {
    return _Bubble(text: '다음 구간까지\n${CurrencyFormatter.won(remainingToNext)}');
  }

  Widget _buildAvatar() {
    return Container(
      width: 44,
      height: 44,
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: Colors.white,
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.2), blurRadius: 6)],
      ),
      child: ClipOval(child: Image.asset(AppImages.mainpageMascot, fit: BoxFit.cover)),
    );
  }
}

class _Bubble extends StatelessWidget {
  final String text;

  const _Bubble({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 140),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.1), blurRadius: 6)],
      ),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.black87),
      ),
    );
  }
}

class _PathPainter extends CustomPainter {
  final List<Offset> points;

  _PathPainter(this.points);

  @override
  void paint(Canvas canvas, Size size) {
    if (points.length < 2) return;
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;

    final path = Path()..moveTo(points.first.dx, points.first.dy);
    for (var i = 1; i < points.length; i++) {
      final prev = points[i - 1];
      final curr = points[i];
      final control = Offset((prev.dx + curr.dx) / 2, (prev.dy + curr.dy) / 2);
      path.quadraticBezierTo(prev.dx, prev.dy, control.dx, control.dy);
    }
    path.lineTo(points.last.dx, points.last.dy);
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _PathPainter oldDelegate) => oldDelegate.points != points;
}

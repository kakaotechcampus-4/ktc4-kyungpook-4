import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/portfolio_option.dart';
import '../../models/single_plan.dart';
import '../../providers/auth_provider.dart';
import '../../providers/portfolio_provider.dart';
import '../../providers/result_provider.dart';
import '../../router/app_router.dart';
import '../../theme/app_colors.dart';
import '../../utils/app_images.dart';
import '../../widgets/portfolio_tier_card.dart';
import '../../widgets/primary_button.dart';
import '../../widgets/secondary_button.dart';
import '../../widgets/single_plan_card.dart';

class ResultScreen extends ConsumerWidget {
  const ResultScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final singlePlan = ref.watch(singlePlanProvider);
    final selectedTier = ref.watch(selectedTierProvider);
    final recommendation = ref.watch(recommendationProvider);
    // 추천 이유(약 26초)는 autoDispose 라, 카드에서만 지켜보면 카드가 스크롤로 화면 밖에 나가거나
    // 선택이 꺼질 때 진행 중인 요청을 버리고 다시 보일 때 처음부터 새로 요청한다.
    // 결과 화면이 열려 있는 동안 요청을 붙잡아 두고, 들어오자마자 미리 받아오게 여기서도 지켜본다.
    ref.watch(portfolioReasonsProvider);

    return Scaffold(
      body: SafeArea(
        child: recommendation.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) =>
              Center(child: Text('추천을 불러오지 못했습니다: $error')),
          data: (result) => _ResultList(
            options: result.options,
            singlePlan: singlePlan,
            selectedTier: selectedTier,
          ),
        ),
      ),
    );
  }
}

class _ResultList extends ConsumerWidget {
  final List<PortfolioOption> options;
  final SinglePlan? singlePlan;
  final PortfolioTier? selectedTier;

  const _ResultList({
    required this.options,
    required this.singlePlan,
    required this.selectedTier,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final name = ref.watch(userDisplayNameProvider);
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 32, 20, 24),
      children: [
        // ↓↓↓ 화면 구간 사이 세로 간격은 이 SizedBox 들의 height 값만
        // 바꾸면 조절된다 (숫자가 클수록 스크롤이 길어짐).
        _IntroSection(name: name),
        const SizedBox(height: 300),
        if (singlePlan != null) ...[
          Text(
            '$name님의 주거래은행인 ${singlePlan!.institutionName}의\n단일안 적용 상품과 비교해볼게요',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 15, height: 1.5, color: Colors.black87),
          ),
          const SizedBox(height: 50),
          SinglePlanCard(plan: singlePlan!),
        ] else
          const Text(
            '주거래은행 정보가 없어 단일안 비교를 표시할 수 없어요',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 15, height: 1.5, color: Colors.black54),
          ),
        const SizedBox(height: 100),
        const _PortfolioIntroText(),
        const SizedBox(height: 50),
        // ↑↑↑ 여기까지
        if (options.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Text('조건에 맞는 상품을 찾지 못했습니다', textAlign: TextAlign.center),
          )
        else
          for (final option in options)
            PortfolioTierCard(
              option: option,
              isSelected: option.tier == selectedTier,
              onTap: () =>
                  ref.read(selectedTierProvider.notifier).toggle(option.tier),
            ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              flex: 2,
              child: SecondaryButton(
                label: '정보를 수정하고\n다시 계산할래요.',
                onPressed: () => context.go(AppRoutes.inputStep1),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              flex: 3,
              child: PrimaryButton(
                label: '이 포트폴리오로\n결정할래요.',
                onPressed: () {
                  if (selectedTier == null) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('먼저 포트폴리오를 선택해주세요.')),
                    );
                    return;
                  }
                  context.push(AppRoutes.resultDetail);
                },
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _IntroSection extends StatelessWidget {
  final String name;

  const _IntroSection({required this.name});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const SizedBox(height: 50),
        Text(
          '$name님을 위한',
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 16, color: Colors.black87),
        ),
        const SizedBox(height: 4),
        const Text(
          '맞춤형 포트폴리오가 생성되었어요!',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 120),
        Image.asset(AppImages.mainpageMascot, width: 120),
        const SizedBox(height: 120),
        const Text(
          '확인하러 가볼까요?',
          style: TextStyle(fontSize: 14, color: Colors.black54),
        ),
        // 스크롤 유도 문구 전 여백 — 여기도 늘리면 인트로 구간이 더 길어진다.
        const SizedBox(height: 200),
        const Text(
          '아래로 스크롤해주세요',
          style: TextStyle(fontSize: 13, color: AppColors.gray),
        ),
        const SizedBox(height: 4),
        const Icon(Icons.keyboard_arrow_down, color: AppColors.gray),
      ],
    );
  }
}

class _PortfolioIntroText extends StatelessWidget {
  const _PortfolioIntroText();

  @override
  Widget build(BuildContext context) {
    return RichText(
      textAlign: TextAlign.center,
      text: const TextSpan(
        style: TextStyle(fontSize: 16, height: 1.5, color: Colors.black87),
        children: [
          TextSpan(text: '이번에는 '),
          TextSpan(
            text: '모아가 선정해온',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          TextSpan(text: '\n'),
          TextSpan(
            text: '네 가지 포트폴리오',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          TextSpan(text: '를 보여드릴게요!'),
        ],
      ),
    );
  }
}

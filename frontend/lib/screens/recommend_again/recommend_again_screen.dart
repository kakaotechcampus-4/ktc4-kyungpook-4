import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers/onboarding_provider.dart';
import '../../providers/result_provider.dart';
import '../../router/app_router.dart';
import '../../utils/app_images.dart';
import '../../widgets/primary_button.dart';

/// 이미 확정한 포트폴리오가 있는 사용자가 캘린더에서 다시 추천을 받으려 할 때 보여준다.
/// 처음 사용자용 튜토리얼 대신 짧게 안내하고, 버튼을 누르면 STEP1부터 새로 입력받는다.
class RecommendAgainScreen extends ConsumerWidget {
  const RecommendAgainScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(backgroundColor: Colors.white, elevation: 0),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(32, 0, 32, 32),
          child: Column(
            children: [
              const Spacer(flex: 2),
              const Text(
                '새로운 포트폴리오를 작성하시고 싶으신가요?\n모아와 함께 출발해봐요!',
                style: TextStyle(fontSize: 17, height: 1.6, fontWeight: FontWeight.w600),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 40),
              Image.asset(AppImages.mainpageMascot, width: 180),
              const Spacer(flex: 3),
              PrimaryButton(
                label: '추천받기',
                onPressed: () {
                  // 지난번 답변·선택한 안이 남아 있지 않게 비우고 STEP1부터 다시 받는다
                  ref.invalidate(onboardingProvider);
                  ref.invalidate(selectedTierProvider);
                  context.push(AppRoutes.inputStep1);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

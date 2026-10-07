import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../router/app_router.dart';
import '../../utils/app_images.dart';
import '../../widgets/primary_button.dart';

const _messageStyle = TextStyle(
  fontSize: 15,
  height: 1.6,
  color: Colors.black87,
);
const _emphasisStyle = TextStyle(
  fontSize: 15,
  height: 1.6,
  fontWeight: FontWeight.bold,
  color: Colors.black,
);

/// 처음 앱을 켠 사용자에게 "모아"(안내 캐릭터)가 서비스를 소개하는
/// 온보딩. 위에서 아래로 쭉 스크롤하면서 읽고, 맨 아래
/// "조건 응답하러 가기"를 누르면 입력 1단계로 이동한다.
class TutorialScreen extends StatelessWidget {
  const TutorialScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(32, 24, 32, 40),
          child: Column(
            children: [
              const SizedBox(height: 50),
              Image.asset(AppImages.cashMascot, width: 150),
              const SizedBox(height: 30),
              Text.rich(
                const TextSpan(
                  style: _messageStyle,
                  children: [
                    TextSpan(text: '처음이시네요! 반가워요.\n저는 '),
                    TextSpan(text: '모아', style: _emphasisStyle),
                    TextSpan(text: '라고 해요.\n원활한 사용을 위해 제가 도와드릴게요.'),
                  ],
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 150),
              Image.asset(AppImages.mainpageMascot, width: 160),
              const SizedBox(height: 12),
              Image.asset(AppImages.titleIcon, width: 140),
              const SizedBox(height: 20),
              Text.rich(
                const TextSpan(
                  style: _messageStyle,
                  children: [
                    TextSpan(text: '안정형은 '),
                    TextSpan(text: '원금손실이 없는 안전한 자산증식', style: _emphasisStyle),
                    TextSpan(text: '을\n원하시는 분들을 위한 서비스에요.'),
                  ],
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 64),
              const Text(
                '원금이 보장되는 상품만 놓고\n이자를 가장 많이 받는 조합을 모아가 찾아드려요.',
                style: _messageStyle,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 60),
              const Text(
                '안정형은 소중한 원금과 이윤을 계산해주고\n기록을 도와드려요.\nOO님이 하신 투자 결정을,\n모아가 알뜰하게 관리할게요.',
                style: _messageStyle,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 160),
              const Text(
                '캘린더에서는 지금까지 가입한 상품들의\n납입일정, 만기일을 쉽게 확인하실 수 있어요.',
                style: _messageStyle,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 64),
              Image.asset(AppImages.safeMascot, width: 200),
              const SizedBox(height: 24),
              const Text(
                'OO님께 최적의 상품을 알아볼 준비가 되셨나요?\n상품들의 조건과 OO님의 상황을 파악할 수 있는\n몇 가지 질문들이 기다리고 있어요.',
                style: _messageStyle,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 82),
              PrimaryButton(
                label: '조건 응답하러 가기',
                onPressed: () => context.push(AppRoutes.inputStep1),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

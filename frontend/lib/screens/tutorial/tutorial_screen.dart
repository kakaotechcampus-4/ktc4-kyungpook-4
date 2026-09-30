import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../router/app_router.dart';
import '../../theme/app_colors.dart';
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
/// 대화형 온보딩. 화면을 탭하거나 좌우로 스와이프해서 다음 메시지로
/// 넘어가고, 마지막 페이지에서 "조건 응답하러 가기"를 누르면
/// 입력 1단계로 이동한다.
class TutorialScreen extends StatefulWidget {
  const TutorialScreen({super.key});

  @override
  State<TutorialScreen> createState() => _TutorialScreenState();
}

class _TutorialScreenState extends State<TutorialScreen> {
  static const _pageCount = 4;

  final _pageController = PageController();
  int _page = 0;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _goToNextPage() {
    if (_page >= _pageCount - 1) return;
    _pageController.nextPage(
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOut,
    );
  }

  void _startOnboarding() => context.push(AppRoutes.inputStep1);

  @override
  Widget build(BuildContext context) {
    final isLastPage = _page == _pageCount - 1;

    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: GestureDetector(
                behavior: HitTestBehavior.translucent,
                onTap: isLastPage ? null : _goToNextPage,
                child: PageView(
                  controller: _pageController,
                  onPageChanged: (index) => setState(() => _page = index),
                  children: const [
                    _WelcomePage(),
                    _MatchingPage(),
                    _CalendarPage(),
                    _ReadyPage(),
                  ],
                ),
              ),
            ),
            _PageIndicator(pageCount: _pageCount, currentPage: _page),
            const SizedBox(height: 20),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
              child: isLastPage
                  ? PrimaryButton(
                      label: '조건 응답하러 가기',
                      onPressed: _startOnboarding,
                    )
                  : Align(
                      child: IconButton(
                        onPressed: _goToNextPage,
                        style: IconButton.styleFrom(
                          backgroundColor: AppColors.background,
                          padding: const EdgeInsets.all(12),
                          shape: const CircleBorder(),
                        ),
                        icon: const Icon(
                          Icons.arrow_forward,
                          color: AppColors.labelPurple,
                        ),
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PageIndicator extends StatelessWidget {
  const _PageIndicator({required this.pageCount, required this.currentPage});

  final int pageCount;
  final int currentPage;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(pageCount, (index) {
        final isActive = index == currentPage;
        return AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          margin: const EdgeInsets.symmetric(horizontal: 4),
          width: isActive ? 20 : 6,
          height: 6,
          decoration: BoxDecoration(
            color: isActive ? AppColors.lavender : AppColors.background,
            borderRadius: BorderRadius.circular(3),
          ),
        );
      }),
    );
  }
}

class _WelcomePage extends StatelessWidget {
  const _WelcomePage();

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        children: [
          const SizedBox(height: 24),
          Image.asset(AppImages.cashMascot, width: 140),
          const SizedBox(height: 20),
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
          const SizedBox(height: 56),
          Image.asset(AppImages.mainpageMascot, width: 100),
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
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

class _MatchingPage extends StatelessWidget {
  const _MatchingPage();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: const Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '원금이 보장되는 상품만 놓고\n이자를 가장 많이 받는 조합을 모아가 찾아드려요.',
              style: _messageStyle,
              textAlign: TextAlign.center,
            ),
            SizedBox(height: 40),
            Text(
              '안정형은 소중한 원금과 이윤을 계산해주고\n기록을 도와드려요.\nOO님이 하신 투자 결정을,\n모아가 알뜰하게 관리할게요.',
              style: _messageStyle,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _CalendarPage extends StatelessWidget {
  const _CalendarPage();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: const Text(
          '캘린더에서는 지금까지 가입한 상품들의\n납입일정, 만기일을 쉽게 확인하실 수 있어요.',
          style: _messageStyle,
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}

class _ReadyPage extends StatelessWidget {
  const _ReadyPage();

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        children: [
          const SizedBox(height: 32),
          Image.asset(AppImages.safeMascot, width: 200),
          const SizedBox(height: 24),
          const Text(
            'OO님께 최적의 상품을 알아볼 준비가 되셨나요?\n상품들의 조건과 OO님의 상황을 파악할 수 있는\n몇 가지 질문들이 기다리고 있어요.',
            style: _messageStyle,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
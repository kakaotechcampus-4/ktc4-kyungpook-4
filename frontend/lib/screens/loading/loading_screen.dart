import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers/onboarding_provider.dart';
import '../../providers/portfolio_provider.dart';
import '../../router/app_router.dart';
import '../../services/api_client.dart';
import '../../theme/app_colors.dart';
import '../../utils/app_images.dart';

/// 마스코트가 빙글빙글 도는 동안 로딩 바가 한 번 가득 차고, 그 사이 프로필을
/// 만든다. 결과 화면·챗봇 질문·재추천이 전부 이 profile_id 하나를 계속 써야
/// 하므로, 생성은 이 화면 한 곳에서만 하고 [currentProfileIdProvider]에
/// 저장해둔다. 애니메이션과 생성 둘 다 끝나야 결과 화면으로 넘어간다.
class LoadingScreen extends ConsumerStatefulWidget {
  const LoadingScreen({super.key});

  @override
  ConsumerState<LoadingScreen> createState() => _LoadingScreenState();
}

class _LoadingScreenState extends ConsumerState<LoadingScreen>
    with TickerProviderStateMixin {
  late final _mascotSpin =
      AnimationController(vsync: this, duration: const Duration(seconds: 2))
        ..repeat();
  late final _barFill = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2200),
  )..forward();

  bool _animationDone = false;
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
    _barFill.addStatusListener(_onBarFillStatusChanged);
    _createProfile();
  }

  Future<void> _createProfile() async {
    try {
      final input = ref.read(onboardingProvider);
      final profileId = await ApiClient.instance.createProfile(input);
      if (!mounted) return;
      ref.read(currentProfileIdProvider.notifier).state = profileId;
      _tryProceed();
    } catch (_) {
      if (!mounted) return;
      setState(() => _hasError = true);
    }
  }

  void _onBarFillStatusChanged(AnimationStatus status) {
    if (status != AnimationStatus.completed) return;
    Future.delayed(const Duration(milliseconds: 300), () {
      if (!mounted) return;
      _animationDone = true;
      _tryProceed();
    });
  }

  /// 로딩 바 애니메이션이 끝났고 프로필도 준비됐을 때만 결과 화면으로 넘어간다.
  void _tryProceed() {
    if (_hasError || !_animationDone) return;
    if (ref.read(currentProfileIdProvider) == null) return;
    context.go(AppRoutes.result);
  }

  void _retry() {
    setState(() => _hasError = false);
    _createProfile();
  }

  @override
  void dispose() {
    _barFill.removeStatusListener(_onBarFillStatusChanged);
    _mascotSpin.dispose();
    _barFill.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            RotationTransition(
              turns: _mascotSpin,
              child: Image.asset(AppImages.loadingMascot, width: 140),
            ),
            const SizedBox(height: 24),
            Text(
              _hasError ? '상품을 준비하지 못했어요' : '모아가 상품을 준비하고 있어요',
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: AppColors.labelPurple,
              ),
            ),
            const SizedBox(height: 20),
            if (_hasError)
              TextButton(onPressed: _retry, child: const Text('다시 시도'))
            else
              _LoadingBar(controller: _barFill),
          ],
        ),
      ),
    );
  }
}

class _LoadingBar extends StatelessWidget {
  static const _width = 220.0;
  static const _height = 14.0;

  final Animation<double> controller;

  const _LoadingBar({required this.controller});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: _width,
      height: _height,
      child: Stack(
        children: [
          Container(
            decoration: BoxDecoration(
              color: AppColors.lavender.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(_height / 2),
            ),
          ),
          AnimatedBuilder(
            animation: controller,
            builder: (context, child) {
              final t = Curves.easeInOut.transform(controller.value);
              // 0%일 땐 폭=높이라 둥근 점으로 보이고, 100%일 때 꽉 찬 바가 된다.
              final fillWidth = _height + (_width - _height) * t;
              return Container(
                width: fillWidth,
                height: _height,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [AppColors.lavender, AppColors.labelPurple],
                  ),
                  borderRadius: BorderRadius.circular(_height / 2),
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}

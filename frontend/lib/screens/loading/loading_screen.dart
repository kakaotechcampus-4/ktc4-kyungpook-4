import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../router/app_router.dart';
import '../../theme/app_colors.dart';
import '../../utils/app_images.dart';

/// 마스코트가 빙글빙글 도는 동안 로딩 바가 한 번 가득 차고 나서
/// 결과 화면으로 넘어가는 전환 화면.
class LoadingScreen extends StatefulWidget {
  const LoadingScreen({super.key});

  @override
  State<LoadingScreen> createState() => _LoadingScreenState();
}

class _LoadingScreenState extends State<LoadingScreen>
    with TickerProviderStateMixin {
  late final _mascotSpin =
      AnimationController(vsync: this, duration: const Duration(seconds: 2))
        ..repeat();
  late final _barFill = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2200),
  )..forward();

  @override
  void initState() {
    super.initState();
    _barFill.addStatusListener(_onBarFillStatusChanged);
  }

  void _onBarFillStatusChanged(AnimationStatus status) {
    if (status != AnimationStatus.completed) return;
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) context.go(AppRoutes.result);
    });
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
            const Text(
              '모아가 상품을 준비하고 있어요',
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: AppColors.labelPurple,
              ),
            ),
            const SizedBox(height: 20),
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

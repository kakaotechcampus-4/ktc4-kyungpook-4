import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../utils/app_images.dart';

/// 챗봇 "모아"의 말풍선 한 턴. 아바타 + 이름표 + 말풍선(내용은 [content])으로 구성된다.
class BotChatTurn extends StatelessWidget {
  final Widget content;

  const BotChatTurn({super.key, required this.content});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _BotAvatar(),
        const SizedBox(height: 4),
        const Text(
          '모아',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.bold,
            color: AppColors.labelPurple,
          ),
        ),
        const SizedBox(height: 8),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.lavender.withValues(alpha: 0.18),
            borderRadius: BorderRadius.circular(18),
          ),
          child: content,
        ),
      ],
    );
  }
}

class _BotAvatar extends StatelessWidget {
  const _BotAvatar();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 48,
      height: 48,
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [AppColors.lavender.withValues(alpha: 0.35), Colors.white],
        ),
        border: Border.all(color: AppColors.lavender.withValues(alpha: 0.4)),
      ),
      child: ClipOval(
        child: Image.asset(AppImages.mainpageMascot, fit: BoxFit.cover),
      ),
    );
  }
}

/// 응답을 기다리는 동안 보여주는 "생각하는 중..." 표시.
class ThinkingIndicator extends StatefulWidget {
  const ThinkingIndicator({super.key});

  @override
  State<ThinkingIndicator> createState() => _ThinkingIndicatorState();
}

class _ThinkingIndicatorState extends State<ThinkingIndicator>
    with SingleTickerProviderStateMixin {
  late final _controller =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))
        ..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Text(
          '생각하는 중',
          style: TextStyle(fontSize: 14, color: Colors.black87),
        ),
        const SizedBox(width: 4),
        AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final dotCount = (_controller.value * 3).floor() + 1;
            return Text(
              '.' * dotCount,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: AppColors.labelPurple,
              ),
            );
          },
        ),
      ],
    );
  }
}

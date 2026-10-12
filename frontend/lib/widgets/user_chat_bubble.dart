import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// 사용자가 보낸 답변을 챗봇 턴 사이에 오른쪽 정렬 말풍선으로 보여준다.
/// [BotChatTurn]과 짝을 이뤄 "모아와 나눈 대화" 형태를 완성한다.
class UserChatBubble extends StatelessWidget {
  final String text;

  const UserChatBubble({super.key, required this.text});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * 0.75,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.lavender,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Text(
          text,
          style: const TextStyle(fontSize: 14, color: Colors.white, height: 1.4),
        ),
      ),
    );
  }
}

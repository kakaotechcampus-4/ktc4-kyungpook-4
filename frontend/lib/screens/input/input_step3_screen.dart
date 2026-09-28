import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/onboarding_input.dart';
import '../../providers/onboarding_provider.dart';
import '../../router/app_router.dart';
import '../../theme/app_colors.dart';
import '../../widgets/bot_chat_turn.dart';
import '../../widgets/choice_chip_group.dart';
import '../../widgets/step_indicator.dart';

/// 상호금융(신협·새마을금고 등) 계좌를 보유한 경우에만 묻는 조합원 여부 확인 질문.
/// 해당 은행이 없으면 확인할 게 없으므로 질문 없이 바로 결과로 넘어간다.
class _ChatQuestion {
  final String botMessage;
  final List<String> options;
  String? answer;

  _ChatQuestion({required this.botMessage, required this.options});
}

List<_ChatQuestion> _buildQuestions(OnboardingInput input) {
  final mutualBanks =
      input.currentBanks.where((b) => b == '신협' || b == '새마을금고').toList();
  if (mutualBanks.isEmpty) return [];

  final bankLabel = mutualBanks.join('·');
  return [
    _ChatQuestion(
      botMessage: '거의 다 왔어요!\n마지막으로 세금 부분만 확인할게요.\n\n'
          '상호금융($bankLabel 등)은 3,000만원까지\n'
          '이자 세금이 15.4% → 1.4%로 낮아져요.\n'
          '현재 금액이면 대략 OO만원 차이입니다.\n\n'
          '아까 $bankLabel 계좌가 있다고 하셨는데,\n'
          '혹시 조합원으로 가입되어 있으실까요?\n\n'
          '(계좌만 만든 경우는 조합원이 아닐 수 있어요.\n'
          '출자금(보통 1~5만원)을 냈다면 조합원입니다.)',
      options: const ['네,조합원이에요', '잘 모르겠어요', '계좌만 있어요'],
    ),
  ];
}

enum _ChatStatus { asking, thinking, error, done }

class InputStep3Screen extends ConsumerStatefulWidget {
  const InputStep3Screen({super.key});

  @override
  ConsumerState<InputStep3Screen> createState() => _InputStep3ScreenState();
}

class _InputStep3ScreenState extends ConsumerState<InputStep3Screen> {
  static const _thinkingTimeout = Duration(seconds: 20);

  final _scrollController = ScrollController();
  late final List<_ChatQuestion> _questions =
      _buildQuestions(ref.read(onboardingProvider));

  int _currentIndex = 0;
  var _status = _ChatStatus.asking;

  @override
  void initState() {
    super.initState();
    if (_questions.isEmpty) {
      _status = _ChatStatus.done;
      WidgetsBinding.instance.addPostFrameCallback((_) => _finish());
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottomSoon() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });
  }

  void _selectAnswer(String value) {
    setState(() => _questions[_currentIndex].answer = value);
    ref.read(onboardingProvider.notifier).updateCooperativeMembershipStatus(value);
    _scrollToBottomSoon();
    _proceed();
  }

  Future<void> _proceed() async {
    setState(() => _status = _ChatStatus.thinking);
    _scrollToBottomSoon();
    try {
      // TODO: 백엔드 챗봇 API 연동 시 이 자리에서 다음 질문을 받아온다.
      await Future<void>.delayed(const Duration(milliseconds: 900))
          .timeout(_thinkingTimeout);
      if (!mounted) return;
      setState(() {
        if (_currentIndex < _questions.length - 1) {
          _currentIndex++;
          _status = _ChatStatus.asking;
        } else {
          _status = _ChatStatus.done;
        }
      });
      _scrollToBottomSoon();
      if (_status == _ChatStatus.done) _finish();
    } on TimeoutException {
      if (!mounted) return;
      setState(() => _status = _ChatStatus.error);
      _scrollToBottomSoon();
    }
  }

  void _finish() {
    Future.delayed(const Duration(milliseconds: 1200), () {
      if (mounted) context.go(AppRoutes.result);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          controller: _scrollController,
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const StepIndicator(currentStep: 3),
              const SizedBox(height: 32),
              if (_questions.isEmpty)
                const BotChatTurn(
                  content: Text(
                    '추가로 확인할 사항이 없어요!\n바로 결과를 보여드릴게요 :)',
                    style: TextStyle(fontSize: 14, height: 1.5, color: Colors.black87),
                  ),
                )
              else
                for (var i = 0; i <= _currentIndex && i < _questions.length; i++)
                  _buildQuestionTurn(i),
              if (_status == _ChatStatus.thinking) ...[
                const SizedBox(height: 20),
                const BotChatTurn(content: ThinkingIndicator()),
              ],
              if (_status == _ChatStatus.error) ...[
                const SizedBox(height: 20),
                BotChatTurn(content: _buildErrorContent()),
              ],
              if (_status == _ChatStatus.done && _questions.isNotEmpty) ...[
                const SizedBox(height: 20),
                const BotChatTurn(
                  content: Text(
                    '모든 확인이 끝났어요!\n맞춤 상품을 준비할게요 🎉',
                    style: TextStyle(fontSize: 14, height: 1.5, color: Colors.black87),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildQuestionTurn(int index) {
    final question = _questions[index];
    final isActive = index == _currentIndex && _status == _ChatStatus.asking;

    return Padding(
      padding: EdgeInsets.only(bottom: index == _currentIndex ? 0 : 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          BotChatTurn(
            content: Text(
              question.botMessage,
              style: const TextStyle(fontSize: 14, height: 1.6, color: Colors.black87),
            ),
          ),
          const SizedBox(height: 12),
          IgnorePointer(
            ignoring: !isActive,
            child: ChoiceChipGroup(
              options: question.options,
              selected: question.answer ?? '',
              onSelected: _selectAnswer,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorContent() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '응답이 없습니다. 다시 실행해주세요.',
          style: TextStyle(fontSize: 14, color: Colors.black87),
        ),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton(
            onPressed: _proceed,
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.labelPurple,
              side: const BorderSide(color: AppColors.lavender),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape:
                  RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: const Text('다시 시도', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ),
      ],
    );
  }
}

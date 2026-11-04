import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/etc_question.dart';
import '../../providers/chatbot_provider.dart';
import '../../providers/portfolio_provider.dart';
import '../../router/app_router.dart';
import '../../services/api_client.dart';
import '../../theme/app_colors.dart';
import '../../widgets/bot_chat_turn.dart';
import '../../widgets/user_chat_bubble.dart';

/// 로딩 화면에서 받아온 '기타' 우대조건 질문을 하나씩 채팅으로 묻는다.
/// 다 답하면 한 번에 저장하고 결과 화면으로 넘어간다 - 그 답이 반영된 결과는
/// 결과 화면의 recommendationProvider 가 처음 recommend 를 부를 때 나온다.
class ChatbotEtcScreen extends ConsumerStatefulWidget {
  const ChatbotEtcScreen({super.key});

  @override
  ConsumerState<ChatbotEtcScreen> createState() => _ChatbotEtcScreenState();
}

class _ChatbotEtcScreenState extends ConsumerState<ChatbotEtcScreen> {
  final _scrollController = ScrollController();
  final _answerController = TextEditingController();

  late final List<EtcQuestion> _questions = ref.read(pendingEtcQuestionsProvider);
  final List<String> _answers = [];
  bool _isSubmitting = false;
  bool _hasError = false;

  bool get _isDone => _answers.length >= _questions.length;

  @override
  void initState() {
    super.initState();
    // 방어적 처리 - 로딩 화면이 질문 있을 때만 이 화면으로 보내지만, 혹시 비어 있으면
    // 물을 게 없으니 바로 결과로 간다.
    if (_questions.isEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) context.go(AppRoutes.result);
      });
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _answerController.dispose();
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

  void _submitCurrentAnswer() {
    final text = _answerController.text.trim();
    if (text.isEmpty || _isDone) return;
    setState(() => _answers.add(text));
    _answerController.clear();
    _scrollToBottomSoon();
    if (_isDone) _finish();
  }

  Future<void> _finish() async {
    setState(() {
      _isSubmitting = true;
      _hasError = false;
    });
    _scrollToBottomSoon();
    try {
      final profileId = ref.read(currentProfileIdProvider);
      final submissions = [
        for (var i = 0; i < _questions.length; i++)
          EtcAnswerSubmission(
            conditionIds: _questions[i].conditionIds,
            question: _questions[i].question,
            answer: _answers[i],
          ),
      ];
      await ApiClient.instance.sendEtcAnswers(profileId!, submissions);
      if (!mounted) return;
      context.go(AppRoutes.result);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        _hasError = true;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: SingleChildScrollView(
                controller: _scrollController,
                padding: const EdgeInsets.fromLTRB(24, 24, 24, 24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (var i = 0; i < _answers.length; i++) ...[
                      BotChatTurn(content: Text(_questions[i].question)),
                      const SizedBox(height: 12),
                      UserChatBubble(text: _answers[i]),
                      const SizedBox(height: 20),
                    ],
                    if (!_isDone)
                      BotChatTurn(content: Text(_questions[_answers.length].question)),
                    if (_isSubmitting)
                      const Padding(
                        padding: EdgeInsets.only(top: 20),
                        child: BotChatTurn(content: ThinkingIndicator()),
                      ),
                    if (_hasError)
                      Padding(
                        padding: const EdgeInsets.only(top: 20),
                        child: BotChatTurn(content: _buildErrorContent()),
                      ),
                  ],
                ),
              ),
            ),
            if (!_isDone && !_isSubmitting) _buildAnswerInputBar(),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorContent() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '답변을 저장하지 못했습니다. 다시 시도해주세요.',
          style: TextStyle(fontSize: 14, color: Colors.black87),
        ),
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton(
            onPressed: _finish,
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.labelPurple,
              side: const BorderSide(color: AppColors.lavender),
              padding: const EdgeInsets.symmetric(vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: const Text('다시 시도', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ),
      ],
    );
  }

  Widget _buildAnswerInputBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(top: BorderSide(color: Colors.grey.shade200)),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _answerController,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _submitCurrentAnswer(),
              decoration: InputDecoration(
                hintText: '답변을 입력해주세요',
                filled: true,
                fillColor: AppColors.background,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            onPressed: _submitCurrentAnswer,
            style: IconButton.styleFrom(
              backgroundColor: AppColors.lavender,
              shape: const CircleBorder(),
            ),
            icon: const Icon(Icons.arrow_upward, color: Colors.white),
          ),
        ],
      ),
    );
  }
}

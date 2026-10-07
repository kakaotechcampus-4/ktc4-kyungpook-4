import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/onboarding_input.dart';
import '../../providers/onboarding_provider.dart';
import '../../router/app_router.dart';
import '../../theme/app_colors.dart';
import '../../widgets/bot_chat_turn.dart';
import '../../widgets/checkbox_option_list.dart';
import '../../widgets/choice_chip_group.dart';
import '../../widgets/next_step_button.dart';
import '../../widgets/step_indicator.dart';
import '../../widgets/user_chat_bubble.dart';

const _membershipOptions = ['네,조합원이에요', '잘 모르겠어요', '계좌만 있어요'];
const _eligibleOptions = ['네,해당돼요', '잘 모르겠어요', '해당되지 않아요'];
const _joinOptions = [
  '신협 (전국 어디든 가입 가능)',
  '새마을금고 (거주지·직장 지역만 가능)',
  '농협·수협 (출자금이 조금 더 높아요 (10만원 안팍))',
  '다 부담스러워요',
];
const _joinNoneOption = '다 부담스러워요';

const _botTextStyle = TextStyle(fontSize: 14, height: 1.6, color: Colors.black87);

/// 상호금융(신협·새마을금고) 계좌를 보유한 경우에만 진행되는 챗봇형 확인 대화.
/// 해당 은행이 없으면 확인할 게 없으므로 대화 없이 바로 결과로 넘어간다.
List<String> _mutualBanksOf(OnboardingInput input) =>
    input.currentBanks.where((b) => b == '신협' || b == '새마을금고').toList();

/// 체크박스에 쓰인 설명 포함 라벨("신협 (전국 어디든...)")에서
/// 짧은 기관명("신협")만 뽑아낸다. 사용자 답변 말풍선 요약에 쓰인다.
String _shortLabel(String option) => option.split(' (').first;

enum _Stage { membership, joinChoices, taxEligible, existingAmount, closing }

enum _ChatStatus { asking, thinking, error, done }

class InputStep3Screen extends ConsumerStatefulWidget {
  const InputStep3Screen({super.key});

  @override
  ConsumerState<InputStep3Screen> createState() => _InputStep3ScreenState();
}

class _InputStep3ScreenState extends ConsumerState<InputStep3Screen> {
  static const _thinkingTimeout = Duration(seconds: 20);

  final _scrollController = ScrollController();
  final _amountController = TextEditingController();
  final _noteController = TextEditingController();

  late final List<String> _mutualBanks = _mutualBanksOf(ref.read(onboardingProvider));

  final List<_Stage> _path = [];
  final List<String> _sentNotes = [];
  var _status = _ChatStatus.asking;

  _Stage? get _currentStage => _path.isEmpty ? null : _path.last;

  @override
  void initState() {
    super.initState();
    if (_mutualBanks.isEmpty) {
      _status = _ChatStatus.done;
    } else {
      _path.add(_Stage.membership);
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _amountController.dispose();
    _noteController.dispose();
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

  /// 현재 단계에 답했을 때 다음에 보여줄 단계를 계산한다 (분기 지점).
  _Stage _resolveNextStage(_Stage current) {
    final input = ref.read(onboardingProvider);
    switch (current) {
      case _Stage.membership:
        return input.cooperativeMembershipStatus == '네,조합원이에요'
            ? _Stage.taxEligible
            : _Stage.joinChoices;
      case _Stage.joinChoices:
        final onlyGaveUp = input.cooperativeJoinChoices.length == 1 &&
            input.cooperativeJoinChoices.first == _joinNoneOption;
        return onlyGaveUp ? _Stage.closing : _Stage.taxEligible;
      case _Stage.taxEligible:
        return _Stage.existingAmount;
      case _Stage.existingAmount:
      case _Stage.closing:
        return _Stage.closing;
    }
  }

  Future<void> _advance() async {
    final current = _currentStage;
    if (current == null) return;
    setState(() => _status = _ChatStatus.thinking);
    _scrollToBottomSoon();
    try {
      // TODO: 백엔드 챗봇 API 연동 시 이 자리에서 다음 질문을 받아온다.
      await Future<void>.delayed(const Duration(milliseconds: 900))
          .timeout(_thinkingTimeout);
      if (!mounted) return;
      final next = _resolveNextStage(current);
      setState(() {
        _status = _ChatStatus.asking;
        if (current != next) _path.add(next);
      });
      _scrollToBottomSoon();
      if (next == _Stage.closing) {
        setState(() => _status = _ChatStatus.done);
      }
    } on TimeoutException {
      if (!mounted) return;
      setState(() => _status = _ChatStatus.error);
      _scrollToBottomSoon();
    }
  }

  /// 자동으로 넘어가지 않고, 사용자가 "결과 보기"를 눌렀을 때만 이동한다.
  void _goToResult() {
    final draft = _noteController.text.trim();
    if (draft.isNotEmpty) {
      ref.read(onboardingProvider.notifier).updateAdditionalNote(draft);
    }
    context.go(AppRoutes.result);
  }

  void _sendNote() {
    final text = _noteController.text.trim();
    if (text.isEmpty) return;
    ref.read(onboardingProvider.notifier).updateAdditionalNote(text);
    setState(() => _sentNotes.add(text));
    _noteController.clear();
    FocusScope.of(context).unfocus();
    _scrollToBottomSoon();
  }

  @override
  Widget build(BuildContext context) {
    final input = ref.watch(onboardingProvider);
    final isClosingActive = _currentStage == _Stage.closing;

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
                    StepIndicator(
                      currentStep: 3,
                      onStepTap: (step) => context.go(AppRoutes.inputStep(step)),
                    ),
                    const SizedBox(height: 32),
                    if (_mutualBanks.isEmpty) ...[
                      const BotChatTurn(
                        content: Text(
                          '추가로 확인할 사항이 없어요!\n바로 결과를 보여드릴게요 :)',
                          style: _botTextStyle,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Align(
                        alignment: Alignment.centerRight,
                        child: NextStepButton(
                          label: '결과 보기',
                          enabled: true,
                          onPressed: _goToResult,
                        ),
                      ),
                    ] else
                      for (final stage in _path) ...[
                        _buildStageTurn(
                          stage,
                          input,
                          isActive:
                              stage == _currentStage && _status == _ChatStatus.asking,
                        ),
                        const SizedBox(height: 20),
                      ],
                    for (final note in _sentNotes) ...[
                      UserChatBubble(text: note),
                      const SizedBox(height: 12),
                    ],
                    if (_status == _ChatStatus.thinking)
                      const BotChatTurn(content: ThinkingIndicator()),
                    if (_status == _ChatStatus.error)
                      BotChatTurn(content: _buildErrorContent()),
                  ],
                ),
              ),
            ),
            if (isClosingActive) _buildNoteInputBar(),
          ],
        ),
      ),
    );
  }

  Widget _buildStageTurn(_Stage stage, OnboardingInput input, {required bool isActive}) {
    switch (stage) {
      case _Stage.membership:
        final bankLabel = _mutualBanks.join('·');
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            BotChatTurn(
              content: Text(
                '거의 다 왔어요!\n마지막으로 세금 부분만 확인할게요.\n\n'
                '상호금융($bankLabel 등)은 3,000만원까지\n'
                '이자 세금이 15.4% → 1.4%로 낮아져요.\n'
                '현재 금액이면 대략 OO만원 차이입니다.\n\n'
                '아까 $bankLabel 계좌가 있다고 하셨는데,\n'
                '혹시 조합원으로 가입되어 있으실까요?\n\n'
                '(계좌만 만든 경우는 조합원이 아닐 수 있어요.\n'
                '출자금(보통 1~5만원)을 냈다면 조합원입니다.)',
                style: _botTextStyle,
              ),
            ),
            const SizedBox(height: 12),
            IgnorePointer(
              ignoring: !isActive,
              child: ChoiceChipGroup(
                options: _membershipOptions,
                selected: input.cooperativeMembershipStatus,
                onSelected: (value) {
                  ref
                      .read(onboardingProvider.notifier)
                      .updateCooperativeMembershipStatus(value);
                  _advance();
                },
              ),
            ),
          ],
        );

      case _Stage.joinChoices:
        final confirmed = !isActive;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const BotChatTurn(
              content: Text(
                '괜찮아요! 대부분 헷갈리시는 부분이에요.\n'
                '조합원이 아니어도, 가입할 때 출자금 1~5만원만\n'
                '내면 바로 조합원이 될 수 있어요.\n'
                '출자금은 나중에 돌려받을 수 있으니 걱정마세요.\n\n'
                '그럼 이 중에서 가입하실 수 있는 곳을 골라주세요.\n'
                '여러 개 선택 가능해요.',
                style: _botTextStyle,
              ),
            ),
            const SizedBox(height: 12),
            IgnorePointer(
              ignoring: !isActive,
              child: CheckboxOptionList(
                options: _joinOptions,
                selected: input.cooperativeJoinChoices,
                noneOption: _joinNoneOption,
                onToggle: (value) => ref
                    .read(onboardingProvider.notifier)
                    .toggleCooperativeJoinChoice(value, noneOption: _joinNoneOption),
              ),
            ),
            if (isActive) ...[
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: NextStepButton(
                  label: '다 골랐어요',
                  enabled: input.cooperativeJoinChoices.isNotEmpty,
                  onPressed: _advance,
                ),
              ),
            ],
            if (confirmed && input.cooperativeJoinChoices.isNotEmpty) ...[
              const SizedBox(height: 12),
              UserChatBubble(
                text: input.cooperativeJoinChoices.map(_shortLabel).join(', '),
              ),
            ],
          ],
        );

      case _Stage.taxEligible:
        final institutions = input.cooperativeMembershipStatus == '네,조합원이에요'
            ? _mutualBanks
            : input.cooperativeJoinChoices
                .where((o) => o != _joinNoneOption)
                .map(_shortLabel)
                .toList();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            BotChatTurn(
              content: Text(
                _buildEligibilityMessage(institutions, input),
                style: _botTextStyle,
              ),
            ),
            const SizedBox(height: 12),
            IgnorePointer(
              ignoring: !isActive,
              child: ChoiceChipGroup(
                options: _eligibleOptions,
                selected: input.mutualFinanceTaxExemptEligible,
                onSelected: (value) {
                  ref
                      .read(onboardingProvider.notifier)
                      .updateMutualFinanceTaxExemptEligible(value);
                  _advance();
                },
              ),
            ),
          ],
        );

      case _Stage.existingAmount:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const BotChatTurn(
              content: Text(
                '좋습니다.\n비과세는 상호금융 전체를 합쳐서 3,000만원의\n'
                '한도 제한이 있어요.\n\n'
                '혹시 다른 곳에 비과세로 넣어두신 돈이 있으신가요?\n'
                '있다면 금액을 입력해주세요.',
                style: _botTextStyle,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                SizedBox(
                  width: 120,
                  child: TextField(
                    controller: _amountController,
                    enabled: isActive && !input.mutualFinanceExistingAmountUnknown,
                    keyboardType: TextInputType.number,
                    textInputAction: TextInputAction.done,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    textAlign: TextAlign.right,
                    decoration: InputDecoration(
                      hintText: '0',
                      filled: true,
                      fillColor: input.mutualFinanceExistingAmountUnknown
                          ? Colors.grey.shade100
                          : Colors.white,
                      contentPadding:
                          const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                        borderSide: BorderSide(color: Colors.grey.shade300),
                      ),
                    ),
                    onChanged: (value) => ref
                        .read(onboardingProvider.notifier)
                        .updateMutualFinanceExistingAmountText(value),
                    onSubmitted: (_) {
                      if (isActive) _advance();
                    },
                  ),
                ),
                const SizedBox(width: 8),
                const Text('원'),
                const SizedBox(width: 12),
                Expanded(
                  child: OptionChip(
                    label: '잘 모르겠어요',
                    selected: input.mutualFinanceExistingAmountUnknown,
                    onTap: () {
                      if (!isActive) return;
                      _amountController.clear();
                      ref
                          .read(onboardingProvider.notifier)
                          .setMutualFinanceExistingAmountUnknown();
                      _advance();
                    },
                  ),
                ),
              ],
            ),
            if (isActive && !input.mutualFinanceExistingAmountUnknown) ...[
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: NextStepButton(
                  label: '입력 완료',
                  enabled: input.mutualFinanceExistingAmountText.isNotEmpty,
                  onPressed: _advance,
                ),
              ),
            ],
          ],
        );

      case _Stage.closing:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const BotChatTurn(
              content: Text(
                '됐어요!\n추가로 궁금하신 점이나,\n'
                '모아가 OO님에 대해 알아야 할 부분이 있다면\n'
                '무엇이든 말해주세요!',
                style: _botTextStyle,
              ),
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: NextStepButton(
                label: '결과 보기',
                enabled: true,
                onPressed: _goToResult,
              ),
            ),
          ],
        );
    }
  }

  String _buildEligibilityMessage(List<String> institutions, OnboardingInput input) {
    final mentionsMg = institutions.contains('새마을금고');
    final region = [input.residenceSido, input.residenceSigungu]
        .where((s) => s.isNotEmpty)
        .join(' ');
    final label = institutions.isEmpty ? _mutualBanks.join('·') : institutions.join('·');
    final intro = (mentionsMg && region.isNotEmpty)
        ? '좋아요, 거주지(직장)를 기준으로 새마을금고는\n$region 지역 금고로 찾아볼게요.\n\n'
        : '좋아요, $label 조건으로 찾아볼게요.\n\n';
    return '$intro'
        '비과세 혜택은 총급여 7,000만원 이하일 때\n적용돼요.\n'
        '(2026년부터 기준이 이렇게 바뀌었어요)\n\n'
        '해당되시나요?';
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
            onPressed: _advance,
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

  Widget _buildNoteInputBar() {
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
              controller: _noteController,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _sendNote(),
              decoration: InputDecoration(
                hintText: '자유롭게 입력해주세요',
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
            onPressed: _sendNote,
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

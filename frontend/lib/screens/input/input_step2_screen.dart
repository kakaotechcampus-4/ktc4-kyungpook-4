import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/bank_options.dart';
import '../../data/korea_regions.dart';
import '../../providers/onboarding_provider.dart';
import '../../router/app_router.dart';
import '../../theme/app_colors.dart';
import '../../widgets/checkbox_option_list.dart';
import '../../widgets/choice_chip_group.dart';
import '../../widgets/next_step_button.dart';
import '../../widgets/searchable_select_field.dart';
import '../../widgets/step_indicator.dart';

const _yesNoUnknownOptions = ['가능해요', '잘 모르겠어요', '불가능해요'];
const _taxExemptOptions = [
  '만 65세 이상이고 기초연금을 받고 있어요',
  '등록 장애인이에요',
  '독립유공자/국가유공자예요',
  '기초생활수급자예요',
  '해당없음',
];
const _specialHouseholdOptions = [
  '다자녀 가정',
  '한부모 가정',
  '다문화 가정',
  '신혼부부',
  '북한이탈주민(탈북자)',
  '해당없음',
];

class InputStep2Screen extends ConsumerStatefulWidget {
  const InputStep2Screen({super.key});

  @override
  ConsumerState<InputStep2Screen> createState() => _InputStep2ScreenState();
}

class _InputStep2ScreenState extends ConsumerState<InputStep2Screen> {
  static const _questionCount = 13;

  final _questionKeys = List.generate(_questionCount, (_) => GlobalKey());
  final _revealed = <int>{};

  late final _birthYearController = TextEditingController(
    text: ref.read(onboardingProvider).birthYear,
  );
  late final _birthMonthController = TextEditingController(
    text: ref.read(onboardingProvider).birthMonth,
  );
  late final _birthDayController = TextEditingController(
    text: ref.read(onboardingProvider).birthDay,
  );
  late final _taxAmountController = TextEditingController(
    text: ref.read(onboardingProvider).existingTaxExemptAmountText,
  );

  @override
  void dispose() {
    _birthYearController.dispose();
    _birthMonthController.dispose();
    _birthDayController.dispose();
    _taxAmountController.dispose();
    super.dispose();
  }

  /// 질문 [questionIndex](0-based)가 이번에 처음 답변 완료됐다면 다음 질문으로 스크롤한다.
  void _revealNext(int questionIndex) {
    if (!_revealed.add(questionIndex)) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final nextIndex = questionIndex + 1;
      if (nextIndex >= _questionKeys.length) return;
      final ctx = _questionKeys[nextIndex].currentContext;
      if (ctx == null) return;
      Scrollable.ensureVisible(
        ctx,
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeOutCubic,
        alignment: 0,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final input = ref.watch(onboardingProvider);
    final notifier = ref.read(onboardingProvider.notifier);
    final sigunguOptions = koreaRegions[input.residenceSido] ?? const [];

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const StepIndicator(currentStep: 2),
              const SizedBox(height: 32),
              _QuestionBlock(
                key: _questionKeys[0],
                index: 1,
                title: '만기 전 인출 가능성이 있나요?',
                child: ChoiceChipGroup(
                  options: const ['있어요', '잘 모르겠어요', '없어요'],
                  selected: input.earlyWithdrawalPossibility,
                  onSelected: (v) {
                    notifier.updateEarlyWithdrawalPossibility(v);
                    _revealNext(0);
                  },
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[1],
                index: 2,
                title: '현재 보유 중인 계좌의 은행이 어디인가요?',
                description: '(복수 선택 가능)',
                child: SearchableSelectField(
                  hintText: '은행을 선택해주세요',
                  options: bankOptions,
                  selectedValues: input.currentBanks,
                  multiSelect: true,
                  onSelect: notifier.toggleCurrentBank,
                  onRemove: notifier.toggleCurrentBank,
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[2],
                index: 3,
                title: '주 거래은행이 어디인가요?',
                description: '(단일 선택)',
                child: SearchableSelectField(
                  hintText: '은행을 선택해주세요',
                  options: bankOptions,
                  selectedValues:
                      input.mainBank.isEmpty ? const [] : [input.mainBank],
                  onSelect: (bank) {
                    notifier.updateMainBank(bank);
                    _revealNext(2);
                  },
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[3],
                index: 4,
                title: '거주지가 어디신가요?',
                description: '(주민등록등본상 거주지를 입력해 주세요.)',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('시/도', style: _fieldLabelStyle),
                    const SizedBox(height: 8),
                    SearchableSelectField(
                      hintText: '시/도를 선택해주세요',
                      options: koreaSidoOptions,
                      selectedValues: input.residenceSido.isEmpty
                          ? const []
                          : [input.residenceSido],
                      onSelect: notifier.updateResidenceSido,
                    ),
                    const SizedBox(height: 20),
                    const Text('시/군/구', style: _fieldLabelStyle),
                    const SizedBox(height: 8),
                    SearchableSelectField(
                      hintText: '시/군/구를 선택해주세요',
                      options: sigunguOptions,
                      enabled: input.residenceSido.isNotEmpty,
                      selectedValues: input.residenceSigungu.isEmpty
                          ? const []
                          : [input.residenceSigungu],
                      onSelect: (v) {
                        notifier.updateResidenceSigungu(v);
                        _revealNext(3);
                      },
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[4],
                index: 5,
                title: '생년월일을 알려주세요!',
                child: Row(
                  children: [
                    Expanded(
                      flex: 3,
                      child: _DigitField(
                        controller: _birthYearController,
                        maxLength: 4,
                        onChanged: (v) {
                          notifier.updateBirthYear(v);
                          if (v.length == 4) FocusScope.of(context).nextFocus();
                        },
                      ),
                    ),
                    const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 8),
                      child: Text('년'),
                    ),
                    Expanded(
                      flex: 2,
                      child: _DigitField(
                        controller: _birthMonthController,
                        maxLength: 2,
                        onChanged: (v) {
                          notifier.updateBirthMonth(v);
                          if (v.length == 2) FocusScope.of(context).nextFocus();
                        },
                      ),
                    ),
                    const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 8),
                      child: Text('월'),
                    ),
                    Expanded(
                      flex: 2,
                      child: _DigitField(
                        controller: _birthDayController,
                        maxLength: 2,
                        onChanged: (v) {
                          notifier.updateBirthDay(v);
                          if (v.length == 2) {
                            FocusScope.of(context).unfocus();
                            _revealNext(4);
                          }
                        },
                      ),
                    ),
                    const Padding(
                      padding: EdgeInsets.only(left: 8),
                      child: Text('일'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[5],
                index: 6,
                title: '급여 받는 계좌를 옮길 수 있나요?',
                child: ChoiceChipGroup(
                  options: _yesNoUnknownOptions,
                  selected: input.salaryAccountTransferable,
                  onSelected: (v) {
                    notifier.updateSalaryAccountTransferable(v);
                    _revealNext(5);
                  },
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[6],
                index: 7,
                title: '통신비·공과금 자동이체를 옮기실 수 있나요?',
                child: ChoiceChipGroup(
                  options: _yesNoUnknownOptions,
                  selected: input.autoTransferMovable,
                  onSelected: (v) {
                    notifier.updateAutoTransferMovable(v);
                    _revealNext(6);
                  },
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[7],
                index: 8,
                title: '매 달 카드를 얼마나 쓰시나요?',
                child: ChoiceChipGroup(
                  itemsPerRow: 2,
                  options: const [
                    '카드 안써요',
                    '30만원 미만',
                    '30~50만원',
                    '50~100만원',
                    '100만원 이상',
                    '잘 모르겠어요',
                  ],
                  selected: input.monthlyCardSpending,
                  onSelected: (v) {
                    notifier.updateMonthlyCardSpending(v);
                    _revealNext(7);
                  },
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[8],
                index: 9,
                title: '마케팅 정보 수신에 동의하실 수 있나요?',
                description: '(마케팅 정보 수신에 따라 받을 수 있는 우대금리를 확인합니다.)',
                child: ChoiceChipGroup(
                  options: _yesNoUnknownOptions,
                  selected: input.marketingConsent,
                  onSelected: (v) {
                    notifier.updateMarketingConsent(v);
                    _revealNext(8);
                  },
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[9],
                index: 10,
                title: '해당 은행 앱을 설치해서 쓰실 수 있나요?',
                description: '(비대면 가입이나 앱 로그인으로 적용받는 우대금리를 확인합니다.)',
                child: ChoiceChipGroup(
                  options: _yesNoUnknownOptions,
                  selected: input.canInstallBankApp,
                  onSelected: (v) {
                    notifier.updateCanInstallBankApp(v);
                    _revealNext(9);
                  },
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[10],
                index: 11,
                title: '비과세종합저축 관련, 해당하는 항목을 모두 선택해주세요.',
                child: CheckboxOptionList(
                  options: _taxExemptOptions,
                  selected: input.taxExemptEligibility,
                  noneOption: '해당없음',
                  onToggle: (v) =>
                      notifier.toggleTaxExemptEligibility(v, noneOption: '해당없음'),
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[11],
                index: 12,
                title: '비과세종합저축으로 이미 가입해서 쓰고 있는 금액이 있나요?',
                child: Row(
                  children: [
                    SizedBox(
                      width: 120,
                      child: TextField(
                        controller: _taxAmountController,
                        keyboardType: TextInputType.number,
                        inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                        textAlign: TextAlign.right,
                        enabled: !input.existingTaxExemptAmountUnknown,
                        decoration: InputDecoration(
                          hintText: '0',
                          filled: true,
                          fillColor: input.existingTaxExemptAmountUnknown
                              ? Colors.grey.shade100
                              : Colors.white,
                          contentPadding: const EdgeInsets.symmetric(
                              horizontal: 14, vertical: 12),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: BorderSide(color: Colors.grey.shade300),
                          ),
                        ),
                        onChanged: notifier.updateExistingTaxExemptAmountText,
                      ),
                    ),
                    const SizedBox(width: 8),
                    const Text('원'),
                    const SizedBox(width: 12),
                    Expanded(
                      child: OptionChip(
                        label: '잘 모르겠어요',
                        selected: input.existingTaxExemptAmountUnknown,
                        onTap: () {
                          _taxAmountController.clear();
                          notifier.setExistingTaxExemptAmountUnknown();
                        },
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              _QuestionBlock(
                key: _questionKeys[12],
                index: 13,
                title: '다음 중 해당하는 항목이 있으신가요?',
                description: '(항목별 우대금리 정보를 확인합니다.)',
                child: CheckboxOptionList(
                  options: _specialHouseholdOptions,
                  selected: input.specialHouseholdTypes,
                  noneOption: '해당없음',
                  onToggle: (v) => notifier.toggleSpecialHouseholdType(
                    v,
                    noneOption: '해당없음',
                  ),
                ),
              ),
              const SizedBox(height: 32),
              Align(
                alignment: Alignment.centerRight,
                child: NextStepButton(
                  enabled: input.isStep2Complete,
                  onPressed: () => context.push(AppRoutes.inputStep3),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

const _fieldLabelStyle = TextStyle(
  fontSize: 14,
  fontWeight: FontWeight.w600,
  color: AppColors.labelPurple,
);

class _QuestionBlock extends StatelessWidget {
  final int index;
  final String title;
  final String? description;
  final Widget child;

  const _QuestionBlock({
    super.key,
    required this.index,
    required this.title,
    this.description,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '$index. $title',
          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
        ),
        if (description != null) ...[
          const SizedBox(height: 2),
          Text(
            description!,
            style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
          ),
        ],
        const SizedBox(height: 12),
        child,
      ],
    );
  }
}

class _DigitField extends StatelessWidget {
  final TextEditingController controller;
  final int maxLength;
  final ValueChanged<String> onChanged;

  const _DigitField({
    required this.controller,
    required this.maxLength,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: TextInputType.number,
      textAlign: TextAlign.center,
      maxLength: maxLength,
      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
      onChanged: onChanged,
      decoration: InputDecoration(
        counterText: '',
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(vertical: 12),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
      ),
    );
  }
}

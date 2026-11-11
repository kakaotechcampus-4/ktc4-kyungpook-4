import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/portfolio_option.dart';
import '../../models/single_plan.dart';
import '../../providers/portfolio_provider.dart';
import '../../providers/result_provider.dart';
import '../../router/app_router.dart';
import '../../services/api_client.dart';
import '../../theme/app_colors.dart';
import '../../utils/currency_formatter.dart';
import '../../widgets/primary_button.dart';
import '../../widgets/product_detail_tile.dart';

/// 사용자가 최종 선택한 포트폴리오의 상세 정보 + 상품별 공식 링크를 보여주고,
/// 만기 캘린더에 저장하러 가는 화면.
class PortfolioDetailScreen extends ConsumerWidget {
  const PortfolioDetailScreen({super.key});

  Future<void> _confirm(
    BuildContext context,
    WidgetRef ref,
    int profileId,
    PortfolioTier tier,
  ) async {
    try {
      final portfolioId = await ApiClient.instance.selectPortfolio(
        profileId: profileId,
        tier: tier,
      );
      ref.read(selectedPortfolioIdProvider.notifier).state = portfolioId;
      if (context.mounted) {
        context.go(AppRoutes.calendar);
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('가입에 실패했습니다: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final singlePlan = ref.watch(singlePlanProvider);
    final selectedTier = ref.watch(selectedTierProvider);
    final recommendation = ref.watch(recommendationProvider);

    return Scaffold(
      body: SafeArea(
        child: recommendation.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) =>
              Center(child: Text('추천을 불러오지 못했습니다: $error')),
          data: (result) {
            final option = result.options.firstWhere(
              (o) => o.tier == selectedTier,
              orElse: () => result.options.first,
            );
            return ListView(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
              children: [
                const Text(
                  '맞춤형 포트폴리오',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 20),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '단일안 적용',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        singlePlanDescription,
                        style: TextStyle(fontSize: 12, color: Colors.black54, height: 1.4),
                      ),
                      const SizedBox(height: 8),
                      if (singlePlan != null)
                        Text(
                          '${singlePlan!.institutionName} ${singlePlan!.productName} 단일 적용시 '
                          '세후 ${CurrencyFormatter.won(singlePlan!.afterTaxInterest)}',
                          style: const TextStyle(fontSize: 14, color: Colors.black87),
                        )
                      else
                        const Text(
                          '주거래은행 정보가 없어 단일안 비교를 표시할 수 없습니다.',
                          style: TextStyle(fontSize: 14, color: Colors.black54),
                        ),
                      if (singlePlan?.exceedsProtection ?? false) ...[
                        const SizedBox(height: 6),
                        const Text(
                          '한 은행에 1억원을 넘게 넣어 초과분은 예금자보호를 받지 못해요',
                          style: TextStyle(fontSize: 12, color: Colors.orange),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.lavender, width: 2),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        option.tier.label,
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        option.tier.description,
                        style: const TextStyle(fontSize: 12, color: Colors.black54, height: 1.4),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        option.extraVsBaseline != null
                            ? '단일안 대비 + ${CurrencyFormatter.won(option.extraVsBaseline!)}'
                            : '단일안과 비교할 주거래은행 정보가 없어요',
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          color: AppColors.accent,
                        ),
                      ),
                      if (option.extraVsSimple != null && option.extraVsSimple! > 0) ...[
                        const SizedBox(height: 4),
                        Text(
                          '단순형 대비 + ${CurrencyFormatter.won(option.extraVsSimple!)}',
                          style: const TextStyle(fontSize: 13, color: AppColors.accent),
                        ),
                      ],
                      const SizedBox(height: 10),
                      Text(
                        '계좌 개설 ${option.newAccountCount}개',
                        style: const TextStyle(fontSize: 13, color: Colors.black54),
                      ),
                      if (option.taxSavingWon > 0) ...[
                        const SizedBox(height: 4),
                        Text(
                          '신협·새마을금고 세금 감면으로 ${CurrencyFormatter.won(option.taxSavingWon)} 절약',
                          style: const TextStyle(fontSize: 13, color: Colors.black54),
                        ),
                      ],
                      if (option.requiredActions.isNotEmpty) ...[
                        const SizedBox(height: 14),
                        const Text(
                          '우대금리를 받으려면 해야 할 일',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 4),
                        for (final action in option.requiredActions)
                          Text(
                            '• $action',
                            style: const TextStyle(fontSize: 13, color: Colors.black87, height: 1.5),
                          ),
                      ],
                      if (option.overComprehensiveTax) ...[
                        const SizedBox(height: 10),
                        const Text(
                          '이자가 연 2천만원을 넘어 금융소득종합과세 대상이 될 수 있어요',
                          style: TextStyle(fontSize: 12, color: Colors.orange),
                        ),
                      ],
                      const SizedBox(height: 20),
                      for (var i = 0; i < option.products.length; i++)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: ProductDetailTile(
                            index: i + 1,
                            product: option.products[i],
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 32),
                PrimaryButton(
                  label: '만기 캘린더에 입력하러 가기',
                  onPressed: () =>
                      _confirm(context, ref, result.profileId, option.tier),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

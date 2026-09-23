import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/portfolio_option.dart';
import '../../providers/result_provider.dart';
import '../../router/app_router.dart';
import '../../theme/app_colors.dart';
import '../../utils/currency_formatter.dart';
import '../../widgets/primary_button.dart';
import '../../widgets/product_detail_tile.dart';

/// 사용자가 최종 선택한 포트폴리오의 상세 정보 + 상품별 공식 링크를 보여주고,
/// 만기 캘린더에 저장하러 가는 화면.
class PortfolioDetailScreen extends ConsumerWidget {
  const PortfolioDetailScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final singlePlan = ref.watch(singlePlanProvider);
    final options = ref.watch(portfolioOptionsProvider);
    final selectedTier = ref.watch(selectedTierProvider);
    final option = options.firstWhere(
      (o) => o.tier == selectedTier,
      orElse: () => options.firstWhere((o) => o.tier == PortfolioTier.balanced),
    );

    return Scaffold(
      body: SafeArea(
        child: ListView(
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
                  const SizedBox(height: 8),
                  Text(
                    '${singlePlan.institutionName} ${singlePlan.productName} 단일 적용시 '
                    '세후 ${CurrencyFormatter.won(singlePlan.afterTaxInterest)}',
                    style: const TextStyle(fontSize: 14, color: Colors.black87),
                  ),
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
                  const SizedBox(height: 8),
                  Text(
                    '단일안 대비 + ${CurrencyFormatter.won(option.vsSingleDiff)}',
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: AppColors.accent,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    '계좌 개설 ${option.newAccountCount}개\n방문 ${option.branchVisitCount}회',
                    style: const TextStyle(fontSize: 13, color: Colors.black54),
                  ),
                  const SizedBox(height: 20),
                  for (var i = 0; i < option.products.length; i++)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: ProductDetailTile(
                        index: i + 1,
                        product: option.products[i],
                        showLink: true,
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 32),
            PrimaryButton(
              label: '만기 캘린더에 입력하러 가기',
              onPressed: () => context.go(AppRoutes.calendar),
            ),
          ],
        ),
      ),
    );
  }
}

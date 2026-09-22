import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/portfolio_option.dart';
import '../../providers/portfolio_provider.dart';
import '../../router/app_router.dart';
import '../../services/api_client.dart';
import '../../theme/app_colors.dart';

class ResultScreen extends ConsumerWidget {
  const ResultScreen({super.key});

  Future<void> _select(BuildContext context, WidgetRef ref, int profileId, PortfolioTier tier) async {
    try {
      final portfolioId = await ApiClient.instance.selectPortfolio(profileId: profileId, tier: tier);
      ref.read(selectedPortfolioIdProvider.notifier).state = portfolioId;
      if (context.mounted) {
        context.go(AppRoutes.calendar);
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('가입에 실패했습니다: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recommendation = ref.watch(recommendationProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('맞춤형 포트폴리오')),
      body: recommendation.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('추천을 불러오지 못했습니다: $error')),
        data: (result) {
          if (result.options.isEmpty) {
            return const Center(child: Text('조건에 맞는 상품을 찾지 못했습니다'));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(20),
            itemCount: result.options.length,
            separatorBuilder: (_, _) => const SizedBox(height: 16),
            itemBuilder: (context, index) {
              final option = result.options[index];
              return _PortfolioOptionCard(
                option: option,
                onSelect: () => _select(context, ref, result.profileId, option.tier),
              );
            },
          );
        },
      ),
    );
  }
}

class _PortfolioOptionCard extends StatelessWidget {
  final PortfolioOption option;
  final VoidCallback onSelect;

  const _PortfolioOptionCard({required this.option, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.lavender.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            option.tier.apiValue,
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppColors.labelPurple),
          ),
          const SizedBox(height: 4),
          Text(option.reason, style: const TextStyle(fontSize: 13, color: AppColors.gray)),
          const SizedBox(height: 12),
          for (final product in option.products) _ProductRow(product: product),
          const Divider(height: 24),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('세후 예상 이자', style: TextStyle(fontWeight: FontWeight.w600)),
              Text(
                '${_formatWon(option.afterTaxTotal)}원',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: onSelect,
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.lavender,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
              ),
              child: const Text('이 조합으로 가입하기'),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProductRow extends StatelessWidget {
  final PortfolioProduct product;

  const _ProductRow({required this.product});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Text(
              '${product.institutionName} · ${product.productName}',
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Text('${product.interestRate}%', style: const TextStyle(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

/// 1234567 -> "1,234,567". API 는 원 단위 정수를 그대로 주므로 만원 단위 포매터는 쓸 수 없다.
String _formatWon(int amount) {
  final text = amount.toString();
  final buffer = StringBuffer();
  for (var i = 0; i < text.length; i++) {
    if (i != 0 && (text.length - i) % 3 == 0) buffer.write(',');
    buffer.write(text[i]);
  }
  return buffer.toString();
}

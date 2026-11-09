import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/portfolio_option.dart';
import '../providers/portfolio_provider.dart';
import '../theme/app_colors.dart';
import '../utils/currency_formatter.dart';
import 'bot_chat_turn.dart';
import 'product_detail_tile.dart';

/// "안정형/단순형/균형형/최대형" 포트폴리오 카드. 선택된 카드만 펼쳐져서
/// 상품 상세와 "왜 이 조합인가요?" 분석을 보여준다.
class PortfolioTierCard extends ConsumerWidget {
  final PortfolioOption option;
  final bool isSelected;
  final VoidCallback onTap;

  const PortfolioTierCard({
    super.key,
    required this.option,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: isSelected
            ? Border.all(color: AppColors.lavender, width: 2)
            : Border.all(color: Colors.black.withValues(alpha: 0.06)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      option.tier.label,
                      style: const TextStyle(
                          fontSize: 20, fontWeight: FontWeight.bold),
                    ),
                  ),
                  _SelectionCircle(isSelected: isSelected),
                ],
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
              const SizedBox(height: 10),
              Text(
                '계좌 개설 ${option.newAccountCount}개',
                style: const TextStyle(fontSize: 13, color: Colors.black54),
              ),
              if (isSelected) ...[
                const SizedBox(height: 20),
                for (var i = 0; i < option.products.length; i++)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: ProductDetailTile(index: i + 1, product: option.products[i]),
                  ),
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      border: Border(
                        top: BorderSide(
                            color: AppColors.gray.withValues(alpha: 0.3)),
                      ),
                    ),
                    child: const SizedBox(height: 1),
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  '포트폴리오 분석',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 4),
                Text(
                  '신규 계좌 ${option.newAccountCount}개',
                  style: const TextStyle(fontSize: 13, color: Colors.black54),
                ),
                const SizedBox(height: 16),
                const Text(
                  '💡 왜 이 조합인가요?',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 6),
                _ReasonText(option: option),
              ],
              const SizedBox(height: 12),
              Center(
                child: Icon(
                  isSelected
                      ? Icons.keyboard_arrow_up
                      : Icons.keyboard_arrow_down,
                  color: AppColors.gray,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// option.reason이 이미 있으면 그걸 쓰고(캐시), 없으면 portfolioReasonsProvider가
/// 들고 올 때까지 "생각하는 중" 표시를 보여준다.
class _ReasonText extends ConsumerWidget {
  final PortfolioOption option;

  const _ReasonText({required this.option});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final reasonsAsync = ref.watch(portfolioReasonsProvider);
    final reason = option.reason ?? reasonsAsync.value?[option.tier.apiValue];

    if (reason != null) {
      return Text(
        reason,
        style: const TextStyle(fontSize: 13, height: 1.5, color: Colors.black87),
      );
    }
    if (reasonsAsync.hasError) {
      return const Text(
        '이유를 불러오지 못했어요.',
        style: TextStyle(fontSize: 13, color: Colors.black54),
      );
    }
    return const ThinkingIndicator();
  }
}

class _SelectionCircle extends StatelessWidget {
  final bool isSelected;

  const _SelectionCircle({required this.isSelected});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 24,
      height: 24,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: isSelected ? AppColors.lavender : Colors.white,
        border: isSelected
            ? null
            : Border.all(color: AppColors.gray.withValues(alpha: 0.4)),
      ),
      child: isSelected
          ? const Icon(Icons.check, size: 16, color: Colors.white)
          : null,
    );
  }
}

import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// 검색 가능한 드롭다운. [selectedValues]가 비어있지 않으면 단일/다중 선택 모두
/// 필드 안에 제거 가능한 칩으로 표시한다. 탭하면 검색창 + 목록 패널이 펼쳐진다.
class SearchableSelectField extends StatefulWidget {
  final String hintText;
  final List<String> options;
  final List<String> selectedValues;
  final bool multiSelect;
  final bool enabled;
  final ValueChanged<String> onSelect;
  final ValueChanged<String>? onRemove;

  const SearchableSelectField({
    super.key,
    required this.hintText,
    required this.options,
    required this.selectedValues,
    required this.onSelect,
    this.onRemove,
    this.multiSelect = false,
    this.enabled = true,
  });

  @override
  State<SearchableSelectField> createState() => _SearchableSelectFieldState();
}

class _SearchableSelectFieldState extends State<SearchableSelectField> {
  final _searchController = TextEditingController();
  bool _expanded = false;
  String _query = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _toggleExpanded() {
    if (!widget.enabled) return;
    setState(() {
      _expanded = !_expanded;
      if (!_expanded) {
        _searchController.clear();
        _query = '';
      }
    });
  }

  void _handleSelect(String value) {
    widget.onSelect(value);
    if (!widget.multiSelect) {
      setState(() {
        _expanded = false;
        _searchController.clear();
        _query = '';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _query.isEmpty
        ? widget.options
        : widget.options
            .where((o) => o.toLowerCase().contains(_query.toLowerCase()))
            .toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildField(),
        if (_expanded) ...[
          const SizedBox(height: 8),
          _buildPanel(filtered),
        ],
      ],
    );
  }

  Widget _buildField() {
    final hasSelection = widget.selectedValues.isNotEmpty;

    return InkWell(
      onTap: _toggleExpanded,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        constraints: const BoxConstraints(minHeight: 52),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: widget.enabled ? Colors.white : Colors.grey.shade100,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: _expanded ? AppColors.lavender : Colors.grey.shade300,
            width: _expanded ? 1.5 : 1,
          ),
        ),
        child: Row(
          children: [
            Expanded(
              child: hasSelection
                  ? Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        for (final value in widget.selectedValues)
                          _SelectedChip(
                            label: value,
                            onRemove: widget.onRemove == null
                                ? null
                                : () => widget.onRemove!(value),
                          ),
                      ],
                    )
                  : Text(
                      widget.hintText,
                      style: TextStyle(fontSize: 15, color: Colors.grey.shade400),
                    ),
            ),
            Icon(
              _expanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
              color: Colors.grey.shade500,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPanel(List<String> filtered) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.grey.shade200),
      ),
      padding: const EdgeInsets.all(10),
      child: Column(
        children: [
          Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.lavender, width: 1.5),
            ),
            child: TextField(
              controller: _searchController,
              autofocus: true,
              onChanged: (v) => setState(() => _query = v),
              decoration: InputDecoration(
                hintText: '검색어를 입력하세요...',
                hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 14),
                suffixIcon: const Icon(Icons.search, size: 20),
                border: InputBorder.none,
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              ),
            ),
          ),
          const SizedBox(height: 4),
          SizedBox(
            height: 200,
            child: filtered.isEmpty
                ? Center(
                    child: Text(
                      '검색 결과가 없어요',
                      style: TextStyle(color: Colors.grey.shade400, fontSize: 13),
                    ),
                  )
                : ListView.separated(
                    itemCount: filtered.length,
                    separatorBuilder: (context, _) =>
                        Divider(height: 1, color: Colors.grey.shade100),
                    itemBuilder: (context, index) {
                      final option = filtered[index];
                      final isSelected = widget.selectedValues.contains(option);
                      return InkWell(
                        onTap: () => _handleSelect(option),
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 12, vertical: 14),
                          child: Text(
                            option,
                            style: TextStyle(
                              fontSize: 14,
                              fontWeight:
                                  isSelected ? FontWeight.w700 : FontWeight.normal,
                              color: isSelected
                                  ? AppColors.labelPurple
                                  : Colors.black87,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _SelectedChip extends StatelessWidget {
  final String label;
  final VoidCallback? onRemove;

  const _SelectedChip({required this.label, this.onRemove});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.only(left: 12, right: 6, top: 6, bottom: 6),
      decoration: BoxDecoration(
        color: AppColors.lavender.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppColors.labelPurple,
            ),
          ),
          if (onRemove != null) ...[
            const SizedBox(width: 4),
            InkWell(
              onTap: onRemove,
              child: const Icon(Icons.close, size: 16, color: AppColors.labelPurple),
            ),
          ],
        ],
      ),
    );
  }
}

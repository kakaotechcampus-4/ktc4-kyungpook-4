import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/bank_options.dart';
import '../models/product_summary.dart';
import '../services/api_client.dart';
import '../theme/app_colors.dart';
import 'primary_button.dart';
import 'searchable_select_field.dart';

/// 상품 정보 기록 제출 콜백. 서버가 entry_id/created_at 을 발급하므로 여기선
/// 입력된 원시 필드만 넘기고, 실제 생성(POST)은 호출하는 쪽(캘린더 화면)이
/// 담당한다. 실패하면 예외를 던져서 폼이 계속 열려있게 한다.
typedef ProductEntrySubmit = Future<void> Function({
  required DateTime date,
  required String institutionName,
  String? productId,
  required String productName,
  required int amount,
  required String memo,
});

/// 상품 정보를 입력받는 폼 본문. 바텀시트 안에 넣을 수도, 전체 화면
/// Scaffold의 body로 넣을 수도 있도록 특정 컨테이너(바텀시트/화면)에
/// 의존하지 않는다 - 지금은 바텀시트에서 쓰고, 입력 항목이 늘어나면
/// 이 위젯을 그대로 풀스크린 화면으로 옮기면 된다.
class ProductEntryForm extends StatefulWidget {
  final DateTime initialDate;
  final ProductEntrySubmit onSubmit;
  final VoidCallback? onCancel;

  const ProductEntryForm({
    super.key,
    required this.initialDate,
    required this.onSubmit,
    this.onCancel,
  });

  @override
  State<ProductEntryForm> createState() => _ProductEntryFormState();
}

class _ProductEntryFormState extends State<ProductEntryForm> {
  late DateTime _date = widget.initialDate;
  String _institutionName = '';
  final _productNameController = TextEditingController();
  final _productNameFocusNode = FocusNode();
  final _amountController = TextEditingController();
  final _memoController = TextEditingController();
  bool _isSubmitting = false;

  List<ProductSummary> _products = const [];
  bool _isLoadingProducts = false;
  String? _selectedProductId;
  String? _selectedProductName;

  @override
  void initState() {
    super.initState();
    _productNameFocusNode.addListener(() {
      if (_productNameFocusNode.hasFocus && _products.isNotEmpty) {
        _openProductPicker();
      }
    });
    _productNameController.addListener(() {
      // 선택해둔 상품명과 다른 텍스트로 바뀌면(직접 수정) product_id는 더 이상
      // 유효하지 않으니 비운다.
      if (_selectedProductId != null &&
          _selectedProductName != _productNameController.text) {
        _selectedProductId = null;
        _selectedProductName = null;
      }
    });
  }

  @override
  void dispose() {
    _productNameController.dispose();
    _productNameFocusNode.dispose();
    _amountController.dispose();
    _memoController.dispose();
    super.dispose();
  }

  Future<void> _onInstitutionSelected(String institution) async {
    setState(() {
      _institutionName = institution;
      _products = const [];
      _selectedProductId = null;
      _selectedProductName = null;
      _productNameController.clear();
      _isLoadingProducts = true;
    });
    try {
      final result = await ApiClient.instance.searchProducts(institution: institution);
      if (!mounted) return;
      setState(() => _products = result.items);
    } catch (_) {
      // 상품 목록 조회가 실패해도 직접 입력으로 계속 쓸 수 있어야 하니
      // 조용히 빈 목록으로 둔다.
      if (!mounted) return;
      setState(() => _products = const []);
    } finally {
      if (mounted) setState(() => _isLoadingProducts = false);
    }
  }

  Future<void> _openProductPicker() async {
    final selected = await showModalBottomSheet<ProductSummary>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => _ProductPickerSheet(products: _products),
    );
    if (!mounted) return;
    // 아무것도 안 고르고 닫았으면(직접 입력하려는 것) 포커스만 유지하고 끝낸다.
    if (selected == null) return;
    setState(() {
      _productNameController.text = selected.productName;
      _selectedProductId = selected.productId;
      _selectedProductName = selected.productName;
    });
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(1900),
      lastDate: DateTime(2200),
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _submit() async {
    if (_isSubmitting) return;
    if (_institutionName.isEmpty) {
      _showMissingFieldMessage('기관을 선택해주세요.');
      return;
    }
    if (_productNameController.text.trim().isEmpty) {
      _showMissingFieldMessage('상품명을 입력해주세요.');
      return;
    }
    if ((int.tryParse(_amountController.text) ?? 0) <= 0) {
      _showMissingFieldMessage('금액을 입력해주세요.');
      return;
    }
    setState(() => _isSubmitting = true);
    try {
      await widget.onSubmit(
        date: _date,
        institutionName: _institutionName,
        productId: _selectedProductId,
        productName: _productNameController.text.trim(),
        amount: int.tryParse(_amountController.text) ?? 0,
        memo: _memoController.text.trim(),
      );
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  void _showMissingFieldMessage(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '상품 정보 기록하기',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 20),
        const _FieldLabel('날짜'),
        const SizedBox(height: 8),
        InkWell(
          onTap: _pickDate,
          borderRadius: BorderRadius.circular(14),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: Row(
              children: [
                Text(
                  '${_date.year}년 ${_date.month}월 ${_date.day}일',
                  style: const TextStyle(fontSize: 15),
                ),
                const Spacer(),
                Icon(Icons.calendar_today_outlined,
                    size: 18, color: Colors.grey.shade500),
              ],
            ),
          ),
        ),
        const SizedBox(height: 20),
        const _FieldLabel('기관'),
        const SizedBox(height: 8),
        SearchableSelectField(
          hintText: '기관을 선택해주세요',
          options: bankOptions,
          selectedValues: _institutionName.isEmpty ? const [] : [_institutionName],
          onSelect: _onInstitutionSelected,
        ),
        const SizedBox(height: 20),
        const _FieldLabel('상품명'),
        const SizedBox(height: 8),
        TextField(
          controller: _productNameController,
          focusNode: _productNameFocusNode,
          enabled: _institutionName.isNotEmpty,
          decoration: _fieldDecoration(
            hintText: _institutionName.isEmpty ? '기관을 먼저 선택해주세요' : '예: 자유적금',
            suffixIcon: _isLoadingProducts
                ? const Padding(
                    padding: EdgeInsets.all(14),
                    child: SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : _products.isEmpty
                    ? null
                    : IconButton(
                        onPressed: _openProductPicker,
                        icon: const Icon(Icons.list, size: 20),
                      ),
          ),
        ),
        const SizedBox(height: 20),
        const _FieldLabel('금액'),
        const SizedBox(height: 8),
        TextField(
          controller: _amountController,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          decoration: _fieldDecoration(hintText: '0', suffixText: '원'),
        ),
        const SizedBox(height: 20),
        const _FieldLabel('메모 (선택)'),
        const SizedBox(height: 8),
        TextField(
          controller: _memoController,
          maxLines: 2,
          decoration: _fieldDecoration(hintText: '예: 만기 자동이체 등록함'),
        ),
        const SizedBox(height: 28),
        PrimaryButton(
          label: _isSubmitting ? '저장 중...' : '기록하기',
          onPressed: _submit,
        ),
      ],
    );
  }

  InputDecoration _fieldDecoration({
    required String hintText,
    String? suffixText,
    Widget? suffixIcon,
  }) {
    return InputDecoration(
      hintText: hintText,
      suffixText: suffixText,
      suffixIcon: suffixIcon,
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: BorderSide(color: Colors.grey.shade300),
      ),
    );
  }
}

class _FieldLabel extends StatelessWidget {
  final String text;

  const _FieldLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        color: AppColors.labelPurple,
      ),
    );
  }
}

/// 기관 선택 후 뜨는 실제 상품 목록 바텀시트. 검색어로 거르고, 고르면 그
/// ProductSummary를 그대로 돌려준다(없으면 닫아서 직접 입력으로 이어간다).
class _ProductPickerSheet extends StatefulWidget {
  final List<ProductSummary> products;

  const _ProductPickerSheet({required this.products});

  @override
  State<_ProductPickerSheet> createState() => _ProductPickerSheetState();
}

class _ProductPickerSheetState extends State<_ProductPickerSheet> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final filtered = _query.isEmpty
        ? widget.products
        : widget.products
            .where((p) => p.productName.toLowerCase().contains(_query.toLowerCase()))
            .toList();

    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '상품 선택',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text(
            '원하는 상품이 없으면 닫고 직접 입력해주세요.',
            style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
          ),
          const SizedBox(height: 16),
          TextField(
            autofocus: true,
            onChanged: (v) => setState(() => _query = v),
            decoration: InputDecoration(
              hintText: '상품명 검색',
              hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 14),
              prefixIcon: const Icon(Icons.search, size: 20),
              filled: true,
              fillColor: Colors.white,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(color: Colors.grey.shade300),
              ),
            ),
          ),
          const SizedBox(height: 8),
          SizedBox(
            height: 320,
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
                      final product = filtered[index];
                      final rate = product.maxRate;
                      return ListTile(
                        onTap: () => Navigator.of(context).pop(product),
                        title: Text(
                          product.productName,
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        subtitle: Text(
                          rate == null
                              ? product.productType
                              : '${product.productType} · 최고 $rate%',
                          style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
                        ),
                        trailing: product.onSale
                            ? null
                            : Text(
                                '판매종료',
                                style: TextStyle(fontSize: 11, color: Colors.grey.shade400),
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

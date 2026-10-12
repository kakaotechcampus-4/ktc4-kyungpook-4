import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/bank_options.dart';
import '../models/manual_product_entry.dart';
import '../theme/app_colors.dart';
import 'primary_button.dart';
import 'searchable_select_field.dart';

/// 상품 정보를 입력받는 폼 본문. 바텀시트 안에 넣을 수도, 전체 화면
/// Scaffold의 body로 넣을 수도 있도록 특정 컨테이너(바텀시트/화면)에
/// 의존하지 않는다 - 지금은 바텀시트에서 쓰고, 입력 항목이 늘어나면
/// 이 위젯을 그대로 풀스크린 화면으로 옮기면 된다.
class ProductEntryForm extends StatefulWidget {
  final DateTime initialDate;
  final ValueChanged<ManualProductEntry> onSubmit;
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
  final _amountController = TextEditingController();
  final _memoController = TextEditingController();

  @override
  void dispose() {
    _productNameController.dispose();
    _amountController.dispose();
    _memoController.dispose();
    super.dispose();
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

  void _submit() {
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
    widget.onSubmit(
      ManualProductEntry(
        id: DateTime.now().microsecondsSinceEpoch.toString(),
        date: _date,
        institutionName: _institutionName,
        productName: _productNameController.text.trim(),
        amount: int.tryParse(_amountController.text) ?? 0,
        memo: _memoController.text.trim(),
      ),
    );
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
          onSelect: (v) => setState(() => _institutionName = v),
        ),
        const SizedBox(height: 20),
        const _FieldLabel('상품명'),
        const SizedBox(height: 8),
        TextField(
          controller: _productNameController,
          decoration: _fieldDecoration(hintText: '예: 자유적금'),
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
          label: '기록하기',
          onPressed: _submit,
        ),
      ],
    );
  }

  InputDecoration _fieldDecoration({required String hintText, String? suffixText}) {
    return InputDecoration(
      hintText: hintText,
      suffixText: suffixText,
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

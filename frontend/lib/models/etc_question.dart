/// 백엔드 POST /profiles/{id}/etc-questions 가 돌려주는 질문 1개.
/// "기타"로 분류돼 정해진 STEP2/3 문항으로는 못 물은 우대조건을, AI가 자연어 질문으로 만든 것.
class EtcQuestion {
  final String question;
  final String evidenceText;

  /// 이 질문의 답을 저장할 조건 ID 묶음. 답 보낼 때 그대로 돌려줘야 한다.
  final List<String> conditionIds;

  const EtcQuestion({
    required this.question,
    required this.evidenceText,
    required this.conditionIds,
  });

  factory EtcQuestion.fromJson(Map<String, dynamic> json) => EtcQuestion(
        question: json['question'] as String,
        evidenceText: json['evidence_text'] as String,
        conditionIds: (json['condition_ids'] as List<dynamic>).cast<String>(),
      );
}

/// POST /profiles/{id}/etc-answers 에 보낼 답 1개.
class EtcAnswerSubmission {
  final List<String> conditionIds;
  final String question;
  final String answer;

  const EtcAnswerSubmission({
    required this.conditionIds,
    required this.question,
    required this.answer,
  });

  Map<String, dynamic> toJson() => {
        'condition_ids': conditionIds,
        'question': question,
        'answer': answer,
      };
}

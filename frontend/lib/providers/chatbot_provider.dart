import 'package:flutter_riverpod/legacy.dart';

import '../models/etc_question.dart';

/// 로딩 화면에서 받아온, 아직 못 물어본 '기타' 우대조건 질문.
/// 비어 있으면 챗봇 화면을 건너뛰고 바로 결과로 간다.
final pendingEtcQuestionsProvider = StateProvider<List<EtcQuestion>>((ref) => []);

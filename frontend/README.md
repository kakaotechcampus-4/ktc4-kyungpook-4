# Frontend

예적금 금리 비교·포트폴리오 추천 서비스의 모바일 앱.

Flutter 3.47 / Dart 3.13

---

## 시작하기

미리 깔아둘 것:

- [Flutter SDK](https://docs.flutter.dev/get-started/install) (stable 채널)
- Android SDK (Android Studio 를 깔면 같이 딸려옵니다) — 실기기/에뮬레이터로 확인하려면 필요

```bash
cd frontend
flutter pub get          # 패키지 설치
flutter doctor            # 환경 점검
```

`flutter doctor` 의 Android toolchain 항목에 라이선스 경고가 뜨면 한 번만 동의합니다.

```bash
flutter doctor --android-licenses
```

그다음 에뮬레이터나 실기기를 연결하고 실행합니다.

```bash
flutter run
```

## 자주 쓰는 명령

| 하려는 것 | 명령 |
|---|---|
| 앱 실행 (핫 리로드) | `flutter run` |
| 정적 분석 (CI 와 동일) | `flutter analyze` |
| 포맷 검사 | `dart format --output=none --set-exit-if-changed .` |
| 포맷 적용 | `dart format .` |
| 테스트 | `flutter test` |
| 패키지 추가 | `flutter pub add <package>` |
| APK 빌드 | `flutter build apk` |

## 아키텍처

- 상태관리: [Riverpod](https://riverpod.dev/)
- 라우팅: [go_router](https://pub.dev/packages/go_router)
- 구조: layer-first (기능별이 아니라 역할별로 폴더를 나눔)

## 폴더 구조

```
frontend/
├── lib/
│   ├── main.dart          앱 진입점 (ProviderScope + MaterialApp.router)
│   ├── router/             go_router 라우트 정의 (AppRoutes 상수 포함)
│   ├── screens/            화면 단위 위젯. 화면별로 하위 폴더
│   │   ├── splash/          스플래시
│   │   ├── loading/         로딩
│   │   ├── calendar/        홈 — 만기 캘린더
│   │   ├── tutorial/        온보딩 튜토리얼
│   │   ├── input/           맞춤 추천 설문 (step 1~3)
│   │   └── result/          포트폴리오 추천 결과
│   ├── widgets/             여러 화면에서 재사용하는 공통 위젯
│   ├── providers/           Riverpod Notifier/Provider
│   ├── models/              화면·API에서 쓰는 데이터 클래스
│   ├── services/            API 클라이언트, 설정값
│   └── utils/               포맷터 등 순수 유틸 함수
├── test/                   위젯/유닛 테스트
├── android/                Android 플랫폼 프로젝트
├── ios/                    iOS 플랫폼 프로젝트
└── pubspec.yaml            의존성 정의
```

새 화면을 추가할 때는 `screens/<화면이름>/` 폴더를 만들고, 필요한 상태는
`providers/`, 재사용 UI는 `widgets/`, 데이터 구조는 `models/`에 둡니다.

> 로그인/마이페이지는 아직 기획이 확정되지 않아 구조에 넣지 않았습니다.
> 확정되면 `screens/` 아래에 폴더만 추가하면 됩니다.

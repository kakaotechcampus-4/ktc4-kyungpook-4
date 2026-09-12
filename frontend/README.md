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

## 폴더 구조

```
frontend/
├── lib/            앱 코드 (진입점: lib/main.dart)
├── test/           위젯/유닛 테스트
├── android/        Android 플랫폼 프로젝트
├── ios/            iOS 플랫폼 프로젝트
└── pubspec.yaml    의존성 정의
```

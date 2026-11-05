import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../router/app_router.dart';
import '../../services/auth_client.dart';
import '../../utils/app_images.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  static const _minimumVisibleDuration = Duration(seconds: 2);

  @override
  void initState() {
    super.initState();
    // 네이티브 스플래시가 걷히고 이 화면이 실제로 화면에 그려진 뒤부터
    // 진행해야, 디버그 빌드의 느린 콜드 스타트 때문에 이 화면이 보이지도
    // 않은 채로 다음 단계가 끝나버리는 문제가 생기지 않는다.
    WidgetsBinding.instance.addPostFrameCallback((_) => _proceed());
  }

  Future<void> _proceed() async {
    // 이미지 디코딩(콜드 스타트에서 수 초 걸릴 수 있다)은 "노출 시간"에
    // 포함시키지 않는다 — 먼저 다 준비해서 완성된 화면을 그린 다음에야
    // 최소 노출 시간을 재기 시작해야, 사용자가 실제로 캐릭터+타이틀이
    // 보이는 화면을 최소 2초 볼 수 있다.
    await _precacheImages();

    // 세션 확인은 최소 노출 시간과 동시에 진행해서, 로그인 돼있는 사용자가
    // 매번 스플래시에서 괜히 더 오래 기다리지 않게 한다.
    final sessionCheck = AuthClient.instance.fetchCurrentUser().catchError((_) => null);
    await Future.delayed(_minimumVisibleDuration);
    final user = await sessionCheck;

    if (!mounted) return;
    context.go(user != null ? AppRoutes.calendar : AppRoutes.login);
  }

  Future<void> _precacheImages() {
    return Future.wait([
      precacheImage(const AssetImage(AppImages.ellipse), context),
      precacheImage(const AssetImage(AppImages.mainpageMascot), context),
      precacheImage(const AssetImage(AppImages.titleIcon), context),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        alignment: Alignment.center,
        children: [
          Image.asset(AppImages.ellipse, fit: BoxFit.contain),
          Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Image.asset(AppImages.mainpageMascot, width: 160),
              const SizedBox(height: 16),
              Image.asset(AppImages.titleIcon, width: 200),
            ],
          ),
        ],
      ),
    );
  }
}

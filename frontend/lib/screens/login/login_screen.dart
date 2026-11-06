import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../router/app_router.dart';
import '../../services/auth_client.dart';
import '../../theme/app_colors.dart';
import '../../utils/app_images.dart';

class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});

  /// 웹은 현재 탭을 백엔드의 로그인 시작 URL로 이동시킨다. fetch 로 호출하면 안 되는
  /// 이유: 이 엔드포인트는 구글/카카오 로그인 화면으로 리다이렉트하는 용도라,
  /// 브라우저가 실제로 그 주소를 따라가야 한다 (XHR/fetch 는 리다이렉트를
  /// 보여주지 못한다). 네이티브는 쿠키 저장소가 없어 외부 브라우저 + PKCE 로
  /// 로그인하고 토큰을 직접 받아오는 별도 경로(loginWithApp)를 탄다.
  Future<void> _startLogin(BuildContext context, SocialProvider provider) async {
    if (kIsWeb) {
      final url = AuthClient.instance.socialLoginUrl(provider, next: AppRoutes.calendar);
      await launchUrl(url, webOnlyWindowName: '_self');
      return;
    }
    try {
      await AuthClient.instance.loginWithApp(provider);
      if (context.mounted) context.go(AppRoutes.calendar);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('로그인에 실패했어요: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            children: [
              const Spacer(flex: 4),
              Image.asset(AppImages.mainpageMascot, width: 160),
              const SizedBox(height: 16),
              Image.asset(AppImages.titleIcon, width: 200),
              const Spacer(flex: 5),
              const Text(
                '로그인',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 20),
              _SocialButton(
                label: '카카오로 계속하기',
                backgroundColor: const Color(0xFFFEE500),
                foregroundColor: Colors.black,
                icon: Image.asset(AppImages.kakaoLogo, width: 20, height: 20),
                onPressed: () => _startLogin(context, SocialProvider.kakao),
              ),
              const SizedBox(height: 12),
              _SocialButton(
                label: '구글로 계속하기',
                backgroundColor: Colors.white,
                foregroundColor: Colors.black,
                borderColor: AppColors.lineGray,
                icon: Image.asset(AppImages.googleLogo, width: 20, height: 20),
                onPressed: () => _startLogin(context, SocialProvider.google),
              ),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }
}

/// 카카오/네이버/구글 버튼이 레이아웃만 다르고 모양은 같아서 공용으로 뺐다.
class _SocialButton extends StatelessWidget {
  final String label;
  final Color backgroundColor;
  final Color foregroundColor;
  final Color? borderColor;
  final Widget icon;
  final VoidCallback onPressed;

  const _SocialButton({
    required this.label,
    required this.backgroundColor,
    required this.foregroundColor,
    required this.icon,
    required this.onPressed,
    this.borderColor,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton(
        onPressed: onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: backgroundColor,
          foregroundColor: foregroundColor,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
            side: borderColor != null
                ? BorderSide(color: borderColor!)
                : BorderSide.none,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            icon,
            const SizedBox(width: 10),
            Text(
              label,
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../../utils/app_images.dart';

class LoadingScreen extends StatelessWidget {
  const LoadingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Image.asset(AppImages.loadingMascot, width: 140),
            const SizedBox(height: 24),
            Image.asset(AppImages.loadingText, height: 20),
            const SizedBox(height: 16),
            Image.asset(AppImages.loadingBar, height: 8),
          ],
        ),
      ),
    );
  }
}

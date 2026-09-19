import 'package:go_router/go_router.dart';

import '../screens/calendar/calendar_screen.dart';
import '../screens/input/input_step1_screen.dart';
import '../screens/input/input_step2_screen.dart';
import '../screens/input/input_step3_screen.dart';
import '../screens/loading/loading_screen.dart';
import '../screens/result/result_screen.dart';
import '../screens/splash/splash_screen.dart';
import '../screens/tutorial/tutorial_screen.dart';

class AppRoutes {
  AppRoutes._();

  static const splash = '/';
  static const loading = '/loading';
  static const calendar = '/calendar';
  static const tutorial = '/tutorial';
  static const inputStep1 = '/input/1';
  static const inputStep2 = '/input/2';
  static const inputStep3 = '/input/3';
  static const result = '/result';
}

final appRouter = GoRouter(
  initialLocation: AppRoutes.splash,
  routes: [
    GoRoute(
      path: AppRoutes.splash,
      builder: (context, state) => const SplashScreen(),
    ),
    GoRoute(
      path: AppRoutes.loading,
      builder: (context, state) => const LoadingScreen(),
    ),
    GoRoute(
      path: AppRoutes.calendar,
      builder: (context, state) => const CalendarScreen(),
    ),
    GoRoute(
      path: AppRoutes.tutorial,
      builder: (context, state) => const TutorialScreen(),
    ),
    GoRoute(
      path: AppRoutes.inputStep1,
      builder: (context, state) => const InputStep1Screen(),
    ),
    GoRoute(
      path: AppRoutes.inputStep2,
      builder: (context, state) => const InputStep2Screen(),
    ),
    GoRoute(
      path: AppRoutes.inputStep3,
      builder: (context, state) => const InputStep3Screen(),
    ),
    GoRoute(
      path: AppRoutes.result,
      builder: (context, state) => const ResultScreen(),
    ),
  ],
);

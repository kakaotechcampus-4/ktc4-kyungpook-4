class CurrentUser {
  final int userId;
  final String nickname;
  final String email;
  final bool isGuest;
  final List<String> providers;

  const CurrentUser({
    required this.userId,
    required this.nickname,
    required this.email,
    required this.isGuest,
    required this.providers,
  });

  factory CurrentUser.fromJson(Map<String, dynamic> json) {
    return CurrentUser(
      userId: json['user_id'] as int,
      nickname: json['nickname'] as String? ?? '',
      email: json['email'] as String? ?? '',
      isGuest: json['is_guest'] as bool,
      providers: (json['providers'] as List<dynamic>? ?? const [])
          .map((e) => e as String)
          .toList(),
    );
  }
}

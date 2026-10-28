#!/usr/bin/env bash
# 팀 서버에서 root 로 실행된다 (GitHub Actions -> SSM send-command).
# 압축을 푼 릴리스 폴더 안의 deploy/deploy.sh 를 그대로 실행하면 된다. 여러 번 돌려도 안전하다.
set -euo pipefail

BASE=/opt/ktc4
SHARED="$BASE/shared"
RELEASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

log() { echo "[deploy] $*"; }

# 1. Docker (처음 한 번만 설치)
if ! command -v docker >/dev/null 2>&1; then
  log "Docker 설치"
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null

# 2. 비밀값. 처음 배포할 때 만들고 이후엔 그대로 쓴다 (DB 비밀번호가 바뀌면 기존 볼륨에 못 붙는다).
mkdir -p "$SHARED"
if [ ! -f "$SHARED/.env" ]; then
  log "$SHARED/.env 생성"
  cat > "$SHARED/.env" <<EOF
ENV=prod
DEBUG=false
POSTGRES_USER=ktc4
POSTGRES_PASSWORD=$(openssl rand -hex 24)
POSTGRES_DB=ktc4
POSTGRES_PORT=5432
REDIS_PORT=6379
REDIS_DB=0
DB_ECHO=false
# 추천 이유 문구(Summary) AI 호출용. 비워두면 계산된 숫자로 만든 기본 문구가 나간다.
OPENAI_API_KEY=
OPENAI_BASE_URL=
EOF
  chmod 600 "$SHARED/.env"
fi
cp "$SHARED/.env" "$RELEASE_DIR/deploy/.env"
chmod 600 "$RELEASE_DIR/deploy/.env"

# 3. 컨테이너 기동 (백엔드는 기동하면서 마이그레이션을 먼저 적용한다)
ln -sfn "$RELEASE_DIR" "$BASE/current"
cd "$BASE/current/deploy"
log "docker compose up"
docker compose up -d --build --remove-orphans

# 도메인을 붙이면 Caddy 는 그 이름으로 온 요청에만 응답하므로, 확인은 백엔드에 직접 한다.
health() {
  docker compose exec -T backend python -c \
    "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/health/db').read().decode())"
}
log "백엔드 응답 대기"
for _ in $(seq 1 60); do
  if health >/dev/null 2>&1; then break; fi
  sleep 2
done
health

# 4. AI 산출물 적재. upsert 라 매번 돌려도 건수가 같다.
log "AI 산출물 적재"
docker compose exec -T backend python -m app.importers.erd_import --erd-dir /data/erd

# 5. DuckDNS IP 자동 갱신 (shared/.env 에 DUCKDNS_DOMAIN·DUCKDNS_TOKEN 이 있을 때만)
#    토큰은 root 만 읽을 수 있는 shared/.env 에만 두고, cron 파일에는 적지 않는다.
cat > "$SHARED/duckdns.sh" <<'EOF'
#!/usr/bin/env bash
set -eu
set -a; . /opt/ktc4/shared/.env; set +a
[ -n "${DUCKDNS_DOMAIN:-}" ] && [ -n "${DUCKDNS_TOKEN:-}" ] || exit 0
curl -fsS "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip="
echo " $(date -Is)"
EOF
chmod 700 "$SHARED/duckdns.sh"
if grep -q '^DUCKDNS_TOKEN=.' "$SHARED/.env"; then
  echo "*/5 * * * * root $SHARED/duckdns.sh >> /var/log/ktc4-duckdns.log 2>&1" > /etc/cron.d/ktc4-duckdns
  log "DuckDNS 갱신: $("$SHARED/duckdns.sh")"
else
  rm -f /etc/cron.d/ktc4-duckdns
fi

# 6. 정리: 최근 릴리스 3개만 남긴다
ls -1dt "$BASE"/releases/* | tail -n +4 | xargs -r rm -rf
docker image prune -f >/dev/null

log "완료: $(basename "$RELEASE_DIR")"

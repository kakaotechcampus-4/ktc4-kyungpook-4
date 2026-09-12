-- ktc4-kyungpook-4 / 금리 비교·포트폴리오 서비스 스키마 (PostgreSQL 14+)
--
-- 실행: psql "$DATABASE_URL" -f backend/db/schema.sql
--
-- 제약조건 이름은 app/db/base.py 의 NAMING_CONVENTION 과 동일한 규칙을 따른다.
-- (pk_/fk_/uq_/ck_/ix_) 나중에 alembic autogenerate 를 붙여도 이름이 어긋나지 않는다.
--
-- [배치 갱신 정책] 상품 데이터는 덮어쓰기다(이력을 쌓지 않는다).
--   단 DELETE + INSERT 로 돌리면 안 된다. user_holding 이 물고 있는 링크가 매 배치마다 끊긴다.
--   product / product_option / product_condition 은 PK 가 결정적으로 생성되는 varchar 이므로
--   반드시 INSERT ... ON CONFLICT (pk) DO UPDATE (upsert) 로 갱신한다.

BEGIN;

-- ============================================================
-- 0. 금융기관 마스터
-- ============================================================

CREATE TABLE institution (
    institution_code varchar(20)  NOT NULL,
    name             varchar(100) NOT NULL,
    institution_type varchar(20)  NOT NULL,
    region           varchar(50),
    is_active        boolean      NOT NULL DEFAULT true,

    CONSTRAINT pk_institution PRIMARY KEY (institution_code),
    CONSTRAINT uq_institution_name UNIQUE (name),
    CONSTRAINT ck_institution_institution_type
        CHECK (institution_type IN ('은행', '저축은행', '신협'))
);

COMMENT ON TABLE  institution IS '금융기관 마스터. 기관을 가리키는 모든 곳은 이름이 아니라 이 코드를 쓴다';
COMMENT ON COLUMN institution.institution_code IS '금감원 금융회사코드(fin_co_no). 공시에 없는 기관은 자체 코드 부여';
COMMENT ON COLUMN institution.name IS '정식 명칭 1개. 표기 변형은 institution_alias 로 흡수한다';
COMMENT ON COLUMN institution.region IS '지역은행·신협의 영업 지역. 전국구면 NULL';


CREATE TABLE institution_alias (
    id               bigint       GENERATED ALWAYS AS IDENTITY,
    institution_code varchar(20)  NOT NULL,
    alias            varchar(100) NOT NULL,

    CONSTRAINT pk_institution_alias PRIMARY KEY (id),
    CONSTRAINT fk_institution_alias_institution_code_institution
        FOREIGN KEY (institution_code) REFERENCES institution (institution_code)
        ON DELETE CASCADE,
    -- 한 표기가 두 기관을 가리키면 매칭이 불가능해진다
    CONSTRAINT uq_institution_alias_alias UNIQUE (alias)
);

COMMENT ON TABLE institution_alias IS
    '크롤링 문자열을 코드로 되돌리는 사전. "KB국민", "국민은행", "국민" 을 모두 같은 코드로 보낸다';


-- ============================================================
-- 1. 사용자 / 인증
-- ============================================================

CREATE TABLE app_user (
    user_id            bigint      GENERATED ALWAYS AS IDENTITY,
    nickname           varchar(50) NOT NULL,
    email              varchar(255),
    marketing_consent  boolean     NOT NULL DEFAULT false,
    consent_updated_at timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT pk_app_user PRIMARY KEY (user_id)
);

COMMENT ON TABLE  app_user IS '서비스 계정. 소셜 로그인으로만 생성된다';
COMMENT ON COLUMN app_user.email IS '대표 이메일. 소셜사가 미제공하면 NULL';
COMMENT ON COLUMN app_user.marketing_consent IS
    '계정 단위 마케팅 동의. 법적 기준은 이 값이며 user_profile 쪽은 조회 시점 기록일 뿐이다';
COMMENT ON COLUMN app_user.consent_updated_at IS '마케팅 동의를 마지막으로 변경한 시각';

-- 이메일은 소셜사마다 중복될 수 있어 UNIQUE 를 걸지 않는다. 조회용 인덱스만 둔다.
CREATE INDEX ix_app_user_email ON app_user (email) WHERE email IS NOT NULL;


CREATE TABLE social_account (
    social_id        bigint       GENERATED ALWAYS AS IDENTITY,
    user_id          bigint       NOT NULL,
    provider         varchar(20)  NOT NULL,
    provider_user_id varchar(255) NOT NULL,
    provider_email   varchar(255),
    linked_at        timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT pk_social_account PRIMARY KEY (social_id),
    CONSTRAINT fk_social_account_user_id_app_user
        FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE,
    CONSTRAINT ck_social_account_provider
        CHECK (provider IN ('GOOGLE', 'KAKAO', 'NAVER')),
    -- 같은 소셜 계정이 두 명에게 붙는 것을 막는다 (로그인 식별의 근거)
    CONSTRAINT uq_social_account_provider
        UNIQUE (provider, provider_user_id),
    -- 한 사용자가 같은 provider 를 두 번 연결하지 못하게 한다
    CONSTRAINT uq_social_account_user_id
        UNIQUE (user_id, provider)
);

COMMENT ON TABLE  social_account IS '소셜 로그인 연결. 한 계정에 여러 provider 연결 가능';
COMMENT ON COLUMN social_account.provider_user_id IS '소셜사가 발급한 고유 ID (sub/id)';


-- ============================================================
-- 2. 조회 프로필 (한 번의 상담 = 한 행)
-- ============================================================

CREATE TABLE user_profile (
    profile_id           bigint      GENERATED ALWAYS AS IDENTITY,
    user_id              bigint      NOT NULL,
    capital              bigint      NOT NULL DEFAULT 0,
    monthly_saving       bigint      NOT NULL DEFAULT 0,
    period_months        int         NOT NULL,
    withdraw_flexibility varchar(20),
    main_bank_code       varchar(20),
    region               varchar(50),
    birth_date           date,
    salary_transfer      boolean,
    auto_transfer        boolean,
    monthly_card_usage   bigint,
    marketing_consent    boolean     NOT NULL DEFAULT false,
    app_install          boolean,
    accepts_membership   boolean,
    tax_exempt_used      bigint      NOT NULL DEFAULT 0,
    created_at           timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT pk_user_profile PRIMARY KEY (profile_id),
    CONSTRAINT fk_user_profile_user_id_app_user
        FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_profile_main_bank_code_institution
        FOREIGN KEY (main_bank_code) REFERENCES institution (institution_code)
        ON DELETE SET NULL,
    CONSTRAINT ck_user_profile_period_months
        CHECK (period_months > 0),
    CONSTRAINT ck_user_profile_amounts
        CHECK (capital >= 0 AND monthly_saving >= 0 AND tax_exempt_used >= 0
               AND (monthly_card_usage IS NULL OR monthly_card_usage >= 0)),
    -- 목돈도 월 저축액도 0 이면 배분할 게 없다
    CONSTRAINT ck_user_profile_has_money
        CHECK (capital > 0 OR monthly_saving > 0)
);

COMMENT ON TABLE  user_profile IS '조회 1건의 입력값 스냅샷. 사용자가 다시 조회하면 새 행이 쌓인다';
COMMENT ON COLUMN user_profile.withdraw_flexibility IS '중도인출 가능성. 값 집합은 기획 확정 후 CHECK 추가';
COMMENT ON COLUMN user_profile.birth_date IS '만 나이 계산에 필요해 원본 보관. 청년·노인 우대조건 판정에 쓴다';
COMMENT ON COLUMN user_profile.salary_transfer IS 'NULL = 아직 물어보지 않음 / 확인 불가';
COMMENT ON COLUMN user_profile.marketing_consent IS
    '이 조회 건에서 받은 동의 기록. 계정 단위 최신 동의는 app_user.marketing_consent 를 본다';
COMMENT ON COLUMN user_profile.accepts_membership IS
    '신협·새마을금고 조합원 가입(출자금 납입) 의향. 예탁금 가입 자격 판정에 쓴다. NULL = 미확인';
COMMENT ON COLUMN user_profile.tax_exempt_used IS '올해 이미 사용한 비과세 한도(원)';

CREATE INDEX ix_user_profile_user_id ON user_profile (user_id, created_at DESC);


CREATE TABLE user_profile_bank (
    id               bigint      GENERATED ALWAYS AS IDENTITY,
    profile_id       bigint      NOT NULL,
    institution_code varchar(20) NOT NULL,

    CONSTRAINT pk_user_profile_bank PRIMARY KEY (id),
    CONSTRAINT fk_user_profile_bank_profile_id_user_profile
        FOREIGN KEY (profile_id) REFERENCES user_profile (profile_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_profile_bank_institution_code_institution
        FOREIGN KEY (institution_code) REFERENCES institution (institution_code),
    CONSTRAINT uq_user_profile_bank_profile_id UNIQUE (profile_id, institution_code)
);

COMMENT ON TABLE user_profile_bank IS '보유(거래 가능) 은행 복수선택';


CREATE TABLE user_profile_tax_exempt (
    id         bigint      GENERATED ALWAYS AS IDENTITY,
    profile_id bigint      NOT NULL,
    category   varchar(50) NOT NULL,

    CONSTRAINT pk_user_profile_tax_exempt PRIMARY KEY (id),
    CONSTRAINT fk_user_profile_tax_exempt_profile_id_user_profile
        FOREIGN KEY (profile_id) REFERENCES user_profile (profile_id) ON DELETE CASCADE,
    CONSTRAINT uq_user_profile_tax_exempt_profile_id UNIQUE (profile_id, category)
);

COMMENT ON TABLE user_profile_tax_exempt IS '비과세 대상 항목 복수선택 (청년/노인/장애인 등)';


CREATE TABLE user_profile_social (
    id         bigint      GENERATED ALWAYS AS IDENTITY,
    profile_id bigint      NOT NULL,
    category   varchar(20) NOT NULL,

    CONSTRAINT pk_user_profile_social PRIMARY KEY (id),
    CONSTRAINT fk_user_profile_social_profile_id_user_profile
        FOREIGN KEY (profile_id) REFERENCES user_profile (profile_id) ON DELETE CASCADE,
    CONSTRAINT ck_user_profile_social_category
        CHECK (category IN ('다자녀', '한부모', '다문화', '신혼부부', '탈북자')),
    CONSTRAINT uq_user_profile_social_profile_id UNIQUE (profile_id, category)
);

COMMENT ON TABLE user_profile_social IS '사회적 배려 대상 복수선택. 우대금리 가산 판단에 쓴다';


CREATE TABLE user_profile_extra (
    id             bigint      GENERATED ALWAYS AS IDENTITY,
    profile_id     bigint      NOT NULL,
    condition_type varchar(50) NOT NULL,
    question_text  text        NOT NULL,
    answer_value   varchar(255),
    answered_at    timestamptz,

    CONSTRAINT pk_user_profile_extra PRIMARY KEY (id),
    CONSTRAINT fk_user_profile_extra_profile_id_user_profile
        FOREIGN KEY (profile_id) REFERENCES user_profile (profile_id) ON DELETE CASCADE,
    -- 답을 받았으면 시각도 있어야 한다
    CONSTRAINT ck_user_profile_extra_answered
        CHECK (answer_value IS NULL OR answered_at IS NOT NULL)
);

COMMENT ON TABLE  user_profile_extra IS '고정 문항으로 못 채운 우대조건을 챗봇이 되물은 기록';
COMMENT ON COLUMN user_profile_extra.condition_type IS
    'product_condition.condition_type 과 반드시 같은 어휘를 쓴다. 어긋나면 우대금리가 조용히 누락된다';

CREATE INDEX ix_user_profile_extra_profile_id ON user_profile_extra (profile_id);


-- ============================================================
-- 3. 배치 / 수집 파이프라인
-- ============================================================

CREATE TABLE batch_run (
    run_id          bigint      GENERATED ALWAYS AS IDENTITY,
    batch_type      varchar(20) NOT NULL,
    status          varchar(20) NOT NULL DEFAULT 'RUNNING',
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    processed_count int         NOT NULL DEFAULT 0,
    failed_count    int         NOT NULL DEFAULT 0,
    error_message   text,

    CONSTRAINT pk_batch_run PRIMARY KEY (run_id),
    CONSTRAINT ck_batch_run_batch_type
        CHECK (batch_type IN ('COLLECT', 'CRAWL', 'VERIFY', 'PARSE', 'MATURITY')),
    CONSTRAINT ck_batch_run_status
        CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL')),
    CONSTRAINT ck_batch_run_counts
        CHECK (processed_count >= 0 AND failed_count >= 0),
    CONSTRAINT ck_batch_run_finished_at
        CHECK (finished_at IS NULL OR finished_at >= started_at),
    -- 종료 상태인데 finished_at 이 비어 있으면 모니터링이 깨진다
    CONSTRAINT ck_batch_run_terminal
        CHECK (status = 'RUNNING' OR finished_at IS NOT NULL)
);

COMMENT ON TABLE  batch_run IS '배치 실행 1회. 수집된 모든 행이 이 run_id 를 들고 다녀 추적 단위가 된다';
COMMENT ON COLUMN batch_run.status IS 'RUNNING 은 시작 시점에 행을 먼저 넣기 위해 추가한 값';
COMMENT ON COLUMN batch_run.batch_type IS
    'MATURITY = 만기일 지난 user_holding 을 만기 처리하는 일배치. 사용자 접속과 무관하게 돌아야 한다';

CREATE INDEX ix_batch_run_batch_type ON batch_run (batch_type, started_at DESC);


CREATE TABLE crawl_history (
    id           bigint        GENERATED ALWAYS AS IDENTITY,
    run_id       bigint        NOT NULL,
    source_type  varchar(50)   NOT NULL,
    source_url   varchar(1000) NOT NULL,
    page_hash    varchar(64)   NOT NULL,
    has_offer    boolean       NOT NULL DEFAULT false,
    processed_at timestamptz   NOT NULL DEFAULT now(),

    CONSTRAINT pk_crawl_history PRIMARY KEY (id),
    CONSTRAINT fk_crawl_history_run_id_batch_run
        FOREIGN KEY (run_id) REFERENCES batch_run (run_id) ON DELETE CASCADE
);

COMMENT ON TABLE  crawl_history IS '크롤링한 게시글 1건. 같은 글을 다음 배치에서 또 봐도 행은 새로 쌓인다';
COMMENT ON COLUMN crawl_history.page_hash IS '본문 SHA-256. 이전 run 과 같은 해시면 파싱을 건너뛴다';

-- run 간 재수집을 허용해야 하므로 UNIQUE 가 아니라 조회용 인덱스로 둔다
CREATE INDEX ix_crawl_history_page_hash ON crawl_history (page_hash);
CREATE INDEX ix_crawl_history_run_id    ON crawl_history (run_id);


CREATE TABLE special_offer (
    offer_id               varchar(64)  NOT NULL,
    run_id                 bigint       NOT NULL,
    crawl_history_id       bigint,

    -- 커뮤니티가 "주장"하는 값 (아직 신뢰하지 않는다)
    claimed_institution    varchar(100) NOT NULL,
    institution_type       varchar(20),
    product_type           varchar(20),
    claimed_product_name   varchar(200),
    claimed_base_rate      numeric(5, 2),
    claimed_max_rate       numeric(5, 2),
    raw_html               text,
    source_type            varchar(20),
    source_url             varchar(1000),

    -- 은행 사이트에서 확인한 값
    institution_code       varchar(20),
    matched_product_name   varchar(200),
    verified_amount_cap    bigint,
    verified_terms_text    text,
    verify_source_url      varchar(1000),

    verification_status    varchar(20)  NOT NULL DEFAULT 'PENDING',
    rejected_reason        varchar(200),
    verify_attempt_count   int          NOT NULL DEFAULT 0,
    last_verify_at         timestamptz,
    discovered_at          timestamptz  NOT NULL DEFAULT now(),
    verified_at            timestamptz,

    CONSTRAINT pk_special_offer PRIMARY KEY (offer_id),
    CONSTRAINT fk_special_offer_run_id_batch_run
        FOREIGN KEY (run_id) REFERENCES batch_run (run_id) ON DELETE CASCADE,
    CONSTRAINT fk_special_offer_crawl_history_id_crawl_history
        FOREIGN KEY (crawl_history_id) REFERENCES crawl_history (id) ON DELETE SET NULL,
    CONSTRAINT fk_special_offer_institution_code_institution
        FOREIGN KEY (institution_code) REFERENCES institution (institution_code),
    CONSTRAINT ck_special_offer_institution_type
        CHECK (institution_type IS NULL OR institution_type IN ('은행', '저축은행', '신협')),
    CONSTRAINT ck_special_offer_product_type
        CHECK (product_type IS NULL OR product_type IN ('예금', '적금', '예탁금')),
    CONSTRAINT ck_special_offer_source_type
        CHECK (source_type IS NULL OR source_type IN ('지역은행공식', '커뮤니티')),
    CONSTRAINT ck_special_offer_verification_status
        CHECK (verification_status IN ('PENDING', 'VERIFIED', 'REJECTED')),
    CONSTRAINT ck_special_offer_rates
        CHECK ((claimed_base_rate IS NULL OR claimed_base_rate >= 0)
           AND (claimed_max_rate IS NULL OR claimed_base_rate IS NULL
                OR claimed_max_rate >= claimed_base_rate)),
    -- 검증 통과했다면 근거(기관 코드·시각·출처)가 반드시 남아 있어야 한다.
    -- 확인 금리는 special_offer_option 에 있어 여기서 CHECK 로 막지 못한다 (승격 배치가 검사한다).
    CONSTRAINT ck_special_offer_verified_evidence
        CHECK (verification_status <> 'VERIFIED'
               OR (verified_at IS NOT NULL
                   AND verify_source_url IS NOT NULL AND institution_code IS NOT NULL)),
    CONSTRAINT ck_special_offer_rejected_reason
        CHECK (verification_status <> 'REJECTED' OR rejected_reason IS NOT NULL),
    CONSTRAINT ck_special_offer_verify_attempt_count
        CHECK (verify_attempt_count >= 0)
);

COMMENT ON TABLE  special_offer IS '커뮤니티/지역은행에서 발견한 특판 후보. 검증 전에는 사용자에게 노출하지 않는다';
COMMENT ON COLUMN special_offer.offer_id IS '출처 URL + 상품명 해시 등으로 만든 애플리케이션 발급 ID';
COMMENT ON COLUMN special_offer.crawl_history_id IS '이 특판을 발견한 크롤링 건. 원문 추적용';
COMMENT ON COLUMN special_offer.claimed_institution IS
    '커뮤니티 글에 적힌 기관명 원문. 검증 단계에서 institution_alias 로 코드를 찾아 붙인다';
COMMENT ON COLUMN special_offer.institution_code IS '기관 매칭에 성공한 뒤 채워진다. NULL 이면 아직 미해결';
COMMENT ON COLUMN special_offer.claimed_max_rate IS '커뮤니티 글이 주장한 금리. 검증 전 값이라 노출 금지';

CREATE INDEX ix_special_offer_verification_status
    ON special_offer (verification_status, discovered_at DESC);
CREATE INDEX ix_special_offer_run_id ON special_offer (run_id);


CREATE TABLE special_offer_option (
    offer_option_id varchar(96)   NOT NULL,
    offer_id        varchar(64)   NOT NULL,
    period_months   int           NOT NULL,
    rate_type       varchar(10)   NOT NULL DEFAULT '단리',
    reserve_type    varchar(20)   NOT NULL DEFAULT '해당없음',
    base_rate       numeric(5, 2) NOT NULL,
    max_rate        numeric(5, 2) NOT NULL,

    CONSTRAINT pk_special_offer_option PRIMARY KEY (offer_option_id),
    CONSTRAINT fk_special_offer_option_offer_id_special_offer
        FOREIGN KEY (offer_id) REFERENCES special_offer (offer_id) ON DELETE CASCADE,
    CONSTRAINT uq_special_offer_option_offer_id
        UNIQUE (offer_id, period_months, rate_type, reserve_type),
    CONSTRAINT ck_special_offer_option_period_months
        CHECK (period_months > 0),
    CONSTRAINT ck_special_offer_option_rate_type
        CHECK (rate_type IN ('단리', '복리')),
    CONSTRAINT ck_special_offer_option_reserve_type
        CHECK (reserve_type IN ('해당없음', '정액적립식', '자유적립식')),
    CONSTRAINT ck_special_offer_option_rates
        CHECK (base_rate >= 0 AND max_rate >= base_rate)
);

COMMENT ON TABLE  special_offer_option IS
    '은행 사이트에서 확인한 특판의 기간별 금리. 특판도 12/24개월 식으로 여러 기간을 줄 수 있다';
COMMENT ON COLUMN special_offer_option.offer_option_id IS
    'offer_id + 기간 + 이자방식 조합. 승격 시 product_option 으로 1:1 옮겨간다';

CREATE INDEX ix_special_offer_option_offer_id ON special_offer_option (offer_id);


-- ============================================================
-- 4. 상품 / 기간옵션 / 우대조건
-- ============================================================

CREATE TABLE product (
    product_id       varchar(64)  NOT NULL,
    offer_id         varchar(64),
    run_id           bigint,
    source           varchar(10)  NOT NULL,
    institution_code varchar(20)  NOT NULL,
    product_name     varchar(200) NOT NULL,
    product_type     varchar(20)  NOT NULL,
    amount_min       bigint,
    amount_cap       bigint,
    monthly_min      bigint,
    monthly_cap      bigint,
    terms_text       text,
    region           varchar(50),
    join_channel     varchar(20),
    membership_required boolean   NOT NULL DEFAULT false,
    new_customer_only   boolean   NOT NULL DEFAULT false,
    min_age          int,
    max_age          int,
    parse_status     varchar(10)  NOT NULL DEFAULT 'PENDING',
    snapshot_date    date         NOT NULL DEFAULT CURRENT_DATE,
    sale_end_date    date,
    is_active        boolean      NOT NULL DEFAULT true,

    CONSTRAINT pk_product PRIMARY KEY (product_id),
    CONSTRAINT fk_product_offer_id_special_offer
        FOREIGN KEY (offer_id) REFERENCES special_offer (offer_id) ON DELETE SET NULL,
    -- 배치 기록을 정리해도 상품은 남아야 한다 (전에는 CASCADE 라 통째로 삭제됐다)
    CONSTRAINT fk_product_run_id_batch_run
        FOREIGN KEY (run_id) REFERENCES batch_run (run_id) ON DELETE SET NULL,
    CONSTRAINT fk_product_institution_code_institution
        FOREIGN KEY (institution_code) REFERENCES institution (institution_code),
    -- 특판 1건은 상품 1건으로만 승격된다
    CONSTRAINT uq_product_offer_id UNIQUE (offer_id),
    CONSTRAINT ck_product_source
        CHECK (source IN ('OFFICIAL', 'SPECIAL')),
    -- OFFICIAL 은 금감원 공시, SPECIAL 은 반드시 원본 특판을 갖는다
    CONSTRAINT ck_product_source_offer
        CHECK ((source = 'SPECIAL' AND offer_id IS NOT NULL)
            OR (source = 'OFFICIAL' AND offer_id IS NULL)),
    CONSTRAINT ck_product_product_type
        CHECK (product_type IN ('예금', '적금', '예탁금')),
    CONSTRAINT ck_product_join_channel
        CHECK (join_channel IS NULL OR join_channel IN ('비대면', '영업점', '전체')),
    CONSTRAINT ck_product_parse_status
        CHECK (parse_status IN ('PENDING', 'PARSED', 'FAILED')),
    CONSTRAINT ck_product_amounts
        CHECK ((amount_min  IS NULL OR amount_min  > 0)
           AND (amount_cap  IS NULL OR amount_cap  > 0)
           AND (monthly_min IS NULL OR monthly_min > 0)
           AND (monthly_cap IS NULL OR monthly_cap > 0)
           AND (amount_min  IS NULL OR amount_cap  IS NULL OR amount_min  <= amount_cap)
           AND (monthly_min IS NULL OR monthly_cap IS NULL OR monthly_min <= monthly_cap)),
    -- 월 납입 한도는 적금에만 있다. 예금·예탁금은 목돈을 한 번에 넣는다.
    CONSTRAINT ck_product_monthly_only_savings
        CHECK (product_type = '적금' OR (monthly_min IS NULL AND monthly_cap IS NULL)),
    CONSTRAINT ck_product_age
        CHECK ((min_age IS NULL OR min_age >= 0)
           AND (max_age IS NULL OR max_age >= 0)
           AND (min_age IS NULL OR max_age IS NULL OR min_age <= max_age))
);

COMMENT ON TABLE  product IS
    '상품 기본정보(금감원 baseList 에 대응). 금리는 기간마다 달라서 product_option 이 들고 있다';
COMMENT ON COLUMN product.product_id IS
    '공시 = 금융회사코드 + 상품코드 조합, 특판 = ''SP-'' || offer_id. 배치 간 안정적이어야 한다';
COMMENT ON COLUMN product.terms_text IS '우대조건 파싱(LLM)의 입력 원문';
COMMENT ON COLUMN product.amount_min IS '최소 가입금액(예금) / 최소 총 납입액(적금)';
COMMENT ON COLUMN product.amount_cap IS '최대 가입금액(예금) / 최대 총 납입액(적금)';
COMMENT ON COLUMN product.monthly_min IS '적금 월 최소 납입액. 예금은 NULL';
COMMENT ON COLUMN product.monthly_cap IS
    '적금 월 최대 납입액. 총 한도와 별개다 - 이걸 모르면 월 배분액이 한도를 넘는 배분안이 나온다';
COMMENT ON COLUMN product.membership_required IS
    '조합원 가입(출자금)이 있어야 가입 가능. 신협·새마을금고 예탁금. 우대조건이 아니라 자격이다';
COMMENT ON COLUMN product.new_customer_only IS '해당 기관 신규 고객 전용';
COMMENT ON COLUMN product.min_age IS '가입 가능 최소 만 나이. 청년 전용 상품 등';
COMMENT ON COLUMN product.max_age IS '가입 가능 최대 만 나이';
COMMENT ON COLUMN product.snapshot_date IS '이 상품 정보가 유효한 기준일. 지난 날짜면 재조회 대상';
COMMENT ON COLUMN product.sale_end_date IS
    '판매 종료 예정일. 특판은 채워지고 공시 상품은 대개 NULL - 그쪽은 snapshot_date 가 오래되면 사라진 것으로 본다';
COMMENT ON COLUMN product.is_active IS
    '추천 후보에서 뺄 때 쓴다. 행을 지우면 가입자의 금리 근거가 끊기므로 삭제 대신 이 값을 내린다';

CREATE INDEX ix_product_product_type
    ON product (product_type) WHERE parse_status = 'PARSED' AND is_active;
CREATE INDEX ix_product_institution_code ON product (institution_code);
CREATE INDEX ix_product_snapshot_date    ON product (snapshot_date);
CREATE INDEX ix_product_run_id           ON product (run_id);


CREATE TABLE product_option (
    option_id     varchar(96)  NOT NULL,
    product_id    varchar(64)  NOT NULL,
    period_months int          NOT NULL,
    rate_type     varchar(10)  NOT NULL DEFAULT '단리',
    reserve_type  varchar(20)  NOT NULL DEFAULT '해당없음',
    base_rate     numeric(5, 2) NOT NULL,
    max_rate      numeric(5, 2) NOT NULL,

    CONSTRAINT pk_product_option PRIMARY KEY (option_id),
    CONSTRAINT fk_product_option_product_id_product
        FOREIGN KEY (product_id) REFERENCES product (product_id) ON DELETE CASCADE,
    -- 같은 상품에 (기간, 이자방식, 적립방식) 이 겹치는 옵션은 없다
    CONSTRAINT uq_product_option_product_id
        UNIQUE (product_id, period_months, rate_type, reserve_type),
    CONSTRAINT ck_product_option_period_months
        CHECK (period_months > 0),
    CONSTRAINT ck_product_option_rate_type
        CHECK (rate_type IN ('단리', '복리')),
    CONSTRAINT ck_product_option_reserve_type
        CHECK (reserve_type IN ('해당없음', '정액적립식', '자유적립식')),
    CONSTRAINT ck_product_option_rates
        CHECK (base_rate >= 0 AND max_rate >= base_rate)
);

COMMENT ON TABLE  product_option IS
    '저축기간별 금리(금감원 optionList 에 대응). 추천·포트폴리오가 실제로 고르는 단위';
COMMENT ON COLUMN product_option.option_id IS
    'product_id + 기간 + 이자방식 조합으로 결정적으로 생성. 배치가 upsert 해도 user_holding 링크가 유지된다';
COMMENT ON COLUMN product_option.reserve_type IS
    '적금의 적립 방식. 예금은 ''해당없음''. NULL 을 쓰면 UNIQUE 가 중복을 못 막아서 기본값을 둔다';

CREATE INDEX ix_product_option_product_id ON product_option (product_id);
CREATE INDEX ix_product_option_period_months ON product_option (period_months, max_rate DESC);


CREATE TABLE product_condition (
    condition_id        varchar(64)  NOT NULL,
    product_id          varchar(64)  NOT NULL,
    condition_type      varchar(50)  NOT NULL,
    rate_bonus          numeric(4, 2) NOT NULL DEFAULT 0,
    threshold_value     bigint,
    threshold_unit      varchar(10),
    applies_period_min  int,
    applies_period_max  int,
    exclusive_group     varchar(50),
    evidence_text       text,
    evidence_url        varchar(1000),
    verification_status varchar(10),
    confidence_badge    varchar(10)  NOT NULL DEFAULT '검수대기',

    CONSTRAINT pk_product_condition PRIMARY KEY (condition_id),
    CONSTRAINT fk_product_condition_product_id_product
        FOREIGN KEY (product_id) REFERENCES product (product_id) ON DELETE CASCADE,
    CONSTRAINT ck_product_condition_threshold_unit
        CHECK (threshold_unit IS NULL OR threshold_unit IN ('KRW', 'COUNT', 'MONTH')),
    -- 임계값과 단위는 항상 짝으로 채워진다
    CONSTRAINT ck_product_condition_threshold_pair
        CHECK ((threshold_value IS NULL) = (threshold_unit IS NULL)),
    CONSTRAINT ck_product_condition_applies_period
        CHECK (applies_period_min IS NULL OR applies_period_max IS NULL
               OR applies_period_min <= applies_period_max),
    CONSTRAINT ck_product_condition_rate_bonus
        CHECK (rate_bonus >= 0),
    CONSTRAINT ck_product_condition_verification_status
        CHECK (verification_status IS NULL
               OR verification_status IN ('EXACT', 'MISSING', 'EXCESS')),
    CONSTRAINT ck_product_condition_confidence_badge
        CHECK (confidence_badge IN ('확인됨', '검수대기'))
);

COMMENT ON TABLE  product_condition IS
    '약관에서 뽑아낸 우대조건 1개. 기간 제한은 applies_period_* 로 표현하므로 상품 단위로 붙인다';
COMMENT ON COLUMN product_condition.condition_type IS
    '닫힌 어휘 목록 확정 필요. user_profile_extra.condition_type 과 같은 값을 써야 매칭이 된다';
COMMENT ON COLUMN product_condition.exclusive_group IS '같은 그룹의 조건은 하나만 적용된다 (택1 우대)';
COMMENT ON COLUMN product_condition.evidence_text IS '가산 근거가 된 약관 원문 인용. 사용자에게 그대로 보여준다';
COMMENT ON COLUMN product_condition.verification_status IS
    '파싱 결과와 약관 대조 결과. EXCESS = 약관에 없는 조건을 만들어냄';

CREATE INDEX ix_product_condition_product_id ON product_condition (product_id);


-- ============================================================
-- 5. 포트폴리오 / 보유
-- ============================================================

CREATE TABLE user_portfolio (
    portfolio_id    bigint      GENERATED ALWAYS AS IDENTITY,
    user_id         bigint      NOT NULL,
    profile_id      bigint      NOT NULL,
    portfolio_type  varchar(10) NOT NULL,
    goal_amount     bigint,
    goal_date       date,
    after_tax_total bigint,
    status          varchar(10) NOT NULL DEFAULT '진행중',
    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT pk_user_portfolio PRIMARY KEY (portfolio_id),
    CONSTRAINT fk_user_portfolio_user_id_app_user
        FOREIGN KEY (user_id) REFERENCES app_user (user_id) ON DELETE CASCADE,
    -- 계산 근거가 된 조회 건은 지워지면 안 된다 (RESTRICT)
    CONSTRAINT fk_user_portfolio_profile_id_user_profile
        FOREIGN KEY (profile_id) REFERENCES user_profile (profile_id) ON DELETE RESTRICT,
    CONSTRAINT ck_user_portfolio_portfolio_type
        CHECK (portfolio_type IN ('단순형', '균형형', '최대형')),
    CONSTRAINT ck_user_portfolio_status
        CHECK (status IN ('진행중', '완료')),
    CONSTRAINT ck_user_portfolio_amounts
        CHECK ((goal_amount IS NULL OR goal_amount > 0)
           AND (after_tax_total IS NULL OR after_tax_total >= 0))
);

COMMENT ON TABLE  user_portfolio IS '사용자가 실제로 선택한 배분안. 제안만 하고 안 고른 안은 저장하지 않는다';
COMMENT ON COLUMN user_portfolio.after_tax_total IS '만기 시 예상 세후 수령액(원)';

CREATE INDEX ix_user_portfolio_user_id ON user_portfolio (user_id, created_at DESC);
CREATE INDEX ix_user_portfolio_profile_id ON user_portfolio (profile_id);


CREATE TABLE user_holding (
    holding_id     bigint        GENERATED ALWAYS AS IDENTITY,
    portfolio_id   bigint        NOT NULL,
    option_id      varchar(96),
    institution    varchar(100)  NOT NULL,
    product_name   varchar(200)  NOT NULL,
    amount         bigint,
    monthly_amount bigint,
    base_rate      numeric(5, 2) NOT NULL,
    effective_rate numeric(5, 2) NOT NULL,
    max_rate       numeric(5, 2) NOT NULL,
    start_date     date          NOT NULL,
    maturity_date  date,
    status         varchar(10)   NOT NULL DEFAULT '유지중',

    CONSTRAINT pk_user_holding PRIMARY KEY (holding_id),
    CONSTRAINT fk_user_holding_portfolio_id_user_portfolio
        FOREIGN KEY (portfolio_id) REFERENCES user_portfolio (portfolio_id) ON DELETE CASCADE,
    -- 상품이 공시에서 사라져도 보유 이력은 스냅샷 컬럼으로 살아남는다
    CONSTRAINT fk_user_holding_option_id_product_option
        FOREIGN KEY (option_id) REFERENCES product_option (option_id) ON DELETE SET NULL,
    CONSTRAINT ck_user_holding_status
        CHECK (status IN ('유지중', '만기')),
    -- 예금이면 amount, 적금이면 monthly_amount. 둘 다 비면 금액 없는 보유가 된다
    CONSTRAINT ck_user_holding_amount
        CHECK (amount IS NOT NULL OR monthly_amount IS NOT NULL),
    CONSTRAINT ck_user_holding_amount_positive
        CHECK ((amount IS NULL OR amount > 0)
           AND (monthly_amount IS NULL OR monthly_amount > 0)),
    -- 기본금리 <= 내 확정금리 <= 상품 최고금리. 계산 결과가 이 범위를 벗어나면 버그다.
    CONSTRAINT ck_user_holding_rates
        CHECK (base_rate >= 0 AND base_rate <= effective_rate
               AND effective_rate <= max_rate),
    CONSTRAINT ck_user_holding_maturity_date
        CHECK (maturity_date IS NULL OR maturity_date >= start_date)
);

COMMENT ON TABLE  user_holding IS '배분안을 이루는 가입 상품 1건';
COMMENT ON COLUMN user_holding.option_id IS
    '가입한 기간옵션. 상품이 아니라 옵션을 가리켜야 "어느 기간으로 가입했는지"가 남는다';
COMMENT ON COLUMN user_holding.institution IS '가입 시점 기관명 스냅샷. 원본이 사라져도 보여줘야 한다';
COMMENT ON COLUMN user_holding.base_rate IS '가입 시점 기본금리 스냅샷. 우대 가산 전';
COMMENT ON COLUMN user_holding.effective_rate IS
    '우대조건까지 반영해 확정된 가입 시점 금리. 적용 내역은 user_holding_condition 에 있다';
COMMENT ON COLUMN user_holding.max_rate IS
    '가입 시점 상품 최고금리 스냅샷. "광고 7.5% 중 당신은 5.5%" 를 보여주기 위한 값';

CREATE INDEX ix_user_holding_portfolio_id ON user_holding (portfolio_id);
CREATE INDEX ix_user_holding_maturity_date
    ON user_holding (maturity_date) WHERE status = '유지중';


CREATE TABLE user_holding_condition (
    id             bigint        GENERATED ALWAYS AS IDENTITY,
    holding_id     bigint        NOT NULL,
    condition_id   varchar(64),
    condition_type varchar(50)   NOT NULL,
    rate_bonus     numeric(4, 2) NOT NULL,
    evidence_text  text,

    CONSTRAINT pk_user_holding_condition PRIMARY KEY (id),
    CONSTRAINT fk_user_holding_condition_holding_id_user_holding
        FOREIGN KEY (holding_id) REFERENCES user_holding (holding_id) ON DELETE CASCADE,
    -- 원본 조건은 배치가 덮어쓰면서 사라질 수 있다. 그래서 아래 세 컬럼을 복사해 둔다.
    CONSTRAINT fk_user_holding_condition_condition_id_product_condition
        FOREIGN KEY (condition_id) REFERENCES product_condition (condition_id)
        ON DELETE SET NULL,
    -- 같은 종류의 조건이 한 보유 건에 두 번 적용되는 일은 없다 (계단 조건도 택1)
    CONSTRAINT uq_user_holding_condition_holding_id
        UNIQUE (holding_id, condition_type),
    CONSTRAINT ck_user_holding_condition_rate_bonus
        CHECK (rate_bonus >= 0)
);

COMMENT ON TABLE  user_holding_condition IS
    '이 보유 건의 확정금리가 어떻게 나왔는지에 대한 근거. 사용자가 "왜 5.5%?" 라고 물으면 이걸 보여준다';
COMMENT ON COLUMN user_holding_condition.condition_id IS
    '원본 우대조건. 상품이 덮어써지면 NULL 이 되지만 아래 스냅샷은 남는다';
COMMENT ON COLUMN user_holding_condition.rate_bonus IS
    '가입 시점에 실제로 가산된 %p. 전부 더하면 effective_rate - base_rate 가 된다';
COMMENT ON COLUMN user_holding_condition.evidence_text IS '가산 근거가 된 약관 원문 인용 스냅샷';

CREATE INDEX ix_user_holding_condition_holding_id ON user_holding_condition (holding_id);

COMMIT;

"""AI 파트 ERD 산출물(jsonl 4종) -> DB 적재.

산출물과 우리 테이블은 컬럼 이름이 비슷하지만 **정규화 수준이 다르다**. 파일 모양은 AI 파트가
정하고 테이블 모양은 우리가 정하므로, 그 차이를 흡수하는 곳은 여기 한 곳뿐이다.

산출물이 뭉쳐놓은 것                      우리가 나누는 방식
───────────────────────────────────────  ────────────────────────────────────────
product_type = '적금(정액적립식)'          product.product_type = '적금'
  (상품 종류 + 적립 방식)                  + product_option.reserve_type = '정액적립식'

product_id 끝에 채널이 붙어 같은 상품이     product 1행
채널별로 2행 (실측 1,861쌍)                + product_option.join_channel
  -> 공통 정보가 그대로 복제돼 있다          창구 3.20% / 비대면 3.25% 를 잃지 않으면서
     (이미 terms_text 2건이 갈렸다)          공통 정보 중복을 없앤다

threshold_unit = '만원' / '년' / '시간'    KRW / MONTH / HOUR 로 정규화하고 값을 환산

조건 PK 가 '-COND-1' 순번                  내용 해시. 순번은 다음 배치에서 같은 번호가
                                           다른 조건을 가리켜 upsert 가 엉뚱한 행을 덮는다

실행:
    uv run python -m app.importers.erd_import --erd-dir ai/output/erd
    uv run python -m app.importers.erd_import --erd-dir ... --dry-run   (DB 를 건드리지 않는다)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models import BatchRun, Institution, Product, ProductCondition, ProductOption

# --- 어휘 변환표 ------------------------------------------------------------
# 산출물 값 -> 우리 값. 표에 없으면 버리지 않고 리포트에 남긴다.

# product_id 꼬리 마디에 붙는 채널. 쉼표로 여러 개가 붙기도 한다('인터넷,스마트폰').
CHANNEL_SEGMENT = {
    "영업점": "영업점",
    "대면": "영업점",
    "인터넷": "비대면",
    "스마트폰": "비대면",
    "모바일": "비대면",
    "텔레뱅킹": "비대면",
    "전화": "비대면",
    "비대면": "비대면",
}

# 산출물은 상품 종류와 적립 방식을 한 컬럼에 붙여서 준다.
PRODUCT_TYPE = {
    "예금": ("예금", "해당없음"),
    "예탁금": ("예탁금", "해당없음"),
    "적금": ("적금", "해당없음"),
    "적금(정액적립식)": ("적금", "정액적립식"),
    "적금(자유적립식)": ("적금", "자유적립식"),
}

# product_option.reserve_type 은 옵션 행에도 따로 실려 온다. '거치식'은 예금을 뜻한다.
RESERVE_TYPE = {"거치식": "해당없음", "해당없음": "해당없음", "정액적립식": "정액적립식", "자유적립식": "자유적립식"}

# 우대조건 임계값의 단위. (우리 단위, 곱할 값) - 환산해서 담아야 값끼리 비교가 된다.
THRESHOLD_UNIT = {
    "원": ("KRW", 1),
    "만원": ("KRW", 10_000),
    "백만원": ("KRW", 1_000_000),
    "억": ("KRW", 100_000_000),
    "억원": ("KRW", 100_000_000),
    "개월": ("MONTH", 1),
    "년": ("MONTH", 12),
    "주": ("WEEK", 1),
    "일": ("DAY", 1),
    "시간": ("HOUR", 1),
    "세": ("AGE", 1),
    "점": ("SCORE", 1),
    "보": ("STEP", 1),
    "회": ("COUNT", 1),
    "건": ("COUNT", 1),
    "명": ("COUNT", 1),
    "개": ("COUNT", 1),
    "종": ("COUNT", 1),
    "회전": ("COUNT", 1),
}

# 산출물 컬럼명 -> 우리 컬럼명. 뜻은 같고 철자만 다르다.
#   apply_period_min/max -> applies_period_min/max
#   exclusion_group      -> exclusive_group


def split_channel(raw_product_id: str) -> tuple[str, list[str]]:
    """'CU-03016-1501-인터넷,스마트폰' -> ('CU-03016-1501', ['비대면', '비대면']).

    꼬리 마디가 전부 채널 이름일 때만 떼어낸다. '정기예탁금(만기지급식)' 처럼 상품명이
    꼬리에 오는 경우가 더 많아서(18,336행) 무조건 떼면 상품 키가 깨진다.
    """
    segments = raw_product_id.split("-")
    parts = [p.strip() for p in segments[-1].split(",")]
    if parts and all(p in CHANNEL_SEGMENT for p in parts):
        return "-".join(segments[:-1]), [CHANNEL_SEGMENT[p] for p in parts]
    return raw_product_id, []


def product_id_of(raw_product_id: str, product_name: str) -> str:
    """채널을 뗀 키에 상품명 해시를 붙인다.

    채널만 떼면 같은 기관·같은 상품코드인데 상품명이 다른 상품끼리 키가 겹친다
    (실측 11건: 1501-영업점 = 만기지급식, 1501-인터넷 = 월지급식). 상품명을 섞으면
    행마다 결정적으로 계산되고 배치를 다시 돌려도 같은 값이 나온다.
    """
    base, _ = split_channel(raw_product_id)
    digest = hashlib.sha1(product_name.encode("utf-8")).hexdigest()[:6]
    return f"{base}-{digest}"


def option_id_of(product_id: str, period: int, rate_type: str, reserve_type: str, channel: str) -> str:
    """UNIQUE(product_id, 기간, 이자방식, 적립방식, 채널) 과 같은 조합으로 만든다.

    PK 규칙이 UNIQUE 보다 좁으면 서로 다른 행이 같은 PK 를 받아 upsert 가 하나를 덮는다.
    """
    return f"{product_id}-{period}-{rate_type}-{reserve_type}-{channel}"


def condition_id_of(product_id: str, evidence: str, bonus: Any, group: Any) -> str:
    """우대조건 PK. 내용 해시로 만든다.

    condition_type 은 일부러 키에서 뺐다. '기타' 였던 조건이 나중에 정식 타입으로
    재분류될 때 키가 바뀌면 제자리 갱신이 안 되고 옛 행이 남는다.
    """
    digest = hashlib.sha1("\x1f".join(str(x) for x in (evidence, bonus, group)).encode("utf-8")).hexdigest()
    return f"{product_id}-COND-{digest[:10]}"


@dataclass
class Report:
    counts: Counter = field(default_factory=Counter)
    merged: Counter = field(default_factory=Counter)
    dropped: Counter = field(default_factory=Counter)
    missing: Counter = field(default_factory=Counter)
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        out = ["", "=" * 66, "적재 결과", "=" * 66]
        for key in ("institution", "product", "product_option", "product_condition"):
            out.append(f"  {key:<24} {self.counts[key]:>9,} 건")
        if self.merged:
            out += ["", "-" * 66, "정규화하면서 합친 것", "-" * 66]
            out += [f"  {k:<44} {v:>9,}" for k, v in self.merged.most_common()]
        if self.dropped:
            out += ["", "-" * 66, "우리 어휘로 옮기지 못해 비운 칸", "-" * 66]
            out += [f"  {k:<44} {v:>9,}" for k, v in self.dropped.most_common()]
        out += ["", "-" * 66, "산출물에 값이 없어 못 채운 칸 (AI 파트 요청 항목)", "-" * 66]
        out += [f"  {k:<44} {v:>9,}" for k, v in self.missing.most_common()] or ["  없음"]
        if self.notes:
            out += ["", "-" * 66, "메모", "-" * 66] + [f"  {n}" for n in self.notes]
        return "\n".join(out) + "\n"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _as_date(value: Any) -> date | None:
    return date.fromisoformat(value) if value else None


def build_rows(src: dict[str, list[dict]], report: Report) -> dict[str, list[dict]]:
    """산출물 4종을 테이블 4종 분량의 행으로 바꾼다. DB 는 건드리지 않는다."""
    # --- institution -------------------------------------------------------
    # 산출물 컬럼이 우리 테이블과 같다. 이름 중복은 더 이상 막지 않는다
    # (지역이 다른 동명 새마을금고가 별개 기관이라 UNIQUE 를 뺐다).
    institutions = [
        {
            "institution_code": r["institution_code"],
            "name": r["name"],
            "institution_type": r["institution_type"],
            "region": r.get("region"),
            "is_active": r.get("is_active", True),
        }
        for r in src["institution"]
    ]
    for r in institutions:
        if not r["region"]:
            report.missing["institution.region (영업 지역)"] += 1

    # --- product : 채널별로 쪼개진 행을 하나로 합친다 -----------------------
    # 어떤 raw_product_id 가 어느 상품·채널에 속하는지 먼저 정리해 둔다.
    # 옵션과 조건이 이 지도를 따라 붙는다.
    where: dict[str, tuple[str, str]] = {}  # raw_product_id -> (product_id, channel)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in src["product"]:
        pid = product_id_of(row["product_id"], row["product_name"])
        _, channels = split_channel(row["product_id"])
        # 한 행에 채널이 여러 개 붙어 있으면('인터넷,스마트폰') 전부 비대면으로 모인다.
        channel = channels[0] if len(set(channels)) == 1 else "전체"
        where[row["product_id"]] = (pid, channel if channels else "전체")
        grouped[pid].append(row)

    products: list[dict] = []
    for pid, rows in grouped.items():
        if len(rows) > 1:
            report.merged["채널별로 쪼개져 있던 product 행 -> 1행"] += len(rows) - 1
        # 같은 상품인데 값이 다른 칸이 있다(수집일이 섞여 들어온다). 최신 수집일을 채택한다.
        head = max(rows, key=lambda r: r.get("snapshot_date") or "")
        for f in ("terms_text", "amount_cap", "product_type"):
            if len({json.dumps(r.get(f), ensure_ascii=False) for r in rows}) > 1:
                report.notes.append(f"{pid}: 합치면서 {f} 가 서로 달라 최신 수집일 값을 택함")

        raw_type = head["product_type"]
        if raw_type not in PRODUCT_TYPE:
            report.dropped[f"product.product_type ('{raw_type}' 대응 값 없음)"] += 1
            continue
        product_type, _ = PRODUCT_TYPE[raw_type]

        # 상품 단위 가입 채널은 옵션에 실린 채널을 모아서 정한다.
        channels = {where[r["product_id"]][1] for r in rows}
        join_channel = channels.pop() if len(channels) == 1 else "전체"

        products.append(
            {
                "product_id": pid,
                "institution_code": head["institution_code"],
                "product_name": head["product_name"],
                "product_type": product_type,
                "amount_min": head.get("amount_min"),
                "amount_cap": head.get("amount_cap"),
                "monthly_min": head.get("monthly_min") if product_type == "적금" else None,
                "monthly_cap": head.get("monthly_cap") if product_type == "적금" else None,
                "terms_text": head.get("terms_text"),
                "region": head.get("region"),
                "join_channel": join_channel,
                # 산출물이 NULL 로 주는 칸이다. 우리 컬럼은 NOT NULL 이라 기본값으로 내린다.
                "membership_required": bool(head.get("membership_required")),
                "new_customer_only": bool(head.get("new_customer_only")),
                "min_age": head.get("min_age"),
                "max_age": head.get("max_age"),
                "parse_status": head.get("parse_status") or "PENDING",
                # NOT NULL 이다. DEFAULT CURRENT_DATE 는 컬럼을 생략했을 때만 걸리는데
                # 임포터는 모든 컬럼을 명시해서 넣으므로 여기서 직접 채운다.
                "snapshot_date": _as_date(head.get("snapshot_date")) or date.today(),
                "sale_end_date": _as_date(head.get("sale_end_date")),
                "is_active": head.get("is_active", True),
            }
        )
        for col, val in (
            ("product.terms_text (약관 원문)", head.get("terms_text")),
            ("product.amount_min (최소 가입금액)", head.get("amount_min")),
            ("product.min_age/max_age (연령 제한)", head.get("min_age")),
            ("product.membership_required (조합원 자격)", head.get("membership_required")),
            ("product.new_customer_only (신규 전용)", head.get("new_customer_only")),
        ):
            if val is None:
                report.missing[col] += 1
        if not head.get("snapshot_date"):
            report.missing["product.snapshot_date (수집 기준일 -> 오늘로 채움)"] += 1
        if product_type == "적금" and head.get("monthly_cap") is None:
            report.missing["product.monthly_cap (적금 월 납입 한도)"] += 1

    known = {p["product_id"] for p in products}

    # --- product_option : 여기에 채널 축이 생긴다 ---------------------------
    options: dict[str, dict] = {}
    for row in src["product_option"]:
        target = where.get(row["product_id"])
        if target is None or target[0] not in known:
            report.dropped["product_option (상품을 못 찾음)"] += 1
            continue
        pid, channel = target
        # 기간별 금리 테이블이라 기간이 0 인 행은 담을 자리가 없다(실측 1,485건, 전부 "Block예금").
        # 추천은 기간옵션 단위로 고르므로 기간을 모르는 금리는 쓸 수도 없다. AI 파트에 확인 요청한 항목.
        if not isinstance(row.get("period_months"), int) or row["period_months"] <= 0:
            report.dropped["product_option.period_months (0 이하 - 담을 수 없음)"] += 1
            continue
        reserve = RESERVE_TYPE.get(row.get("reserve_type"))
        if reserve is None:
            report.dropped[f"product_option.reserve_type ('{row.get('reserve_type')}' 대응 값 없음)"] += 1
            continue
        oid = option_id_of(pid, row["period_months"], row["rate_type"], reserve, channel)
        if oid in options:
            report.merged["같은 (상품·기간·이자방식·적립방식·채널) 옵션 중복"] += 1
            continue
        options[oid] = {
            "option_id": oid,
            "product_id": pid,
            "period_months": row["period_months"],
            "rate_type": row["rate_type"],
            "reserve_type": reserve,
            "join_channel": channel,
            "base_rate": row["base_rate"],
            "max_rate": row["max_rate"],
        }

    # --- product_condition -------------------------------------------------
    conditions: dict[str, dict] = {}
    for row in src["product_condition"]:
        target = where.get(row["product_id"])
        if target is None or target[0] not in known:
            report.dropped["product_condition (상품을 못 찾음)"] += 1
            continue
        pid = target[0]

        value, unit = row.get("threshold_value"), row.get("threshold_unit")
        if unit is not None:
            mapped = THRESHOLD_UNIT.get(unit)
            if mapped is None:
                # 값과 단위는 CHECK 로 짝이 묶여 있다. 하나만 남기면 INSERT 가 막힌다.
                report.dropped[f"product_condition.threshold ('{unit}' 대응 단위 없음)"] += 1
                value, unit = None, None
            else:
                unit, factor = mapped
                value = int(value * factor) if value is not None else None
                if factor != 1:
                    report.merged[f"threshold 값 환산 ({unit})"] += 1

        cid = condition_id_of(pid, row["evidence_text"], row.get("rate_bonus"), row.get("exclusion_group"))
        if cid in conditions:
            # 산출물은 채널별 상품마다 같은 조건을 복사해서 준다. 합치면 한 건이다.
            report.merged["채널별로 복사돼 있던 우대조건 -> 1건"] += 1
            continue
        if row.get("rate_bonus") is None:
            report.missing["product_condition.rate_bonus (원문에 %p 없음 -> NULL 유지)"] += 1
        conditions[cid] = {
            "condition_id": cid,
            "product_id": pid,
            "condition_type": row["condition_type"],
            "rate_bonus": row.get("rate_bonus"),
            "threshold_value": value,
            "threshold_unit": unit,
            "applies_period_min": row.get("apply_period_min"),
            "applies_period_max": row.get("apply_period_max"),
            "exclusive_group": row.get("exclusion_group"),
            "evidence_text": row.get("evidence_text"),
            "evidence_url": row.get("evidence_url"),
            # 산출물에서 빠진 칸이다(aab0efc). 검수 전이므로 기본값을 그대로 쓴다.
            "verification_status": None,
            "confidence_badge": "검수대기",
        }

    tables = {
        "institution": institutions,
        "product": products,
        "product_option": list(options.values()),
        "product_condition": list(conditions.values()),
    }
    report.counts.update({k: len(v) for k, v in tables.items()})
    return tables


async def _upsert(session, model, rows: list[dict], pk: str, chunk: int = 1000) -> None:
    """PK 충돌 시 갱신한다. DELETE+INSERT 로 돌면 user_holding 링크가 매 배치마다 끊긴다."""
    if not rows:
        return
    for i in range(0, len(rows), chunk):
        part = rows[i : i + chunk]
        stmt = insert(model).values(part)
        updatable = {c: stmt.excluded[c] for c in part[0] if c != pk}
        await session.execute(stmt.on_conflict_do_update(index_elements=[pk], set_=updatable))


async def run_import(erd_dir: Path, dry_run: bool = False) -> Report:
    report = Report()
    src = {
        name: load_jsonl(erd_dir / f"{name}.jsonl")
        for name in ("institution", "product", "product_option", "product_condition")
    }
    report.notes.append("산출물 " + " / ".join(f"{k} {len(v):,}" for k, v in src.items()))
    tables = build_rows(src, report)

    if dry_run:
        report.notes.append("dry-run: DB 에 쓰지 않았다")
        return report

    async with SessionLocal() as session:
        run = BatchRun(batch_type="COLLECT", status="RUNNING")
        session.add(run)
        await session.flush()  # run_id 를 받아 product.run_id 에 넣는다
        for row in tables["product"]:
            row["run_id"] = run.run_id

        try:
            await _upsert(session, Institution, tables["institution"], "institution_code")
            await _upsert(session, Product, tables["product"], "product_id")
            await _upsert(session, ProductOption, tables["product_option"], "option_id")
            await _upsert(session, ProductCondition, tables["product_condition"], "condition_id")
        except Exception as exc:
            await session.rollback()
            async with SessionLocal() as s2:
                # 종료 상태는 finished_at 이 반드시 같이 있어야 ck_batch_run_terminal 을 통과한다.
                await s2.execute(
                    update(BatchRun)
                    .where(BatchRun.run_id == run.run_id)
                    .values(status="FAILED", finished_at=func.now(), error_message=str(exc)[:500])
                )
                await s2.commit()
            raise

        await session.execute(
            update(BatchRun)
            .where(BatchRun.run_id == run.run_id)
            .values(status="SUCCESS", finished_at=func.now(), processed_count=sum(report.counts.values()))
        )
        await session.commit()
        report.notes.append(f"batch_run #{run.run_id} 로 기록")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 산출물 jsonl 4종을 DB 에 적재한다")
    parser.add_argument(
        "--erd-dir",
        required=True,
        type=Path,
        help="institution/product/product_option/product_condition .jsonl 이 있는 폴더",
    )
    parser.add_argument("--dry-run", action="store_true", help="DB 를 건드리지 않고 리포트만 출력")
    args = parser.parse_args()

    report = asyncio.run(run_import(args.erd_dir, args.dry_run))
    print(report.render())


if __name__ == "__main__":
    main()

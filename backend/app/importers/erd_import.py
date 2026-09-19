"""AI 파트 산출물(product.jsonl / product_condition.jsonl) -> DB 적재.

AI 산출물은 "상품 + 만기" 가 한 행인 flat 구조다. 우리 테이블은 기관 / 상품 /
기간옵션 / 우대조건 네 개로 나뉘어 있으므로 이 모듈이 그 사이를 변환한다.

    product.jsonl        ─┬─> institution
                          ├─> product
                          └─> product_option
    product_condition    ───> product_condition

파일 모양은 AI 파트가 자유롭게 정하고, 테이블 모양은 우리가 정한다. 그 둘이
어긋나는 부분을 전부 여기서 흡수한다 - 산출물 구조가 또 바뀌어도 고칠 곳은 이 파일뿐이다.

실행:
    uv run python -m app.importers.erd_import --product <경로> --condition <경로>
    uv run python -m app.importers.erd_import ... --dry-run   (DB 를 건드리지 않고 리포트만)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models import BatchRun, Institution, Product, ProductCondition, ProductOption

# --- 값 변환 규칙 -----------------------------------------------------------
# AI 산출물 어휘 -> 우리 어휘. 없는 값은 None 으로 떨어뜨리고 리포트에 남긴다.
JOIN_CHANNEL = {"대면": "영업점", "비대면": "비대면", "대면+비대면": "전체"}  # '모집인' 은 대응 값 없음
# 산출물은 적립방식을 product_type 안에 섞어서 준다. 우리는 상품 종류와 적립 방식을 나눠 쓴다.
PRODUCT_TYPE = {"예금": "예금", "적금(정액적립식)": "적금", "적금(자유적립식)": "적금"}
RESERVE_TYPE = {"예금": "해당없음", "적금(정액적립식)": "정액적립식", "적금(자유적립식)": "자유적립식"}
# 산출물에 이자 계산 방식이 없다. 금감원 원본(intr_rate_type_nm)에는 있으므로 요청해 둔 상태이고,
# 그때까지는 단리로 둔다. UNIQUE(product_id, period_months, rate_type, reserve_type) 때문에
# NULL 을 쓸 수 없어서 기본값이 필요하다.
DEFAULT_RATE_TYPE = "단리"

MATURITY_SUFFIX_RE = re.compile(r"-\d+$")


def base_product_id(product_id: str) -> str:
    """'BANK-0010002-00320342-12' -> 'BANK-0010002-00320342'. 만기를 떼면 상품 단위 키가 된다."""
    return MATURITY_SUFFIX_RE.sub("", product_id)


def institution_code_of(product_id: str) -> str:
    """'CU-01235-1508-스마트폰-3' -> 'CU-01235'.

    산출물에 기관 코드 컬럼이 없어서 product_id 앞 두 마디에서 꺼낸다. 문자열 규칙에
    의존하므로 깨지기 쉽다 - institution_code 를 컬럼으로 달라고 요청해 둔 상태다.
    """
    return "-".join(product_id.split("-")[:2])


def condition_id_of(base_pid: str, key: tuple) -> str:
    """우대조건 PK. 내용 해시로 만든다.

    산출물은 '-COND-1', '-COND-2' 처럼 순번을 쓰는데, 다음 배치에서 조건 순서나 개수가
    바뀌면 같은 번호가 다른 조건을 가리키게 된다. upsert 로 갱신하면 엉뚱한 행을 덮어쓴다.
    내용으로 만들면 같은 조건은 언제 돌려도 같은 PK 를 받는다.
    """
    digest = hashlib.sha1("\x1f".join(str(k) for k in key).encode("utf-8")).hexdigest()
    return f"{base_pid}-COND-{digest[:10]}"


@dataclass
class Report:
    """적재 건수와 '값이 없어서 못 채운 칸'을 센다.

    AI 파트에 요청해 둔 값들이 실제로 들어오기 시작했는지를 이 출력만 보고 판단하려는 것이다.
    새 산출물을 받으면 임포터를 한 번 돌리는 것으로 반영 여부가 드러난다.
    """

    counts: Counter = field(default_factory=Counter)
    missing: Counter = field(default_factory=Counter)
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = ["", "=" * 62, "적재 결과", "=" * 62]
        for key in ("institution", "product", "product_option", "product_condition"):
            lines.append(f"  {key:<20} {self.counts[key]:>8,} 건")
        lines += ["", "-" * 62, "산출물에 값이 없어 못 채운 칸 (AI 파트에 요청해 둔 항목)", "-" * 62]
        if not self.missing:
            lines.append("  없음 - 전부 채워졌다")
        for key, n in self.missing.most_common():
            lines.append(f"  {key:<34} {n:>8,} 건")
        if self.notes:
            lines += ["", "-" * 62, "처리 중 조정한 것", "-" * 62]
            lines += [f"  {note}" for note in self.notes]
        return "\n".join(lines) + "\n"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_rows(products: list[dict], conditions: list[dict], report: Report) -> dict[str, list[dict]]:
    """flat 산출물을 테이블 네 개 분량의 행으로 나눈다. DB 는 건드리지 않는다."""
    by_product: dict[str, list[dict]] = defaultdict(list)
    for row in products:
        by_product[base_product_id(row["product_id"])].append(row)

    # --- institution -------------------------------------------------------
    # name 에 UNIQUE 가 걸려 있는데 산출물에는 이름이 같은 다른 기관이 있다
    # ('국민은행' 은행 / '국민은행' 직장 신협). 코드 사전순으로 첫 번째가 원래 이름을 갖고,
    # 나머지는 기관 종류를 붙여 구분한다. 코드 기준이라 재실행해도 같은 결과가 나온다.
    inst_seen: dict[str, tuple[str, str]] = {}
    for base_pid, rows in by_product.items():
        head = rows[0]
        inst_seen[institution_code_of(base_pid)] = (head["institution"], head["institution_type"])

    used_names: dict[str, str] = {}
    institutions: list[dict] = []
    for code, (name, itype) in sorted(inst_seen.items()):
        final = name
        if used_names.get(name, code) != code:
            final = f"{name}({itype})"
            report.notes.append(f"기관명 중복 -> '{name}' 을 '{final}' 로 구분 (코드 {code})")
        used_names.setdefault(name, code)
        institutions.append(
            {"institution_code": code, "name": final, "institution_type": itype, "region": None, "is_active": True}
        )
    report.missing["institution.region (영업 지역)"] = len(institutions)

    # --- product / product_option -----------------------------------------
    prods: list[dict] = []
    options: list[dict] = []
    for base_pid, rows in by_product.items():
        # 같은 상품인데 행마다 값이 다른 경우가 있다(수집일이 섞여 들어옴). 최신 수집일을 채택한다.
        head = max(rows, key=lambda r: r.get("snapshot_date") or "")
        channel = JOIN_CHANNEL.get(head.get("join_channel"))
        if head.get("join_channel") and channel is None:
            report.missing[f"product.join_channel ('{head['join_channel']}' 대응 값 없음)"] += 1
        prods.append(
            {
                "product_id": base_pid,
                "offer_id": None,
                "source": head.get("source") or "OFFICIAL",
                "institution_code": institution_code_of(base_pid),
                "product_name": head["product_name"],
                "product_type": PRODUCT_TYPE[head["product_type"]],
                "amount_min": None,
                "amount_cap": head.get("amount_cap"),
                "monthly_min": None,
                "monthly_cap": None,
                "terms_text": None,
                "region": head.get("region"),
                "join_channel": channel,
                "membership_required": False,
                "new_customer_only": False,
                "min_age": None,
                "max_age": None,
                "parse_status": "PARSED",
                "snapshot_date": date.fromisoformat(head["snapshot_date"]) if head.get("snapshot_date") else None,
                "sale_end_date": None,
                "is_active": True,
            }
        )
        for col in (
            "product.terms_text (약관 원문)",
            "product.sale_end_date (판매 종료일)",
            "product.membership_required (조합원 자격)",
            "product.min_age/max_age (연령 제한)",
        ):
            report.missing[col] += 1
        if PRODUCT_TYPE[head["product_type"]] == "적금":
            report.missing["product.monthly_min/monthly_cap (적금 월 납입 한도)"] += 1

        for row in rows:
            options.append(
                {
                    "option_id": f"{base_pid}-{row['period_months']}-{DEFAULT_RATE_TYPE}",
                    "product_id": base_pid,
                    "period_months": row["period_months"],
                    "rate_type": DEFAULT_RATE_TYPE,
                    "reserve_type": RESERVE_TYPE[row["product_type"]],
                    "base_rate": row["base_rate"],
                    "max_rate": row["max_rate"],
                }
            )
        report.missing["product_option.rate_type (단리/복리)"] += len(rows)

    # --- product_condition -------------------------------------------------
    # 산출물은 만기 행마다 같은 조건을 복사해서 준다. 우리는 조건을 상품 단위로 들고
    # 만기 적용 범위를 컬럼으로 표현하므로, 내용이 같은 것은 한 건으로 합친다.
    known_products = {p["product_id"] for p in prods}
    dedup: dict[str, dict[tuple, dict]] = defaultdict(dict)
    orphan = 0
    for cond in conditions:
        base_pid = base_product_id(cond["product_id"])
        if base_pid not in known_products:
            orphan += 1
            continue
        key = (
            cond.get("condition_type") or "기타",
            cond.get("rate_bonus"),
            cond["evidence_text"],
            cond.get("exclusive_group"),
        )
        dedup[base_pid].setdefault(key, cond)
    if orphan:
        report.notes.append(f"product 에 없는 우대조건 {orphan:,}건은 건너뜀 (FK 위반 방지)")

    conds: list[dict] = []
    for base_pid, items in dedup.items():
        for key, cond in items.items():
            ctype, bonus, evidence, group = key
            if bonus is None:
                report.missing["product_condition.rate_bonus (원문에 %p 없음 -> 0 처리)"] += 1
            if cond.get("verification_status") is None:
                report.missing["product_condition.verification_status (검산 결과)"] += 1
            report.missing["product_condition.applies_period_min/max (조건별 적용 기간)"] += 1
            if cond.get("threshold_value") is None:
                report.missing["product_condition.threshold_value/unit (조건 기준값)"] += 1
            conds.append(
                {
                    "condition_id": condition_id_of(base_pid, key),
                    "product_id": base_pid,
                    "condition_type": ctype,
                    "rate_bonus": bonus if bonus is not None else 0,
                    "threshold_value": None,
                    "threshold_unit": None,
                    "applies_period_min": None,
                    "applies_period_max": None,
                    "exclusive_group": group,
                    "evidence_text": evidence,
                    "evidence_url": cond.get("source_url") or cond.get("evidence_url"),
                    "verification_status": None,
                    "confidence_badge": "검수대기",
                }
            )

    report.counts.update(
        {
            "institution": len(institutions),
            "product": len(prods),
            "product_option": len(options),
            "product_condition": len(conds),
        }
    )
    report.notes.append(f"우대조건 {len(conditions):,}건(만기별 중복 포함) -> {len(conds):,}건으로 합침")
    return {"institution": institutions, "product": prods, "product_option": options, "product_condition": conds}


async def _upsert(session, model, rows: list[dict], pk: str, chunk: int = 1000) -> None:
    """PK 충돌 시 갱신한다. 배치가 DELETE+INSERT 로 돌면 user_holding 링크가 매번 끊긴다."""
    if not rows:
        return
    for i in range(0, len(rows), chunk):
        part = rows[i : i + chunk]
        stmt = insert(model).values(part)
        updatable = {c: stmt.excluded[c] for c in part[0] if c != pk}
        await session.execute(stmt.on_conflict_do_update(index_elements=[pk], set_=updatable))


async def run_import(product_path: Path, condition_path: Path, dry_run: bool = False) -> Report:
    report = Report()
    tables = build_rows(load_jsonl(product_path), load_jsonl(condition_path), report)

    if dry_run:
        report.notes.append("dry-run: DB 에 쓰지 않았다")
        return report

    async with SessionLocal() as session:
        run = BatchRun(batch_type="COLLECT", status="RUNNING")
        session.add(run)
        await session.flush()  # run_id 를 받아서 product.run_id 에 넣는다
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
                # finished_at 은 반드시 같이 채운다. RUNNING 이 아닌 상태는
                # 종료 시각이 없으면 ck_batch_run_terminal 에 걸려 기록 자체가 안 된다.
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
    parser = argparse.ArgumentParser(description="AI 산출물 jsonl 을 DB 에 적재한다")
    parser.add_argument("--product", required=True, type=Path, help="product.jsonl 경로")
    parser.add_argument("--condition", required=True, type=Path, help="product_condition.jsonl 경로")
    parser.add_argument("--dry-run", action="store_true", help="DB 를 건드리지 않고 리포트만 출력")
    args = parser.parse_args()

    report = asyncio.run(run_import(args.product, args.condition, args.dry_run))
    print(report.render())


if __name__ == "__main__":
    main()

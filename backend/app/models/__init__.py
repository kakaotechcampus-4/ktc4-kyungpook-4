"""모든 모델을 여기서 import 해야 Base.metadata 가 채워진다.

alembic autogenerate 와 테스트용 create_all 이 이 목록을 보고 동작한다.
"""

from app.models.batch import BatchRun, CrawlHistory
from app.models.institution import Institution, InstitutionAlias
from app.models.offer import SpecialOffer, SpecialOfferOption
from app.models.portfolio import UserHolding, UserHoldingCondition, UserPortfolio
from app.models.product import Product, ProductCondition, ProductOption
from app.models.profile import (
    UserProfile,
    UserProfileBank,
    UserProfileExtra,
    UserProfileSocial,
    UserProfileTaxExempt,
)
from app.models.user import AppUser, SocialAccount

__all__ = [
    "AppUser",
    "BatchRun",
    "CrawlHistory",
    "Institution",
    "InstitutionAlias",
    "Product",
    "ProductCondition",
    "ProductOption",
    "SocialAccount",
    "SpecialOffer",
    "SpecialOfferOption",
    "UserHolding",
    "UserHoldingCondition",
    "UserPortfolio",
    "UserProfile",
    "UserProfileBank",
    "UserProfileExtra",
    "UserProfileSocial",
    "UserProfileTaxExempt",
]

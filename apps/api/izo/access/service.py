"""ACCESS composition root; behavior lives in focused mixins."""
from .base import AccessServiceBase
from .mutations import AccessMutationMixin
from .owner import AccessOwnerMixin
from .reads import AccessReadMixin


class AccessService(AccessMutationMixin, AccessReadMixin, AccessOwnerMixin, AccessServiceBase):
    """Public ACCESS service API assembled from bounded modules."""

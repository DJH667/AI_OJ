"""分页参数规范化（api.md：与 GET /api/submissions/ 语义一致）。

- page 有值但 page_size 为空 → 参数错误（400）；
- page 空但 page_size 有值 → 取第 1 页；
- 两者皆空 → 全部数据（返回 page=None, page_size=None）；
- page/page_size < 1 → 400。
"""
from app.core import messages
from app.core.exceptions import ApiError


def normalize_page(page: int | None, page_size: int | None) -> tuple[int | None, int | None]:
    if page is not None and page_size is None:
        raise ApiError(400, messages.PAGE_SIZE_REQUIRED)
    if page is not None and page < 1:
        raise ApiError(400, messages.INVALID_PAGINATION)
    if page_size is not None and page_size < 1:
        raise ApiError(400, messages.INVALID_PAGINATION)
    if page is None and page_size is not None:
        page = 1
    return page, page_size

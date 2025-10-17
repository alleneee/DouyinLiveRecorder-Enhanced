"""通用schemas"""
from pydantic import BaseModel
from typing import Generic, TypeVar, List

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    total: int
    page: int
    page_size: int
    items: List[T]
    
    class Config:
        from_attributes = True

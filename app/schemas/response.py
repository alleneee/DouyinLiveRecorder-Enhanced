"""统一API响应体封装

提供标准化的API响应格式,支持:
- 成功/失败响应
- 分页数据响应
- 泛型数据支持
- 错误追踪(trace_id)
- 响应时间戳

使用示例:
    # 成功响应
    return ApiResponse.success(data={"user_id": 123})

    # 失败响应
    return ApiResponse.fail(message="用户不存在", code=404)

    # 分页响应
    return ApiResponse.success_with_pagination(
        data=items,
        total=100,
        page=1,
        page_size=20
    )
"""

from typing import Generic, TypeVar, Optional, Any, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import IntEnum

T = TypeVar('T')


class ResponseCode(IntEnum):
    """标准响应码枚举"""
    # 成功响应 (2xx)
    SUCCESS = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204

    # 客户端错误 (4xx)
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422

    # 服务器错误 (5xx)
    INTERNAL_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503


class PaginationMeta(BaseModel):
    """分页元数据"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., ge=1, description="当前页码")
    page_size: int = Field(..., ge=1, le=1000, description="每页大小")
    total_pages: int = Field(..., description="总页数")
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")

    @classmethod
    def from_params(cls, total: int, page: int, page_size: int) -> 'PaginationMeta':
        """从参数构建分页元数据"""
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )

    class Config:
        json_schema_extra = {
            "example": {
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "has_next": True,
                "has_prev": False
            }
        }


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应体

    字段说明:
        code: HTTP状态码
        success: 请求是否成功
        message: 响应消息
        data: 响应数据(泛型)
        pagination: 分页信息(可选)
        trace_id: 请求追踪ID(可选)
        timestamp: 响应时间戳
    """
    code: int = Field(..., description="响应状态码")
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[T] = Field(None, description="响应数据")
    pagination: Optional[PaginationMeta] = Field(None, description="分页信息")
    trace_id: Optional[str] = Field(None, description="请求追踪ID")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="响应时间戳"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "success": True,
                "message": "操作成功",
                "data": {"id": 1, "name": "示例数据"},
                "trace_id": "req-123456",
                "timestamp": "2024-01-01T12:00:00"
            }
        }


# 工厂函数（替代classmethod，解决pydantic泛型问题）
def success_response(
    data: Optional[T] = None,
    message: str = "操作成功",
    code: int = ResponseCode.SUCCESS,
    trace_id: Optional[str] = None
) -> ApiResponse[T]:
    """构建成功响应

    Args:
        data: 响应数据
        message: 成功消息
        code: 响应码,默认200
        trace_id: 请求追踪ID

    Returns:
        标准成功响应对象

    Examples:
        >>> success_response(data={"user_id": 123})
        >>> success_response(message="创建成功", code=201)
    """
    return ApiResponse(
        code=code,
        success=True,
        message=message,
        data=data,
        trace_id=trace_id
    )


def fail_response(
    message: str = "操作失败",
    code: int = ResponseCode.BAD_REQUEST,
    data: Optional[Any] = None,
    trace_id: Optional[str] = None
) -> ApiResponse[Any]:
    """构建失败响应

    Args:
        message: 错误消息
        code: 错误码,默认400
        data: 错误详情数据(可选)
        trace_id: 请求追踪ID

    Returns:
        标准失败响应对象

    Examples:
        >>> fail_response(message="用户不存在", code=404)
        >>> fail_response(
        ...     message="验证失败",
        ...     code=422,
        ...     data={"errors": ["字段不能为空"]}
        ... )
    """
    return ApiResponse(
        code=code,
        success=False,
        message=message,
        data=data,
        trace_id=trace_id
    )


def success_response_with_pagination(
    data: List[Any],
    total: int,
    page: int = 1,
    page_size: int = 20,
    message: str = "查询成功",
    trace_id: Optional[str] = None
) -> ApiResponse[List[Any]]:
    """构建分页成功响应

    Args:
        data: 当前页数据列表
        total: 总记录数
        page: 当前页码
        page_size: 每页大小
        message: 成功消息
        trace_id: 请求追踪ID

    Returns:
        带分页信息的成功响应

    Examples:
        >>> success_response_with_pagination(
        ...     data=[{"id": 1}, {"id": 2}],
        ...     total=100,
        ...     page=1,
        ...     page_size=20
        ... )
    """
    pagination = PaginationMeta.from_params(
        total=total,
        page=page,
        page_size=page_size
    )

    return ApiResponse(
        code=ResponseCode.SUCCESS,
        success=True,
        message=message,
        data=data,
        pagination=pagination,
        trace_id=trace_id
    )


class ErrorDetail(BaseModel):
    """错误详情模型"""
    field: Optional[str] = Field(None, description="错误字段")
    message: str = Field(..., description="错误信息")
    code: Optional[str] = Field(None, description="错误代码")

    class Config:
        json_schema_extra = {
            "example": {
                "field": "email",
                "message": "邮箱格式不正确",
                "code": "INVALID_EMAIL"
            }
        }


class ValidationErrorResponse(ApiResponse[List[ErrorDetail]]):
    """验证错误响应"""

    @classmethod
    def from_validation_error(
        cls,
        errors: List[ErrorDetail],
        trace_id: Optional[str] = None
    ) -> 'ValidationErrorResponse':
        """从验证错误列表构建响应"""
        return cls(
            code=ResponseCode.UNPROCESSABLE_ENTITY,
            success=False,
            message="数据验证失败",
            data=errors,
            trace_id=trace_id
        )


# 常用响应类型别名
SuccessResponse = ApiResponse[Any]
"""成功响应类型别名"""

FailResponse = ApiResponse[None]
"""失败响应类型别名"""

PaginatedResponse = ApiResponse[List[Any]]
"""分页响应类型别名"""

"""响应包装工具

提供装饰器和工具函数简化API响应处理:
- @response_wrapper: 自动包装返回值为ApiResponse
- @paginated_response: 自动处理分页响应
- extract_trace_id: 从请求中提取追踪ID

使用示例:
    @router.get("/users")
    @response_wrapper
    async def get_users():
        return {"users": [...]}  # 自动包装为ApiResponse

    @router.get("/users/list")
    @paginated_response
    async def list_users(page: int = 1):
        return items, 100  # 返回(data, total)元组
"""

from functools import wraps
from typing import Callable, Any, Tuple, Optional, Union
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import uuid
import traceback

from app.schemas.response import (
    ApiResponse,
    ResponseCode,
    ValidationErrorResponse,
    ErrorDetail
)
from app.logger import logger


def extract_trace_id(request: Optional[Request] = None) -> str:
    """从请求中提取或生成追踪ID

    Args:
        request: FastAPI请求对象

    Returns:
        追踪ID字符串

    Examples:
        >>> trace_id = extract_trace_id(request)
        >>> logger.info("处理请求", extra={"trace_id": trace_id})
    """
    if request and hasattr(request.state, "trace_id"):
        return request.state.trace_id

    # 尝试从请求头获取
    if request and request.headers.get("X-Trace-ID"):
        return request.headers["X-Trace-ID"]

    # 生成新的追踪ID
    return f"req-{uuid.uuid4().hex[:16]}"


def response_wrapper(
    success_code: int = ResponseCode.SUCCESS,
    success_message: str = "操作成功",
    include_trace_id: bool = True
):
    """响应包装装饰器

    自动将路由函数的返回值包装为标准ApiResponse格式。

    支持的返回值类型:
        - dict/list/str/int等: 包装为data字段
        - ApiResponse: 直接返回
        - tuple(data, message): 自定义消息
        - None: 返回成功响应,无数据

    异常处理:
        - HTTPException: 转换为失败响应
        - 其他异常: 记录日志并返回500错误

    Args:
        success_code: 成功时的HTTP状态码,默认200
        success_message: 成功时的消息,默认"操作成功"
        include_trace_id: 是否包含追踪ID,默认True

    Returns:
        装饰后的函数

    Examples:
        >>> @router.get("/users/{user_id}")
        >>> @response_wrapper(success_message="查询成功")
        >>> async def get_user(user_id: int):
        ...     return {"id": user_id, "name": "张三"}

        >>> @router.post("/users")
        >>> @response_wrapper(success_code=201, success_message="创建成功")
        >>> async def create_user(user: UserCreate):
        ...     return new_user
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            request = kwargs.get('request') or next(
                (arg for arg in args if isinstance(arg, Request)),
                None
            )
            trace_id = extract_trace_id(request) if include_trace_id else None

            try:
                # 执行原函数
                result = await func(*args, **kwargs)

                # 如果已经是ApiResponse,直接返回
                if isinstance(result, ApiResponse):
                    if trace_id and not result.trace_id:
                        result.trace_id = trace_id
                    return result

                # 处理元组返回值 (data, message)
                if isinstance(result, tuple) and len(result) == 2:
                    data, message = result
                    return ApiResponse.success(
                        data=data,
                        message=message,
                        code=success_code,
                        trace_id=trace_id
                    )

                # 包装普通返回值
                return ApiResponse.success(
                    data=result,
                    message=success_message,
                    code=success_code,
                    trace_id=trace_id
                )

            except HTTPException as e:
                # 处理FastAPI的HTTPException
                logger.warning(
                    f"HTTP异常: {e.detail}",
                    extra={"trace_id": trace_id, "status_code": e.status_code}
                )
                return ApiResponse.fail(
                    message=str(e.detail) if isinstance(e.detail, str) else "请求失败",
                    code=e.status_code,
                    data=e.detail if not isinstance(e.detail, str) else None,
                    trace_id=trace_id
                )

            except Exception as e:
                # 处理未预期的异常
                error_msg = str(e)
                logger.error(
                    f"服务器错误: {error_msg}",
                    extra={
                        "trace_id": trace_id,
                        "error_type": type(e).__name__,
                        "traceback": traceback.format_exc()
                    },
                    exc_info=True
                )
                return ApiResponse.fail(
                    message="服务器内部错误",
                    code=ResponseCode.INTERNAL_ERROR,
                    data={"error": error_msg} if logger.level <= 10 else None,  # DEBUG模式返回详情
                    trace_id=trace_id
                )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            """同步函数包装器"""
            request = kwargs.get('request') or next(
                (arg for arg in args if isinstance(arg, Request)),
                None
            )
            trace_id = extract_trace_id(request) if include_trace_id else None

            try:
                result = func(*args, **kwargs)

                if isinstance(result, ApiResponse):
                    if trace_id and not result.trace_id:
                        result.trace_id = trace_id
                    return result

                if isinstance(result, tuple) and len(result) == 2:
                    data, message = result
                    return ApiResponse.success(
                        data=data,
                        message=message,
                        code=success_code,
                        trace_id=trace_id
                    )

                return ApiResponse.success(
                    data=result,
                    message=success_message,
                    code=success_code,
                    trace_id=trace_id
                )

            except HTTPException as e:
                logger.warning(
                    f"HTTP异常: {e.detail}",
                    extra={"trace_id": trace_id, "status_code": e.status_code}
                )
                return ApiResponse.fail(
                    message=str(e.detail) if isinstance(e.detail, str) else "请求失败",
                    code=e.status_code,
                    data=e.detail if not isinstance(e.detail, str) else None,
                    trace_id=trace_id
                )

            except Exception as e:
                error_msg = str(e)
                logger.error(
                    f"服务器错误: {error_msg}",
                    extra={
                        "trace_id": trace_id,
                        "error_type": type(e).__name__,
                        "traceback": traceback.format_exc()
                    },
                    exc_info=True
                )
                return ApiResponse.fail(
                    message="服务器内部错误",
                    code=ResponseCode.INTERNAL_ERROR,
                    data={"error": error_msg} if logger.level <= 10 else None,
                    trace_id=trace_id
                )

        # 根据函数类型返回对应的包装器
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def paginated_response(
    success_message: str = "查询成功",
    default_page_size: int = 20
):
    """分页响应装饰器

    自动处理分页响应包装。函数应返回(data, total)元组。

    Args:
        success_message: 成功消息
        default_page_size: 默认每页大小

    Returns:
        装饰后的函数

    Examples:
        >>> @router.get("/users")
        >>> @paginated_response(success_message="用户列表获取成功")
        >>> async def list_users(
        ...     page: int = 1,
        ...     page_size: int = 20
        ... ):
        ...     users = [...]  # 查询用户列表
        ...     total = 100    # 总数
        ...     return users, total  # 返回元组

    Note:
        - 函数必须返回(data, total)元组
        - 路由参数需包含page和page_size(可选)
        - page_size会限制在1-1000之间
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            request = kwargs.get('request') or next(
                (arg for arg in args if isinstance(arg, Request)),
                None
            )
            trace_id = extract_trace_id(request)

            # 提取分页参数
            page = kwargs.get('page', 1)
            page_size = kwargs.get('page_size', default_page_size)

            # 限制page_size范围
            page_size = max(1, min(page_size, 1000))

            try:
                # 执行原函数
                result = await func(*args, **kwargs)

                # 必须返回(data, total)元组
                if not isinstance(result, tuple) or len(result) != 2:
                    raise ValueError(
                        "分页接口必须返回(data, total)元组"
                    )

                data, total = result

                return ApiResponse.success_with_pagination(
                    data=data,
                    total=total,
                    page=page,
                    page_size=page_size,
                    message=success_message,
                    trace_id=trace_id
                )

            except HTTPException as e:
                logger.warning(
                    f"HTTP异常: {e.detail}",
                    extra={"trace_id": trace_id}
                )
                return ApiResponse.fail(
                    message=str(e.detail) if isinstance(e.detail, str) else "请求失败",
                    code=e.status_code,
                    trace_id=trace_id
                )

            except Exception as e:
                logger.error(
                    f"分页查询错误: {str(e)}",
                    extra={"trace_id": trace_id},
                    exc_info=True
                )
                return ApiResponse.fail(
                    message="查询失败",
                    code=ResponseCode.INTERNAL_ERROR,
                    trace_id=trace_id
                )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            """同步函数包装器"""
            request = kwargs.get('request') or next(
                (arg for arg in args if isinstance(arg, Request)),
                None
            )
            trace_id = extract_trace_id(request)

            page = kwargs.get('page', 1)
            page_size = kwargs.get('page_size', default_page_size)
            page_size = max(1, min(page_size, 1000))

            try:
                result = func(*args, **kwargs)

                if not isinstance(result, tuple) or len(result) != 2:
                    raise ValueError("分页接口必须返回(data, total)元组")

                data, total = result

                return ApiResponse.success_with_pagination(
                    data=data,
                    total=total,
                    page=page,
                    page_size=page_size,
                    message=success_message,
                    trace_id=trace_id
                )

            except HTTPException as e:
                logger.warning(
                    f"HTTP异常: {e.detail}",
                    extra={"trace_id": trace_id}
                )
                return ApiResponse.fail(
                    message=str(e.detail) if isinstance(e.detail, str) else "请求失败",
                    code=e.status_code,
                    trace_id=trace_id
                )

            except Exception as e:
                logger.error(
                    f"分页查询错误: {str(e)}",
                    extra={"trace_id": trace_id},
                    exc_info=True
                )
                return ApiResponse.fail(
                    message="查询失败",
                    code=ResponseCode.INTERNAL_ERROR,
                    trace_id=trace_id
                )

        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def create_error_response(
    exception: Exception,
    trace_id: Optional[str] = None
) -> ApiResponse:
    """从异常创建错误响应

    Args:
        exception: 异常对象
        trace_id: 追踪ID

    Returns:
        错误响应对象

    Examples:
        >>> try:
        ...     raise ValueError("参数错误")
        ... except Exception as e:
        ...     return create_error_response(e, trace_id)
    """
    if isinstance(exception, HTTPException):
        return ApiResponse.fail(
            message=str(exception.detail),
            code=exception.status_code,
            trace_id=trace_id
        )

    logger.error(
        f"创建错误响应: {str(exception)}",
        extra={"trace_id": trace_id},
        exc_info=True
    )

    return ApiResponse.fail(
        message="服务器内部错误",
        code=ResponseCode.INTERNAL_ERROR,
        data={"error": str(exception)} if logger.level <= 10 else None,
        trace_id=trace_id
    )

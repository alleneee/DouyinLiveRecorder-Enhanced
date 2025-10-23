"""响应体封装单元测试

测试覆盖:
1. ApiResponse基础功能
2. 成功/失败响应构建
3. 分页响应生成
4. 装饰器功能
5. 边界条件和异常处理
"""

import pytest
from datetime import datetime
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app.schemas.response import (
    ApiResponse,
    ResponseCode,
    PaginationMeta,
    ErrorDetail,
    ValidationErrorResponse
)
from app.utils.response_wrapper import (
    response_wrapper,
    paginated_response,
    extract_trace_id,
    create_error_response
)


# ============================================================
# 测试ApiResponse基础功能
# ============================================================

class TestApiResponse:
    """ApiResponse类测试"""

    def test_success_response_basic(self):
        """测试基础成功响应"""
        response = ApiResponse.success(
            data={"user_id": 123},
            message="操作成功"
        )

        assert response.code == ResponseCode.SUCCESS
        assert response.success is True
        assert response.message == "操作成功"
        assert response.data == {"user_id": 123}
        assert response.pagination is None

    def test_success_response_with_custom_code(self):
        """测试自定义状态码的成功响应"""
        response = ApiResponse.success(
            data={"id": 1},
            message="创建成功",
            code=ResponseCode.CREATED
        )

        assert response.code == 201
        assert response.success is True
        assert response.message == "创建成功"

    def test_success_response_no_data(self):
        """测试无数据的成功响应"""
        response = ApiResponse.success(message="删除成功")

        assert response.code == ResponseCode.SUCCESS
        assert response.success is True
        assert response.message == "删除成功"
        assert response.data is None

    def test_fail_response_basic(self):
        """测试基础失败响应"""
        response = ApiResponse.fail(
            message="参数错误",
            code=ResponseCode.BAD_REQUEST
        )

        assert response.code == 400
        assert response.success is False
        assert response.message == "参数错误"
        assert response.data is None

    def test_fail_response_with_data(self):
        """测试带数据的失败响应"""
        error_data = {"field": "email", "error": "格式不正确"}
        response = ApiResponse.fail(
            message="验证失败",
            code=ResponseCode.UNPROCESSABLE_ENTITY,
            data=error_data
        )

        assert response.code == 422
        assert response.success is False
        assert response.data == error_data

    def test_response_timestamp(self):
        """测试响应时间戳生成"""
        response = ApiResponse.success(data={})

        # 验证时间戳格式
        timestamp = datetime.fromisoformat(response.timestamp)
        assert isinstance(timestamp, datetime)

    def test_response_trace_id(self):
        """测试追踪ID"""
        trace_id = "test-trace-123"
        response = ApiResponse.success(
            data={},
            trace_id=trace_id
        )

        assert response.trace_id == trace_id


# ============================================================
# 测试分页功能
# ============================================================

class TestPagination:
    """分页功能测试"""

    def test_pagination_meta_creation(self):
        """测试分页元数据创建"""
        meta = PaginationMeta.from_params(
            total=100,
            page=1,
            page_size=20
        )

        assert meta.total == 100
        assert meta.page == 1
        assert meta.page_size == 20
        assert meta.total_pages == 5
        assert meta.has_next is True
        assert meta.has_prev is False

    def test_pagination_last_page(self):
        """测试最后一页分页"""
        meta = PaginationMeta.from_params(
            total=100,
            page=5,
            page_size=20
        )

        assert meta.has_next is False
        assert meta.has_prev is True

    def test_pagination_middle_page(self):
        """测试中间页分页"""
        meta = PaginationMeta.from_params(
            total=100,
            page=3,
            page_size=20
        )

        assert meta.has_next is True
        assert meta.has_prev is True

    def test_pagination_single_page(self):
        """测试单页情况"""
        meta = PaginationMeta.from_params(
            total=10,
            page=1,
            page_size=20
        )

        assert meta.total_pages == 1
        assert meta.has_next is False
        assert meta.has_prev is False

    def test_pagination_zero_total(self):
        """测试零记录分页"""
        meta = PaginationMeta.from_params(
            total=0,
            page=1,
            page_size=20
        )

        assert meta.total_pages == 0
        assert meta.has_next is False
        assert meta.has_prev is False

    def test_success_with_pagination(self):
        """测试分页成功响应"""
        data = [{"id": 1}, {"id": 2}]
        response = ApiResponse.success_with_pagination(
            data=data,
            total=100,
            page=1,
            page_size=20
        )

        assert response.success is True
        assert response.data == data
        assert response.pagination is not None
        assert response.pagination.total == 100
        assert response.pagination.page == 1


# ============================================================
# 测试装饰器功能
# ============================================================

class TestDecorators:
    """装饰器功能测试"""

    def test_response_wrapper_basic(self):
        """测试基础响应包装"""
        @response_wrapper()
        async def test_func():
            return {"test": "data"}

        import asyncio
        result = asyncio.run(test_func())

        assert isinstance(result, ApiResponse)
        assert result.success is True
        assert result.data == {"test": "data"}

    def test_response_wrapper_with_custom_message(self):
        """测试自定义消息的响应包装"""
        @response_wrapper(success_message="自定义成功消息")
        async def test_func():
            return {"test": "data"}

        import asyncio
        result = asyncio.run(test_func())

        assert result.message == "自定义成功消息"

    def test_response_wrapper_tuple_return(self):
        """测试元组返回值"""
        @response_wrapper()
        async def test_func():
            return {"test": "data"}, "操作完成"

        import asyncio
        result = asyncio.run(test_func())

        assert result.message == "操作完成"
        assert result.data == {"test": "data"}

    def test_response_wrapper_http_exception(self):
        """测试HTTPException处理"""
        @response_wrapper()
        async def test_func():
            raise HTTPException(status_code=404, detail="资源不存在")

        import asyncio
        result = asyncio.run(test_func())

        assert isinstance(result, ApiResponse)
        assert result.success is False
        assert result.code == 404
        assert "资源不存在" in result.message

    def test_response_wrapper_general_exception(self):
        """测试普通异常处理"""
        @response_wrapper()
        async def test_func():
            raise ValueError("测试错误")

        import asyncio
        result = asyncio.run(test_func())

        assert isinstance(result, ApiResponse)
        assert result.success is False
        assert result.code == ResponseCode.INTERNAL_ERROR

    def test_paginated_response_decorator(self):
        """测试分页装饰器"""
        @paginated_response()
        async def test_func(page: int = 1, page_size: int = 20):
            data = [{"id": i} for i in range(1, 21)]
            return data, 100

        import asyncio
        result = asyncio.run(test_func(page=1, page_size=20))

        assert isinstance(result, ApiResponse)
        assert result.success is True
        assert result.pagination is not None
        assert result.pagination.total == 100
        assert len(result.data) == 20

    def test_paginated_response_invalid_return(self):
        """测试分页装饰器无效返回值"""
        @paginated_response()
        async def test_func(page: int = 1, page_size: int = 20):
            return [{"id": 1}]  # 应该返回元组

        import asyncio
        result = asyncio.run(test_func())

        assert result.success is False


# ============================================================
# 测试工具函数
# ============================================================

class TestUtilityFunctions:
    """工具函数测试"""

    def test_extract_trace_id_from_request(self):
        """测试从请求提取追踪ID"""
        # 模拟请求对象
        class MockRequest:
            def __init__(self):
                self.state = type('obj', (object,), {'trace_id': 'req-123'})()

        request = MockRequest()
        trace_id = extract_trace_id(request)

        assert trace_id == 'req-123'

    def test_extract_trace_id_generation(self):
        """测试追踪ID生成"""
        trace_id = extract_trace_id(None)

        assert trace_id.startswith('req-')
        assert len(trace_id) > 4

    def test_create_error_response_http_exception(self):
        """测试从HTTPException创建错误响应"""
        exception = HTTPException(status_code=400, detail="参数错误")
        response = create_error_response(exception)

        assert isinstance(response, ApiResponse)
        assert response.success is False
        assert response.code == 400

    def test_create_error_response_general_exception(self):
        """测试从普通异常创建错误响应"""
        exception = ValueError("测试错误")
        response = create_error_response(exception, trace_id="test-123")

        assert isinstance(response, ApiResponse)
        assert response.success is False
        assert response.code == ResponseCode.INTERNAL_ERROR
        assert response.trace_id == "test-123"


# ============================================================
# 测试错误详情
# ============================================================

class TestErrorDetail:
    """错误详情测试"""

    def test_error_detail_creation(self):
        """测试错误详情创建"""
        error = ErrorDetail(
            field="email",
            message="邮箱格式不正确",
            code="INVALID_EMAIL"
        )

        assert error.field == "email"
        assert error.message == "邮箱格式不正确"
        assert error.code == "INVALID_EMAIL"

    def test_validation_error_response(self):
        """测试验证错误响应"""
        errors = [
            ErrorDetail(field="email", message="邮箱格式不正确"),
            ErrorDetail(field="name", message="名称不能为空")
        ]

        response = ValidationErrorResponse.from_validation_error(errors)

        assert response.success is False
        assert response.code == ResponseCode.UNPROCESSABLE_ENTITY
        assert len(response.data) == 2


# ============================================================
# 测试边界条件
# ============================================================

class TestEdgeCases:
    """边界条件测试"""

    def test_very_large_pagination(self):
        """测试大数据量分页"""
        meta = PaginationMeta.from_params(
            total=1000000,
            page=1,
            page_size=100
        )

        assert meta.total_pages == 10000
        assert meta.has_next is True

    def test_empty_data_success_response(self):
        """测试空数据成功响应"""
        response = ApiResponse.success(data=[])

        assert response.success is True
        assert response.data == []

    def test_none_data_success_response(self):
        """测试None数据成功响应"""
        response = ApiResponse.success(data=None)

        assert response.success is True
        assert response.data is None

    def test_complex_nested_data(self):
        """测试复杂嵌套数据"""
        complex_data = {
            "user": {
                "id": 1,
                "profile": {
                    "name": "测试",
                    "settings": {
                        "theme": "dark"
                    }
                }
            },
            "items": [1, 2, 3]
        }

        response = ApiResponse.success(data=complex_data)

        assert response.data == complex_data
        assert response.data["user"]["profile"]["settings"]["theme"] == "dark"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

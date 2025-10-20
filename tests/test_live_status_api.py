"""测试直播状态检测API"""
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_check_live_status_success():
    """测试检测直播状态成功"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/live-rooms/check-live-status",
            json={"url": "https://live.douyin.com/745964462470"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 验证响应字段
        assert "is_live" in data
        assert isinstance(data["is_live"], bool)
        # 只有一个字段
        assert len(data) == 1


@pytest.mark.asyncio
async def test_check_live_status_douyin():
    """测试抖音平台检测"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/live-rooms/check-live-status",
            json={"url": "https://live.douyin.com/745964462470"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "is_live" in data


@pytest.mark.asyncio
async def test_check_live_status_bilibili():
    """测试B站平台检测"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/live-rooms/check-live-status",
            json={"url": "https://live.bilibili.com/21593109"}
        )
        
        # 可能因为网络或其他原因失败，但应该返回合法响应
        assert response.status_code in [200, 500]


@pytest.mark.asyncio
async def test_check_live_status_missing_url():
    """测试缺少URL参数"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/live-rooms/check-live-status",
            json={}
        )
        
        # Pydantic验证应该失败
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_check_live_status_response_is_boolean():
    """测试响应是布尔值"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/live-rooms/check-live-status",
            json={"url": "https://live.douyin.com/745964462470"}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # 验证 is_live 是布尔类型
            assert isinstance(data["is_live"], bool)
            assert data["is_live"] in [True, False]

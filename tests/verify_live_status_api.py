"""手动验证直播状态检测API"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.live_recorder import LiveRecorder
from loguru import logger


async def test_live_status_check():
    """测试直播状态检测功能"""
    
    # 测试URL列表
    test_urls = [
        ("抖音", "https://live.douyin.com/745964462470"),
        ("B站", "https://live.bilibili.com/21593109"),
        ("快手", "https://live.kuaishou.com/u/xxx"),
    ]
    
    recorder = LiveRecorder(proxy_addr=None, cookies={})
    
    logger.info("=" * 60)
    logger.info("开始测试直播状态检测功能")
    logger.info("=" * 60)
    
    for platform, url in test_urls:
        logger.info(f"\n测试平台: {platform}")
        logger.info(f"URL: {url}")
        
        try:
            # 检测直播状态（简化版）
            is_live = await recorder.check_live_status(url)
            
            logger.info(f"是否直播: {is_live}")
            logger.success(f"✅ {platform} 检测成功")
            
        except Exception as e:
            logger.error(f"❌ {platform} 检测失败: {e}")
        
        logger.info("-" * 60)
        
        # 避免请求过快
        await asyncio.sleep(1)
    
    logger.info("\n测试完成!")


async def test_api_endpoint():
    """测试API端点（需要先启动服务）"""
    import httpx
    
    api_url = "http://localhost:8000/api/live-rooms/check-live-status"
    
    test_cases = [
        {
            "name": "抖音直播间",
            "url": "https://live.douyin.com/745964462470"
        },
        {
            "name": "B站直播间",
            "url": "https://live.bilibili.com/21593109"
        }
    ]
    
    logger.info("\n" + "=" * 60)
    logger.info("开始测试API端点（需要服务运行在 http://localhost:8000）")
    logger.info("=" * 60)
    
    async with httpx.AsyncClient() as client:
        for test in test_cases:
            logger.info(f"\n测试: {test['name']}")
            logger.info(f"URL: {test['url']}")
            
            try:
                response = await client.post(
                    api_url,
                    json={"url": test['url']},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"是否直播: {data['is_live']}")
                    logger.success(f"✅ API调用成功")
                else:
                    logger.error(f"❌ API返回错误: {response.status_code}")
                    logger.error(f"响应: {response.text}")
                    
            except httpx.ConnectError:
                logger.error("❌ 无法连接到API服务，请先启动服务: python app/run.py")
                break
            except Exception as e:
                logger.error(f"❌ API调用失败: {e}")
            
            logger.info("-" * 60)
            await asyncio.sleep(1)


async def main():
    """主函数"""
    logger.info("直播状态检测功能验证")
    logger.info("选择测试模式:")
    logger.info("1. 测试核心功能（LiveRecorder）")
    logger.info("2. 测试API端点（需要启动服务）")
    logger.info("3. 全部测试")
    
    choice = input("\n请选择 (1/2/3): ").strip()
    
    if choice == "1":
        await test_live_status_check()
    elif choice == "2":
        await test_api_endpoint()
    elif choice == "3":
        await test_live_status_check()
        await test_api_endpoint()
    else:
        logger.warning("无效选择")


if __name__ == "__main__":
    asyncio.run(main())

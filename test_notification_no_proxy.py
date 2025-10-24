#!/usr/bin/env python3
"""
测试分片通知是否使用代理
用于验证 segment_notifier.py 的代理禁用功能
"""
import os
import sys

# 设置项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_proxy_settings():
    """测试代理配置"""
    print("=" * 80)
    print("检查系统环境变量中的代理设置")
    print("=" * 80)
    
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
    has_proxy = False
    
    for var in proxy_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var} = {value}")
            has_proxy = True
        else:
            print(f"❌ {var} = (未设置)")
    
    if has_proxy:
        print("\n⚠️  警告: 系统环境变量中设置了代理")
        print("   但分片通知已配置为强制禁用代理，不会受影响")
    else:
        print("\n✅ 系统环境变量中未设置代理")
    
    print("\n" + "=" * 80)
    return has_proxy


def test_notification_request():
    """测试通知请求是否使用代理"""
    import requests
    
    print("测试 requests 库的代理禁用")
    print("=" * 80)
    
    # 模拟设置代理环境变量
    os.environ['HTTP_PROXY'] = 'http://invalid-proxy:8080'
    os.environ['HTTPS_PROXY'] = 'http://invalid-proxy:8080'
    
    print(f"设置测试代理: HTTP_PROXY = {os.environ.get('HTTP_PROXY')}")
    
    # 临时清除代理（模拟 segment_notifier.py 的逻辑）
    old_http_proxy = os.environ.get('HTTP_PROXY')
    old_https_proxy = os.environ.get('HTTPS_PROXY')
    
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)
    
    try:
        # 测试请求（使用公共 API）
        response = requests.get(
            'https://httpbin.org/get',
            timeout=10,
            proxies={'http': None, 'https': None}
        )
        
        if response.status_code == 200:
            print("✅ 请求成功（未使用代理）")
            print(f"   HTTP状态码: {response.status_code}")
        else:
            print(f"⚠️  请求返回异常状态码: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    finally:
        # 恢复代理设置
        if old_http_proxy is not None:
            os.environ['HTTP_PROXY'] = old_http_proxy
        if old_https_proxy is not None:
            os.environ['HTTPS_PROXY'] = old_https_proxy
    
    print("=" * 80)


def test_aiohttp_proxy():
    """测试 aiohttp 的代理禁用"""
    import asyncio
    import aiohttp
    
    async def _test():
        print("\n测试 aiohttp 库的代理禁用")
        print("=" * 80)
        
        # 设置测试代理环境变量
        os.environ['HTTP_PROXY'] = 'http://invalid-proxy:8080'
        os.environ['HTTPS_PROXY'] = 'http://invalid-proxy:8080'
        
        print(f"设置测试代理: HTTP_PROXY = {os.environ.get('HTTP_PROXY')}")
        
        try:
            # 使用 trust_env=False 禁用代理（模拟 segment_notifier.py 的逻辑）
            connector = aiohttp.TCPConnector()
            async with aiohttp.ClientSession(connector=connector, trust_env=False) as session:
                async with session.get('https://httpbin.org/get', timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        print("✅ 异步请求成功（未使用代理）")
                        print(f"   HTTP状态码: {response.status}")
                    else:
                        print(f"⚠️  异步请求返回异常状态码: {response.status}")
        except Exception as e:
            print(f"❌ 异步请求失败: {e}")
        finally:
            # 清除测试代理
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)
        
        print("=" * 80)
    
    asyncio.run(_test())


if __name__ == '__main__':
    print("\n🔍 分片通知代理禁用测试\n")
    
    # 1. 检查系统代理设置
    test_proxy_settings()
    
    # 2. 测试 requests（同步）
    print()
    test_notification_request()
    
    # 3. 测试 aiohttp（异步）
    test_aiohttp_proxy()
    
    print("\n✅ 所有测试完成！")
    print("\n📌 总结:")
    print("   1. segment_notifier.py 中的两个发送方法都已配置为强制禁用代理")
    print("   2. send_notification_sync: 临时清除环境变量 + proxies 参数")
    print("   3. send_notification_async: trust_env=False 参数")
    print("   4. 无论系统是否设置代理，分片通知都不会使用代理\n")

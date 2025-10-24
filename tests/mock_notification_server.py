"""Mock 分片通知接收端服务器

用于测试分片通知发送功能

运行方式:
python tests/mock_notification_server.py

然后在 .env 中配置:
SEGMENT_NOTIFICATION_BASE_URL=http://localhost:8888

特性:
1. 接收并打印通知内容
2. 模拟不同的响应场景(成功/失败)
3. 统计接收情况
4. 详细日志输出
"""
import json
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
import uvicorn


app = FastAPI(title="分片通知Mock服务器")

# 统计信息
stats = {
    'total_received': 0,
    'success_count': 0,
    'error_count': 0,
    'notifications': []
}


@app.post("/shard/plan")
async def receive_notification(request: Request):
    """
    接收分片通知

    模拟响应模式:
    - 正常模式: 返回 200 + {"code": 0, "message": "success"}
    - 可通过查询参数模拟错误: ?error=400
    """
    # 获取请求数据
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"code": -1, "message": f"Invalid JSON: {str(e)}"}
        )

    # 更新统计
    stats['total_received'] += 1

    # 记录通知
    notification_record = {
        'received_at': datetime.now().isoformat(),
        'data': data
    }
    stats['notifications'].append(notification_record)

    # 打印详细信息
    print("\n" + "="*80)
    print(f"🔔 收到分片通知 #{stats['total_received']}")
    print("="*80)
    print(f"⏰ 接收时间: {notification_record['received_at']}")

    # 解析数据
    live_info = data.get('live_info', {})
    sub_video = data.get('sub_video_info', {})

    print(f"\n📺 直播信息:")
    print(f"  名称: {live_info.get('live_name')}")
    print(f"  URL: {live_info.get('live_url')}")
    print(f"  直播ID: {live_info.get('live_id')}")

    print(f"\n🎬 分片信息:")
    print(f"  序号: {sub_video.get('serial_num')}")
    print(f"  时长: {sub_video.get('duration')}秒")
    print(f"  开始时间: {sub_video.get('absolute_start_time')}")
    print(f"  结束时间: {sub_video.get('absolute_end_time')}")
    print(f"  最后分片: {sub_video.get('last_segment_flag', False)}")

    print(f"\n📁 文件地址:")
    print(f"  视频: {sub_video.get('video_url')}")
    print(f"  音频: {sub_video.get('audio_url')}")

    # 检查是否模拟错误
    error_code = request.query_params.get('error')

    if error_code:
        # 模拟错误响应
        error_code = int(error_code)
        stats['error_count'] += 1

        print(f"\n⚠️  模拟错误响应: HTTP {error_code}")
        print("="*80 + "\n")

        return JSONResponse(
            status_code=error_code,
            content={
                "code": -1,
                "message": f"Simulated error {error_code}"
            }
        )

    # 正常响应
    stats['success_count'] += 1

    print(f"\n✅ 返回成功响应")
    print("="*80 + "\n")

    return JSONResponse(
        status_code=200,
        content={
            "code": 0,
            "message": "success",
            "data": {
                "received_at": notification_record['received_at'],
                "segment_index": sub_video.get('serial_num')
            }
        }
    )


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    return JSONResponse(content=stats)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "notification-mock-server"}


@app.on_event("startup")
async def startup_event():
    """启动时打印信息"""
    print("\n" + "🚀"*40)
    print("分片通知 Mock 服务器启动成功!")
    print("🚀"*40)
    print(f"\n📡 监听地址: http://localhost:8888")
    print(f"📋 通知接口: http://localhost:8888/shard/plan")
    print(f"📊 统计接口: http://localhost:8888/stats")
    print(f"💚 健康检查: http://localhost:8888/health")

    print(f"\n⚙️  配置方法:")
    print(f"在 .env 文件中添加:")
    print(f"  SEGMENT_NOTIFICATION_BASE_URL=http://localhost:8888")

    print(f"\n🧪 测试方法:")
    print(f"1. 运行本服务: python tests/mock_notification_server.py")
    print(f"2. 配置 .env: SEGMENT_NOTIFICATION_BASE_URL=http://localhost:8888")
    print(f"3. 运行测试: python tests/test_notification_with_real_data.py")

    print(f"\n💡 模拟错误响应:")
    print(f"  修改代码中的 notification_url 添加参数: ?error=400")
    print(f"  或手动测试: curl -X POST http://localhost:8888/shard/plan?error=500")

    print("\n" + "="*80 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时打印统计"""
    print("\n" + "📊"*40)
    print("服务关闭 - 统计信息")
    print("📊"*40)
    print(f"总接收: {stats['total_received']}")
    print(f"成功: {stats['success_count']}")
    print(f"错误: {stats['error_count']}")
    print("="*80 + "\n")


def main():
    """启动服务器"""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8888,
        log_level="info"
    )


if __name__ == '__main__':
    main()

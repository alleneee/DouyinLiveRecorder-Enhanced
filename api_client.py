#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API客户端模块
用于调用外部接口，包括获取令牌和通知后处理结果
"""

import json
import time
import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode


class APIClient:
    """API客户端类"""

    def __init__(self):
        """
        初始化API客户端
        """
        # 写死的配置参数 - 测试环境
        self.domain = "data-application-test.topsports.com.cn"
        self.client_id = "ts-python-live"
        self.client_secret = "asdasdfagafaqwewqrqfasf"
        self.notification_endpoint = "/api/v1/liveRecord/receive"

        # 请求设置
        self.timeout = 30
        self.retry_count = 3
        self.retry_delay = 5

        self.token = None
        self.token_expires_at = 0
        
    def get_auth_token(self) -> Optional[str]:
        """
        获取认证令牌
        :return: 令牌字符串，失败返回None
        """
        # 检查令牌是否还有效
        if self.token and time.time() < self.token_expires_at:
            return self.token

        # 构建请求URL
        params = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

        url = f"https://{self.domain}/auth-token/oauth2/client_token?{urlencode(params)}"

        for attempt in range(self.retry_count):
            try:
                print(f"正在获取API令牌... (尝试 {attempt + 1}/{self.retry_count})")
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()

                data = response.json()

                if data.get('code') == 200:
                    token_data = data.get('data', {})
                    self.token = token_data.get('client_token')
                    expires_in = int(token_data.get('expires_in', 0))

                    # 设置令牌过期时间（提前60秒过期以确保安全）
                    self.token_expires_at = time.time() + expires_in - 60

                    print(f"API令牌获取成功，有效期: {expires_in}秒")
                    return self.token
                else:
                    print(f"获取API令牌失败: {data.get('msg', '未知错误')}")
                    return None

            except requests.exceptions.RequestException as e:
                print(f"获取API令牌时网络错误 (尝试 {attempt + 1}): {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay)
                    continue
            except json.JSONDecodeError as e:
                print(f"解析API令牌响应失败: {e}")
                return None
            except Exception as e:
                print(f"获取API令牌时发生未知错误: {e}")
                return None

        print("获取API令牌失败，已达到最大重试次数")
        return None
    
    def notify_post_process_result(self, live_records: List[Dict[str, Any]]) -> bool:
        """
        通知后处理结果
        :param live_records: 直播录制数据列表
        :return: 成功返回True，失败返回False
        """
        # 获取令牌
        token = self.get_auth_token()
        if not token:
            print("无法获取API令牌，跳过结果通知")
            return False

        # 构建请求头
        headers = {
            'auth-token': token,
            'Content-Type': 'application/json'
        }

        # 构建请求URL
        url = f"https://{self.domain}{self.notification_endpoint}"

        for attempt in range(self.retry_count):
            try:
                print(f"正在发送后处理结果通知... (尝试 {attempt + 1}/{self.retry_count})")
                print(f"请求URL: {url}")
                print(f"发送数据: {json.dumps(live_records, ensure_ascii=False, indent=2)}")

                response = requests.post(url, json=live_records, headers=headers, timeout=self.timeout)
                response.raise_for_status()

                result = response.json()
                if result.get('code') == 0:  # 根据接口文档，成功时code为0
                    print("后处理结果通知发送成功")
                    print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    return True
                else:
                    print(f"后处理结果通知发送失败: {result.get('msg', '未知错误')}")
                    return False

            except requests.exceptions.RequestException as e:
                print(f"发送结果通知时网络错误 (尝试 {attempt + 1}): {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay)
                    continue
            except json.JSONDecodeError as e:
                print(f"解析结果通知响应失败: {e}")
                return False
            except Exception as e:
                print(f"发送结果通知时发生未知错误: {e}")
                return False

        print("发送后处理结果通知失败，已达到最大重试次数")
        return False


def create_live_record_data(record_name: str, room_id: str, record_start_time: str,
                           record_date: str, record_file_name: str,
                           m3u8_url: str = None, ts_url: str = None,
                           mp3_urls: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    创建直播录制数据
    :param record_name: 录制名称
    :param room_id: 房间ID (authorAwemeId)
    :param record_start_time: 录制开始时间
    :param record_date: 录制日期
    :param record_file_name: 录制文件名称
    :param m3u8_url: M3U8文件URL
    :param ts_url: TS文件URL
    :param mp3_urls: MP3文件URL列表
    :return: 直播录制数据字典
    """
    live_record = {
        'authorAwemeId': room_id,
        'recordDate': record_date,
        'recordFileName': record_file_name,
        'recordBeginTime': record_start_time
    }

    # 添加可选字段
    if m3u8_url:
        live_record['m3u8Url'] = m3u8_url

    if ts_url:
        live_record['tsUrl'] = ts_url

    if mp3_urls:
        live_record['liveRecordMp3ReceiveInfo'] = mp3_urls

    return live_record


def create_mp3_info(section: int, mp3_url: str) -> Dict[str, Any]:
    """
    创建MP3信息
    :param section: 第几部分的MP3
    :param mp3_url: MP3文件URL
    :return: MP3信息字典
    """
    return {
        'section': section,
        'mp3Url': mp3_url
    }


# 测试函数
def test_api_client():
    """测试API客户端功能"""
    client = APIClient()

    # 测试获取令牌
    token = client.get_auth_token()
    print(f"获取到的令牌: {token}")

    # 创建测试数据
    mp3_infos = [
        create_mp3_info(1, "https://bucket.oss-cn-beijing.aliyuncs.com/live-records/20240115/123456-测试主播/audio/test_part001_of_003.mp3"),
        create_mp3_info(2, "https://bucket.oss-cn-beijing.aliyuncs.com/live-records/20240115/123456-测试主播/audio/test_part002_of_003.mp3"),
        create_mp3_info(3, "https://bucket.oss-cn-beijing.aliyuncs.com/live-records/20240115/123456-测试主播/audio/test_part003_of_003.mp3")
    ]

    live_record = create_live_record_data(
        record_name="测试主播",
        room_id="123456",
        record_start_time="2024-01-15 14:30:45",
        record_date="2024-01-15",
        record_file_name="测试主播_2024-01-15_14-30-45.ts",
        m3u8_url="https://bucket.oss-cn-beijing.aliyuncs.com/live-records/20240115/123456-测试主播/m3u8/test.m3u8",
        ts_url="https://bucket.oss-cn-beijing.aliyuncs.com/live-records/20240115/123456-测试主播/video/test.ts",
        mp3_urls=mp3_infos
    )

    # 测试结果通知
    result = client.notify_post_process_result([live_record])
    print(f"结果通知状态: {result}")


if __name__ == "__main__":
    test_api_client()

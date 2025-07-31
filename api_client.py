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

# 添加日志导入
from src.logger import logger


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
        self.notification_endpoint = "/live-streaming/api/v1/liveRecord/receive"

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

                    # 关键日志：API令牌获取成功
                    logger.info(f"API令牌获取成功，有效期: {expires_in}秒")
                    print(f"API令牌获取成功，有效期: {expires_in}秒")
                    return self.token
                else:
                    # 关键日志：API令牌获取失败
                    logger.info(f"获取API令牌失败: {data.get('msg', '未知错误')}")
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

        # 关键日志：API令牌获取最终失败
        logger.info("获取API令牌失败，已达到最大重试次数")
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
                if attempt == 0:  # 只在第一次尝试时打印详细信息
                    print(f"正在发送后处理结果通知...")
                    print(f"请求URL: {url}")
                else:
                    print(f"正在重试发送通知... (尝试 {attempt + 1}/{self.retry_count})")

                response = requests.post(url, json=live_records, headers=headers, timeout=self.timeout)

                response.raise_for_status()
                result = response.json()
                
                # 提取并记录traceid
                trace_id = result.get('traceId', '未知')
                logger.info(f"API响应接收 - 状态码: {response.status_code}, traceId: {trace_id}")
                print(f"响应状态码: {response.status_code}, traceId: {trace_id}")

                if result.get('code') == 0:  # 根据接口文档，成功时code为0
                    logger.info(f"后处理结果通知发送成功 - {result.get('msg', '成功')}")
                    print(f"API通知成功: {result.get('msg', '成功')}")
                    return True
                else:
                    error_msg = result.get('msg', '未知错误')
                    error_code = result.get('code', 'unknown')
                    logger.info(f"后处理结果通知发送失败: {error_msg} (错误码: {error_code})")
                    print(f"API通知失败: {error_msg} (错误码: {error_code})")
                    return False

            except requests.exceptions.RequestException as e:
                logger.error(f"网络错误 (尝试 {attempt + 1}): {e}")
                print(f"网络错误: {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(self.retry_delay)
                    continue
            except json.JSONDecodeError as e:
                logger.error(f"响应解析失败: {e}")
                print(f"响应解析失败: {e}")
                return False
            except Exception as e:
                logger.error(f"未知错误: {e}")
                print(f"未知错误: {e}")
                return False

        logger.error("API通知最终失败，已达到最大重试次数")
        print("API通知最终失败")
        return False


def create_live_record_data(record_name: str, room_id: str, record_start_time: str,
                           record_date: str, record_file_name: str,
                           m3u8_url: Optional[str] = None, video_url: Optional[str] = None,
                           mp3_urls: Optional[List[Dict[str, Any]]] = None,
                           cover_image_url: Optional[str] = None,
                           biz_type: str = "live") -> Dict[str, Any]:
    """
    创建直播录制数据
    :param record_name: 录制名称
    :param room_id: 房间ID (authorAwemeId)
    :param record_start_time: 录制开始时间
    :param record_date: 录制日期
    :param record_file_name: 录制文件名称
    :param m3u8_url: M3U8文件URL
    :param video_url: 视频文件URL (更新字段名为videoUrl)
    :param mp3_urls: MP3文件URL列表
    :param cover_image_url: 封面图片URL (新增字段)
    :param biz_type: 业务类型 (新增字段: "live"=直播, "shortVideo"=短视频)
    :return: 直播录制数据字典
    """

    live_record: Dict[str, Any] = {
        'authorAwemeId': room_id,
        'recordDate': record_date,
        'recordFileName': record_file_name,
        'recordBeginTime': record_start_time,
        'bizType': biz_type  # 新增：业务类型
    }

    # 添加可选字段
    if m3u8_url:
        live_record['m3u8Url'] = m3u8_url

    if video_url:
        # 更新：字段名从 tsUrl 改为 videoUrl
        live_record['videoUrl'] = video_url

    if cover_image_url:
        # 新增：封面图片URL
        live_record['coverImageUrl'] = cover_image_url

    # 始终包含 liveRecordMp3ReceiveInfo 字段，即使为空
    if mp3_urls:
        live_record['liveRecordMp3ReceiveInfo'] = mp3_urls
    else:
        live_record['liveRecordMp3ReceiveInfo'] = []

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

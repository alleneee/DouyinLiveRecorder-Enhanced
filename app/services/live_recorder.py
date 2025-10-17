"""直播录制工具类 - 封装main.py的录制逻辑供API系统复用"""
import asyncio
import sys
import os

# 将src添加到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src import spider, stream
from src.utils import logger
from typing import Dict, Optional, Tuple
import time


class LiveRecorder:
    """直播录制器 - 封装各平台录制逻辑"""
    
    def __init__(self, proxy_addr: Optional[str] = None, cookies: Optional[Dict] = None):
        self.proxy_addr = proxy_addr
        self.cookies = cookies or {}
        
    async def get_live_stream_info(self, url: str, quality: str = "原画") -> Dict:
        """
        获取直播流信息
        
        Args:
            url: 直播间URL
            quality: 录制质量
            
        Returns:
            {
                'is_live': bool,
                'platform': str,
                'stream_url': str,
                'anchor_name': str,
                'title': str
            }
        """
        result = {
            'is_live': False,
            'platform': '未知平台',
            'stream_url': '',
            'anchor_name': '',
            'title': ''
        }
        
        try:
            # 抖音
            if "douyin.com/" in url:
                result['platform'] = '抖音'
                if 'v.douyin.com' not in url and '/user/' not in url:
                    json_data = await spider.get_douyin_stream_data(
                        url=url,
                        proxy_addr=self.proxy_addr,
                        cookies=self.cookies.get('douyin')
                    )
                else:
                    json_data = await spider.get_douyin_app_stream_data(
                        url=url,
                        proxy_addr=self.proxy_addr,
                        cookies=self.cookies.get('douyin')
                    )
                
                result['is_live'] = json_data.get('is_live', False)
                result['anchor_name'] = json_data.get('anchor_name', '')
                result['title'] = json_data.get('title', '')
                
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_douyin_stream_url(
                        json_data, quality_code, self.proxy_addr
                    )
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # TikTok
            elif "tiktok.com/" in url:
                result['platform'] = 'TikTok'
                json_data = await spider.get_tiktok_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('tiktok')
                )
                result['is_live'] = json_data.get('is_live', False)
                result['anchor_name'] = json_data.get('anchor_name', '')
                
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_tiktok_stream_url(
                        json_data, quality_code, self.proxy_addr
                    )
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 快手
            elif "kuaishou.com/" in url:
                result['platform'] = '快手'
                json_data = await spider.get_kuaishou_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('kuaishou')
                )
                result['is_live'] = json_data.get('is_live', False)
                result['anchor_name'] = json_data.get('anchor_name', '')
                
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_kuaishou_stream_url(json_data, quality_code)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # B站
            elif "bilibili.com/" in url:
                result['platform'] = 'B站'
                json_data = await spider.get_bilibili_room_info(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('bilibili')
                )
                result['is_live'] = json_data.get('is_live', False)
                result['anchor_name'] = json_data.get('anchor_name', '')
                
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_bilibili_stream_url(
                        json_data,
                        video_quality=quality_code,
                        cookies=self.cookies.get('bilibili'),
                        proxy_addr=self.proxy_addr
                    )
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 虎牙
            elif "huya.com/" in url:
                result['platform'] = '虎牙'
                quality_code = self._get_quality_code(quality)
                
                if quality_code not in ['OD', 'BD', 'UHD']:
                    json_data = await spider.get_huya_stream_data(
                        url=url,
                        proxy_addr=self.proxy_addr,
                        cookies=self.cookies.get('huya')
                    )
                    port_info = await stream.get_huya_stream_url(json_data, quality_code)
                else:
                    port_info = await spider.get_huya_app_stream_url(
                        url=url,
                        proxy_addr=self.proxy_addr,
                        cookies=self.cookies.get('huya')
                    )
                
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 斗鱼
            elif "douyu.com/" in url:
                result['platform'] = '斗鱼'
                json_data = await spider.get_douyu_info_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('douyu')
                )
                result['is_live'] = json_data.get('is_live', False)
                result['anchor_name'] = json_data.get('anchor_name', '')
                
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_douyu_stream_url(
                        json_data,
                        video_quality=quality_code,
                        cookies=self.cookies.get('douyu'),
                        proxy_addr=self.proxy_addr
                    )
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # YY
            elif "yy.com/" in url:
                result['platform'] = 'YY'
                json_data = await spider.get_yy_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('yy')
                )
                result['is_live'] = json_data.get('is_live', False)
                result['anchor_name'] = json_data.get('anchor_name', '')
                
                if result['is_live']:
                    port_info = await stream.get_yy_stream_url(json_data)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 小红书
            elif "xiaohongshu.com/" in url or "xhslink.com/" in url:
                result['platform'] = '小红书'
                port_info = await spider.get_xhs_stream_url(
                    url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('xhs')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # Bigo
            elif "bigo.tv/" in url or "slink.bigovideo.tv/" in url:
                result['platform'] = 'Bigo'
                port_info = await spider.get_bigo_stream_url(
                    url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('bigo')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # Blued
            elif "app.blued.cn/" in url:
                result['platform'] = 'Blued'
                port_info = await spider.get_blued_stream_url(
                    url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('blued')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # SOOP (原AfreecaTV)
            elif "sooplive.co.kr/" in url:
                result['platform'] = 'SOOP'
                json_data = await spider.get_sooplive_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('sooplive'),
                    username=self.cookies.get('sooplive_username'),
                    password=self.cookies.get('sooplive_password')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(json_data, quality_code, spec=True)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 网易CC
            elif "cc.163.com/" in url:
                result['platform'] = '网易CC'
                json_data = await spider.get_netease_stream_data(
                    url=url,
                    cookies=self.cookies.get('netease')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_netease_stream_url(json_data, quality_code)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 千度热播
            elif "qiandurebo.com/" in url:
                result['platform'] = '千度热播'
                port_info = await spider.get_qiandurebo_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('qiandurebo')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # PandaTV
            elif "pandalive.co.kr/" in url:
                result['platform'] = 'PandaTV'
                json_data = await spider.get_pandatv_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('pandatv')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(json_data, quality_code, spec=True)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 猫耳FM
            elif "fm.missevan.com/" in url:
                result['platform'] = '猫耳FM'
                port_info = await spider.get_maoerfm_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('maoerfm')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # WinkTV
            elif "winktv.co.kr/" in url:
                result['platform'] = 'WinkTV'
                json_data = await spider.get_winktv_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('winktv')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(json_data, quality_code, spec=True)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # FlexTV/TTingLive
            elif "flextv.co.kr/" in url or "ttinglive.com/" in url:
                result['platform'] = 'FlexTV'
                json_data = await spider.get_flextv_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('flextv')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(json_data, quality_code, spec=True)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # Look直播
            elif "look.163.com/" in url:
                result['platform'] = 'Look'
                port_info = await spider.get_looklive_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('looklive')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # PopkonTV
            elif "popkontv.com/" in url:
                result['platform'] = 'PopkonTV'
                port_info = await spider.get_popkontv_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('popkontv')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # TwitCasting
            elif "twitcasting.tv/" in url:
                result['platform'] = 'TwitCasting'
                port_info = await spider.get_twitcasting_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('twitcasting')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 百度直播
            elif "live.baidu.com/" in url:
                result['platform'] = '百度'
                json_data = await spider.get_baidu_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('baidu')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_baidu_stream_url(json_data, quality_code)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 微博直播
            elif "weibo.com/" in url:
                result['platform'] = '微博'
                json_data = await spider.get_weibo_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('weibo')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    port_info = await stream.get_weibo_stream_url(json_data)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 酷狗直播
            elif "kugou.com/" in url:
                result['platform'] = '酷狗'
                port_info = await spider.get_kugou_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('kugou')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # TwitchTV
            elif "twitch.tv/" in url:
                result['platform'] = 'TwitchTV'
                json_data = await spider.get_twitchtv_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('twitch')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(json_data, quality_code, spec=True)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # LiveMe
            elif "liveme.com/" in url:
                result['platform'] = 'LiveMe'
                port_info = await spider.get_liveme_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('liveme')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 花椒直播
            elif "huajiao.com/" in url:
                result['platform'] = '花椒'
                port_info = await spider.get_huajiao_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('huajiao')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 流星直播
            elif "7u66.com/" in url:
                result['platform'] = '流星'
                port_info = await spider.get_liuxing_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('liuxing')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # ShowRoom
            elif "showroom-live.com/" in url:
                result['platform'] = 'ShowRoom'
                json_data = await spider.get_showroom_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('showroom')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(json_data, quality_code, spec=True)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # Acfun
            elif "acfun.cn/" in url:
                result['platform'] = 'Acfun'
                json_data = await spider.get_acfun_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('acfun')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(
                        json_data, quality_code, url_type='flv', flv_extra_key='url'
                    )
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 畅聊直播
            elif "tlclw.com/" in url:
                result['platform'] = '畅聊'
                port_info = await spider.get_changliao_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('changliao')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 音播直播
            elif "ybw1666.com/" in url:
                result['platform'] = '音播'
                port_info = await spider.get_yinbo_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('yinbo')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 映客直播
            elif "inke.cn/" in url:
                result['platform'] = '映客'
                port_info = await spider.get_yingke_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('yingke')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 知乎直播
            elif "zhihu.com/" in url:
                result['platform'] = '知乎'
                port_info = await spider.get_zhihu_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('zhihu')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # CHZZK
            elif "chzzk.naver.com/" in url:
                result['platform'] = 'CHZZK'
                json_data = await spider.get_chzzk_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('chzzk')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(json_data, quality_code, spec=True)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 嗨秀直播
            elif "haixiutv.com/" in url:
                result['platform'] = '嗨秀'
                port_info = await spider.get_haixiu_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('haixiu')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # VV星球
            elif "vvxqiu.com/" in url:
                result['platform'] = 'VV星球'
                port_info = await spider.get_vvxqiu_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('vvxqiu')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 17Live
            elif "17.live/" in url:
                result['platform'] = '17Live'
                port_info = await spider.get_17live_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('17live')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 浪Live
            elif "lang.live/" in url:
                result['platform'] = '浪Live'
                port_info = await spider.get_langlive_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('langlive')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 飘飘直播
            elif "pp.weimipopo.com/" in url:
                result['platform'] = '飘飘'
                port_info = await spider.get_pplive_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('pplive')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 六间房
            elif ".6.cn/" in url:
                result['platform'] = '六间房'
                port_info = await spider.get_6room_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('6room')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 乐嗨直播
            elif "lehaitv.com/" in url:
                result['platform'] = '乐嗨'
                port_info = await spider.get_haixiu_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('lehaitv')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 花猫直播
            elif "catshow168.com/" in url:
                result['platform'] = '花猫'
                port_info = await spider.get_pplive_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('huamao')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # Shopee
            elif "shopee" in url or "shp.ee/" in url:
                result['platform'] = 'Shopee'
                port_info = await spider.get_shopee_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('shopee')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # Youtube
            elif "youtube.com/" in url or "youtu.be/" in url:
                result['platform'] = 'Youtube'
                json_data = await spider.get_youtube_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('youtube')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(json_data, quality_code, spec=True)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 淘宝直播
            elif "tb.cn" in url or "taobao.com" in url:
                result['platform'] = '淘宝'
                json_data = await spider.get_taobao_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('taobao')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(
                        json_data, quality_code,
                        url_type='all', hls_extra_key='hlsUrl', flv_extra_key='flvUrl'
                    )
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 京东直播
            elif "3.cn" in url or "jd.com" in url:
                result['platform'] = '京东'
                port_info = await spider.get_jd_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('jd')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # Faceit
            elif "faceit.com/" in url:
                result['platform'] = 'Faceit'
                json_data = await spider.get_faceit_stream_data(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('faceit')
                )
                result['is_live'] = json_data.get('is_live', False)
                if result['is_live']:
                    quality_code = self._get_quality_code(quality)
                    port_info = await stream.get_stream_url(json_data, quality_code, spec=True)
                    result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 咪咕直播
            elif "miguvideo.com" in url:
                result['platform'] = '咪咕'
                port_info = await spider.get_migu_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('migu')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 连接直播
            elif "lailianjie.com" in url:
                result['platform'] = '连接'
                port_info = await spider.get_lianjie_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('lianjie')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 来秀直播
            elif "imkktv.com" in url:
                result['platform'] = '来秀'
                port_info = await spider.get_laixiu_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('laixiu')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # Picarto
            elif "picarto.tv" in url:
                result['platform'] = 'Picarto'
                port_info = await spider.get_picarto_stream_url(
                    url=url,
                    proxy_addr=self.proxy_addr,
                    cookies=self.cookies.get('picarto')
                )
                result['is_live'] = port_info.get('is_live', False)
                result['stream_url'] = port_info.get('flv_url') or port_info.get('m3u8_url', '')
            
            # 自定义流媒体地址（.m3u8 或 .flv）
            elif ".m3u8" in url or ".flv" in url:
                result['platform'] = '自定义'
                result['is_live'] = True
                result['stream_url'] = url
            
        except Exception as e:
            logger.error(f"获取直播流信息失败: {url}, error={e}")
        
        return result
    
    def _get_quality_code(self, quality_zh: str) -> str:
        """将中文画质转换为代码"""
        quality_map = {
            '原画': 'OD',
            '蓝光': 'BD',
            '超清': 'UHD',
            '高清': 'HD',
            '标清': 'SD',
            '流畅': 'LD'
        }
        return quality_map.get(quality_zh, 'OD')
    
    async def check_live_status(self, url: str) -> bool:
        """
        快速检查直播状态（不获取流地址）
        
        Args:
            url: 直播间URL
            
        Returns:
            是否正在直播
        """
        info = await self.get_live_stream_info(url)
        return info['is_live']

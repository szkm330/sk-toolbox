#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Replive 直播录制
"""

import requests
import subprocess
import time
import json
from datetime import datetime
import sys 

# ==================== CONFIG ====================
REFRESH_TOKEN = ""
FFMPEG_PATH = "ffmpeg.exe" 
# ==============================================

API_BASE = "https://api.replive.com/"
access_token = None
token_expire_time = 0


def get_access_token():
    """获取或刷新 access token"""
    global access_token, token_expire_time
    
    # 如果 token 还没过期（提前3分钟刷新）
    if access_token and token_expire_time > time.time() + 180:
        return access_token
    
    print("刷新 access token...")
    url = API_BASE + "user.v1.UserService/RefreshAccessToken"
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Replive/3.1.1",
        "accept": "application/json"
    }
    
    data = json.dumps({"refreshToken": REFRESH_TOKEN})
    
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            result = resp.json()
            
            # 提取 access token
            access_token = (result.get("accessToken") or 
                           result.get("access_token") or
                           result.get("AccessToken"))
            
            # 提取过期时间
            expire_info = (result.get("accessTokenExpireTime") or 
                          result.get("access_token_expire_time") or
                          result.get("AccessTokenExpireTime"))
            
            # 解析过期时间
            if isinstance(expire_info, str):
                # ISO 8601 格式: "2025-11-06T14:14:58.708342065Z"
                try:
                    from dateutil import parser as date_parser
                    expire_dt = date_parser.parse(expire_info)
                    token_expire_time = int(expire_dt.timestamp())
                except ImportError:
                    # 如果没有 dateutil，手动解析
                    expire_str = expire_info.replace('Z', '+00:00').split('.')[0]
                    expire_dt = datetime.fromisoformat(expire_str)
                    token_expire_time = int(expire_dt.timestamp())
            elif isinstance(expire_info, dict):
                # Protobuf 格式: {"seconds": 123456}
                token_expire_time = int(expire_info.get("seconds", 0))
            elif isinstance(expire_info, (int, float)):
                # 直接是时间戳
                token_expire_time = int(expire_info)
            else:
                # 默认1小时后过期
                token_expire_time = int(time.time()) + 3600
            
            if access_token:
                print(f"Token 刷新成功")
                print(f"过期时间: {datetime.fromtimestamp(token_expire_time).strftime('%Y-%m-%d %H:%M:%S')}")
                return access_token
            else:
                print(f"ERROR: 响应中没有找到 access token")
                return None
        else:
            print(f"ERROR: 请求失败: {resp.status_code} - {resp.text[:200]}")
            return None
        
    except Exception as e:
        print(f"ERROR: 获取 token 失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_live():
    """检查是否有直播"""
    token = get_access_token()
    if not token:
        return []
    
    url = API_BASE + "user.v1.LiveService/CheckStreamingLive"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Replive/3.1.1",
        "accept": "application/json"
    }
    
    # 空的请求体
    data = json.dumps({})
    
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        resp.raise_for_status()
        
        result = resp.json()
        
        # 正确的字段名
        lives = result.get("followingLives", [])
        users_dict = result.get("users", {})
        
        live_list = []
        for live in lives:
            user_id = live.get("userId")
            user_info = users_dict.get(user_id, {})
            
            name = user_info.get("displayName", "Unknown")
            title = live.get("title", "无标题")
            live_id = live.get("liveId")
            playback_url = live.get("playbackUrl", "")
            
            rtmp_url = convert_to_rtmp(playback_url)
            
            live_list.append({
                "live_id": live_id,
                "title": title,
                "name": name,
                "rtmp_url": rtmp_url
            })
        
        return live_list
        
    except Exception as e:
        print(f"ERROR: 检查直播失败: {e}")
        return []


def convert_to_rtmp(playback_url):
    """将 playback URL 转换为 RTMP URL"""
    if not playback_url:
        return ""
    
    try:
        # playback_url 格式: webrtc://lvplay.replive.com/replive/xxx?txSecret=...&txTime=...
        # 转换为 RTMP: rtmp://lvplay.replive.com/replive/xxx?txSecret=...&txTime=...
        rtmp_url = playback_url.replace("webrtc://", "rtmp://")
        return rtmp_url
    except:
        return playback_url


def start_recording(live_info):
    """开始录制直播"""
    name = live_info["name"]
    rtmp_url = live_info["rtmp_url"]
    title = live_info["title"]
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{name}_{timestamp}.mp4"
    log_file = f"{name}_{timestamp}.log"
    
    # 在新开播时，先清除当前行再输出新开播信息
    sys.stdout.write("\r" + " " * 120 + "\r") # 清除当前行
    sys.stdout.flush()

    print(f"\n{'='*50}")
    print(f"{name} 开始直播")
    print(f"标题: {title}")
    print(f"录制到: {output_file}")
    print(f"{'='*50}\n")
    
    # FFmpeg 命令
    cmd = [
        FFMPEG_PATH,
        "-i", rtmp_url,
        "-c", "copy",
        output_file
    ]
    
    try:
        # 打开日志文件
        with open(log_file, "w", encoding="utf-8") as log:
            log.write(f"开始时间: {datetime.now()}\n")
            log.write(f"主播: {name}\n")
            log.write(f"标题: {title}\n")
            log.write(f"URL: {rtmp_url}\n\n")
            
            # 启动 FFmpeg（后台运行）
            process = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=log,
                stdin=subprocess.DEVNULL
            )
            
            print(f"录制开始，进程 ID: {process.pid}")
            return process
            
    except Exception as e:
        print(f"Error: 启动录制失败: {e}")
        return None


def main():
    """主程序"""
    
    print("="*60)
    print("  Replive 直播录制")
    print("="*60)
    print()
    
    # 检查配置
    if REFRESH_TOKEN == "refresh_token":
        print("ERROR: 请在代码中填入 refresh_token")
        return
    
    # 测试 token
    if not get_access_token():
        print("ERROR: Token 验证失败，请检查 refresh_token 是否正确")
        return
    
    print("\n初始化成功，开始监控直播...")
    print("=" * 60)
    print()
    
    # 记录已经在录制的直播
    recording_lives = {}
    recording_start_times = {}  # 记录开始时间
    check_count = 0
    
    try:
        while True:
            check_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            
            # 检查直播
            lives = check_live()
            
            # 构建状态行
            status_parts = [
                f"[{current_time}] 监控中...",
                f"检查: {check_count}"
            ]
            
            if recording_lives:
                time_info = []
                for live_id, start_time in recording_start_times.items():
                    duration = int(time.time() - start_time)
                    hours = duration // 3600
                    minutes = (duration % 3600) // 60
                    seconds = duration % 60
                    time_info.append(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                status_parts.append(f"录制中: {len(recording_lives)} 个 | 时长: {', '.join(time_info)}")
            else:
                status_parts.append("录制中: 0 个")
            
            status_line = " | ".join(status_parts)
            
            # 清除当前行并输出新的状态
            sys.stdout.write("\r" + " " * 120 + "\r") # 清除当前行，假设最长120字符
            sys.stdout.write(status_line)
            sys.stdout.flush()
            
            for live in lives:
                live_id = live["live_id"]
                
                # 如果这个直播还没开始录制
                if live_id not in recording_lives:
                    # 在开始录制前，先将状态行换行，避免覆盖
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    process = start_recording(live)
                    if process:
                        recording_lives[live_id] = process
                        recording_start_times[live_id] = time.time()
            
            # 每 5 秒检查一次
            time.sleep(5)
            
    except KeyboardInterrupt:
        sys.stdout.write("\n") # 确保中断时换行
        sys.stdout.flush()
        print("\n\n" + "="*60)
        print("  程序已停止")
        print("="*60)
        if recording_lives:
            print(f"\n共录制了 {len(recording_lives)} 个直播")
            for live_id, start_time in recording_start_times.items():
                duration = int(time.time() - start_time)
                minutes = duration // 60
                print(f"  - 录制时长: {minutes} 分钟")
        print()


if __name__ == "__main__":
    main()
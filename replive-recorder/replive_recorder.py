#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import subprocess
import sys
import time
import random
import requests
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# ==================== CONFIG ====================
REFRESH_TOKEN = ""
FFMPEG_PATH = "ffmpeg.exe"
CHECK_INTERVAL = 20  # 检查间隔（秒）
# ==============================================

API_BASE = "https://api.replive.com/"


@dataclass
class LiveInfo:
    """直播信息"""
    live_id: str
    title: str
    name: str
    rtmp_url: str


@dataclass
class RecordingSession:
    """录制会话"""
    process: subprocess.Popen
    start_time: float
    output_file: str
    streamer_name: str
    title: str
    
    @property
    def duration(self) -> int:
        """录制时长（秒）"""
        return int(time.time() - self.start_time)
    
    @property
    def duration_str(self) -> str:
        """格式化时长"""
        h, m, s = self.duration // 3600, (self.duration % 3600) // 60, self.duration % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    
    def is_alive(self) -> bool:
        """检查进程是否存活"""
        return self.process.poll() is None


class TokenManager:
    """Token 管理器"""
    
    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token
        self.access_token: Optional[str] = None
        self.expire_time: float = 0
    
    def get_token(self) -> Optional[str]:
        """获取有效的 access token"""
        if self.access_token and self.expire_time > time.time() + 180:
            return self.access_token
        return self._refresh_token()
    
    def _refresh_token(self) -> Optional[str]:
        """刷新 access token"""
        url = f"{API_BASE}user.v1.UserService/RefreshAccessToken"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Replive/3.1.1",
            "accept": "application/json"
        }
        
        try:
            resp = requests.post(url, json={"refreshToken": self.refresh_token}, 
                               headers=headers, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            self.access_token = (result.get("accessToken") or 
                                result.get("access_token") or 
                                result.get("AccessToken"))
            
            expire_info = (result.get("accessTokenExpireTime") or 
                          result.get("access_token_expire_time") or 
                          result.get("AccessTokenExpireTime"))
            
            self.expire_time = self._parse_expire_time(expire_info)
            
            return self.access_token
            
        except Exception as e:
            return None
    
    @staticmethod
    def _parse_expire_time(expire_info) -> float:
        """解析过期时间"""
        if isinstance(expire_info, str):
            try:
                from dateutil import parser as date_parser
                return date_parser.parse(expire_info).timestamp()
            except ImportError:
                expire_str = expire_info.replace('Z', '+00:00').split('.')[0]
                return datetime.fromisoformat(expire_str).timestamp()
        elif isinstance(expire_info, dict):
            return float(expire_info.get("seconds", 0))
        elif isinstance(expire_info, (int, float)):
            return float(expire_info)
        return time.time() + 3600


class RepliveRecorder:
    """Replive 录制器"""
    
    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager
        self.recordings: Dict[str, RecordingSession] = {}
        self.console = Console()
    
    def check_live(self) -> List[LiveInfo]:
        """检查当前直播"""
        token = self.token_manager.get_token()
        if not token:
            return []
        
        url = f"{API_BASE}user.v1.LiveService/CheckStreamingLive"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Replive/3.1.1",
            "accept": "application/json"
        }
        
        try:
            resp = requests.post(url, json={}, headers=headers, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            
            lives = result.get("followingLives", [])
            users = result.get("users", {})
            
            return [
                LiveInfo(
                    live_id=live["liveId"],
                    title=live.get("title", "无标题"),
                    name=users.get(live["userId"], {}).get("displayName", "Unknown"),
                    rtmp_url=self._convert_to_rtmp(live.get("playbackUrl", ""))
                )
                for live in lives
            ]
        except Exception as e:
            return []
    
    @staticmethod
    def _convert_to_rtmp(playback_url: str) -> str:
        """转换为 RTMP URL"""
        return playback_url.replace("webrtc://", "rtmp://") if playback_url else ""
    
    def start_recording(self, live: LiveInfo) -> bool:
        """开始录制"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{live.name}_{timestamp}.mp4"
        log_file = f"{live.name}_{timestamp}.log"
        
        cmd = [FFMPEG_PATH, "-i", live.rtmp_url, "-c", "copy", output_file]
        
        try:
            with open(log_file, "w", encoding="utf-8") as log:
                log.write(f"开始时间: {datetime.now()}\n")
                log.write(f"主播: {live.name}\n标题: {live.title}\nURL: {live.rtmp_url}\n\n")
                
                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=log,
                    stdin=subprocess.DEVNULL
                )
                
                self.recordings[live.live_id] = RecordingSession(
                    process=process,
                    start_time=time.time(),
                    output_file=output_file,
                    streamer_name=live.name,
                    title=live.title
                )
                
                return True
        except Exception as e:
            return False
    
    def cleanup_ended_recordings(self, current_lives: List[LiveInfo]) -> List[RecordingSession]:
        """清理已结束的录制，返回结束的会话列表"""
        current_live_ids = {live.live_id for live in current_lives}
        ended_sessions = []
        ended_ids = []
        
        for live_id, session in self.recordings.items():
            # 检查直播是否结束或进程是否已终止
            if live_id not in current_live_ids or not session.is_alive():
                ended_ids.append(live_id)
                ended_sessions.append(session)
                if session.is_alive():
                    session.process.terminate()
        
        for live_id in ended_ids:
            del self.recordings[live_id]
        
        return ended_sessions
    
    def generate_display(self, new_recordings: List[str] = None, ended_sessions: List[RecordingSession] = None) -> Table:
        """生成显示内容"""
        # 标题面板
        current_time = datetime.now().strftime("%H:%M:%S")
        status = Text()
        status.append("监控状态: ", style="bold")
        status.append("运行中", style="bold")
        status.append(f" | 时间: {current_time}")
        
        title_panel = Panel(
            status,
            title="[bold]Replive 直播录制[/bold]",
            border_style="bright_black"
        )
        
        # 创建主表格
        main_table = Table(show_header=False, box=None, padding=(0, 0))
        main_table.add_row(title_panel)
        
        # 新开播通知
        if new_recordings:
            notification = Table(show_header=False, box=None, padding=(0, 1))
            for name in new_recordings:
                notification.add_row(f"[bold]{name} 开始直播[/bold]")
            main_table.add_row("")
            main_table.add_row(notification)
        
        # 录制结束通知
        if ended_sessions:
            notification = Table(show_header=False, box=None, padding=(0, 1))
            for session in ended_sessions:
                notification.add_row(
                    f"[bold]{session.streamer_name} 录制结束[/bold] "
                    f"[dim]({session.duration_str})[/dim]"
                )
            main_table.add_row("")
            main_table.add_row(notification)
        
        # 录制列表
        if self.recordings:
            main_table.add_row("")
            main_table.add_row("[bold]正在录制的直播:[/bold]")
            
            recording_table = Table(
                show_header=True,
                header_style="bold",
                border_style="bright_black",
                padding=(0, 1)
            )
            
            recording_table.add_column("主播", no_wrap=True)
            recording_table.add_column("标题")
            recording_table.add_column("时长", justify="right")
            recording_table.add_column("状态", justify="center")
            
            for session in self.recordings.values():
                recording_table.add_row(
                    session.streamer_name,
                    session.title[:30] + "..." if len(session.title) > 30 else session.title,
                    session.duration_str,
                    "录制中"
                )
            
            main_table.add_row(recording_table)
        else:
            main_table.add_row("")
            main_table.add_row("[dim]当前没有正在录制的直播[/dim]")
        
        return main_table
    
    def run(self):
        """主循环"""
        # 初始化显示
        self.console.print("Token 验证成功")
        self.console.print("初始化完成，开始监控直播\n")
        
        time.sleep(1)
        
        try:
            with Live(self.generate_display(), console=self.console, refresh_per_second=1) as live:
                while True:
                    lives = self.check_live()
                    
                    # 清理已结束的录制
                    ended_sessions = self.cleanup_ended_recordings(lives)
                    
                    # 开始新的录制
                    new_recordings = []
                    for live_info in lives:
                        if live_info.live_id not in self.recordings:
                            if self.start_recording(live_info):
                                new_recordings.append(live_info.name)
                    
                    # 更新显示（显示通知3秒）
                    if new_recordings or ended_sessions:
                        live.update(self.generate_display(new_recordings, ended_sessions))
                        time.sleep(3)
                    
                    # 正常更新
                    live.update(self.generate_display())
                    random_delay = random.uniform(0.5, 5.0)
                    time.sleep(CHECK_INTERVAL + random_delay)
                    
        except KeyboardInterrupt:
            self.console.print("\n\n[bold]程序已停止[/bold]")
            
            if self.recordings:
                self.console.print(f"\n[bold]录制统计:[/bold]")
                summary_table = Table(show_header=True, border_style="bright_black")
                summary_table.add_column("主播")
                summary_table.add_column("文件")
                summary_table.add_column("时长", justify="right")
                
                for session in self.recordings.values():
                    summary_table.add_row(
                        session.streamer_name,
                        session.output_file,
                        session.duration_str
                    )
                
                self.console.print(summary_table)
            
            self.console.print()


def main():
    """主函数"""
    console = Console()
    
    if not REFRESH_TOKEN:
        console.print("[bold red]ERROR:[/bold red] 请在代码中填入 REFRESH_TOKEN")
        return
    
    token_manager = TokenManager(REFRESH_TOKEN)
    
    # 验证 token
    console.print("\n[bold]正在验证 Token[/bold]")
    if not token_manager.get_token():
        console.print("[bold red]ERROR:[/bold red] Token 验证失败，请检查 REFRESH_TOKEN 是否正确")
        return
    
    recorder = RepliveRecorder(token_manager)
    recorder.run()


if __name__ == "__main__":
    main()

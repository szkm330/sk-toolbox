#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Niconico弹幕XML转ASS工具 - Python版本
"""

import xml.etree.ElementTree as ET
import json
import re
from dataclasses import dataclass
from typing import List, Optional, Dict
import argparse


@dataclass
class Config:
    """配置选项"""
    limit_line_amount: int = 11  # 弹幕行数限制
    ass_code: str = r"\fnMS PGothic\b1\bord2\blur0"  # ASS代码前缀
    danmaku_size: int = 46  # 弹幕大小
    danmaku_density: int = 10  # 弹幕密度
    start_time_adjust: float = 0.0  # 时间轴偏移（秒）
    danmaku_speed_adjust: float = 1.0  # 滚动速度调整（秒）
    use_ass_colors: bool = True  # 是否使用弹幕颜色
    difficult_vip: bool = False  # 是否区分会员
    filter_outsider: bool = False  # 是否过滤非会员
    use_speed_a: bool = False  # 是否使用速度算法
    manual_add_office_id: List[str] = None  # 手动添加运营弹幕ID
    filter_keywords: List[str] = None  # 屏蔽关键词

    def __post_init__(self):
        if self.manual_add_office_id is None:
            self.manual_add_office_id = []
        if self.filter_keywords is None:
            self.filter_keywords = []


class NicoXML2ASS:
    """Niconico XML转ASS转换器"""
    
    # 视频尺寸
    VIDEO_WIDTH = 1280
    VIDEO_HEIGHT = 720
    
    # CSS颜色到ASS颜色映射
    CSS2ASS = {
        "white": "#FFFFFF", "red": "#FF0000", "pink": "#FF8080",
        "orange": "#FFA500", "yellow": "#FFFF00", "green": "#00FF00",
        "cyan": "#00FFFF", "blue": "#0000FF", "purple": "#C000FF",
        "black": "#000000", "white2": "#CCCC99", "niconicowhite": "#CCCC99",
        "red2": "#CC0033", "truered": "#CC0033", "pink2": "#FF33CC",
        "orange2": "#FF6600", "passionorange": "#FF6600", "yellow2": "#999900",
        "madyellow": "#999900", "green2": "#00CC66", "elementalgreen": "#00CC66",
        "cyan2": "#00CCCC", "blue2": "#3399FF", "marineblue": "#3399FF",
        "purple2": "#6633CC", "nobleviolet": "#6633CC", "black2": "#666666",
    }
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.title = "无标题"
        self.office_ids = []
        self.all_danmaku = []
        self.aa_start_times = []
        
    def load_xml(self, xml_path: str):
        """加载XML文件"""
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # 获取标题（如果有）
        thread = root.find('thread')
        if thread is not None:
            self.title = thread.get('title', xml_path.split('/')[-1].replace('.xml', ''))
        
        # 获取所有chat元素
        chats = root.findall('.//chat')
        
        # 转换为字典列表
        self.all_danmaku = []
        for chat in chats:
            danmaku = {
                'text': chat.text or '',
                'vpos': int(chat.get('vpos', 0)),
                'user_id': chat.get('user_id', ''),
                'premium': chat.get('premium', '0'),
                'mail': chat.get('mail', ''),
                'date': int(chat.get('date', 0)),
                'date_usec': int(chat.get('date_usec', 0)),
            }
            self.all_danmaku.append(danmaku)
        
        # 排序
        self.all_danmaku.sort(key=lambda x: x['vpos'])
        
        # 检查运营ID
        self._check_office_ids()
        
    def _check_office_ids(self):
        """自动检测运营弹幕ID"""
        office_id_set = set()
        
        for danmaku in self.all_danmaku:
            if danmaku['premium'] == '2':
                text = danmaku['text']
                # 排除特殊类型的运营消息
                if not any(x in text for x in ['/trialpanel', '/nicoad', '/spi', '/gift', '/info', '/commentlock']):
                    office_id_set.add(danmaku['user_id'])
        
        self.office_ids = list(office_id_set)
        # 添加手动指定的ID
        self.office_ids.extend(self.config.manual_add_office_id)
        
    def convert_to_ass(self) -> str:
        """转换为ASS格式"""
        # 生成ASS头部
        ass_header = self._generate_ass_header()
        
        # 处理弹幕
        office_lines = []  # 运营弹幕
        shita_lines = []   # 底部弹幕
        aa_lines = []      # AA弹幕
        normal_lines = []  # 普通弹幕
        
        # 弹幕通道管理（用于碰撞检测）
        danmaku_passageway = [0.0] * self.config.limit_line_amount
        danmaku_passageway_width = [0] * self.config.limit_line_amount
        danmaku_passageway_speed = [0.0] * self.config.limit_line_amount
        danmaku_passageway_finish = [0.0] * self.config.limit_line_amount
        
        for danmaku in self.all_danmaku:
            # 跳过无效弹幕
            if not danmaku['text'] or danmaku['text'] == '※ NGコメントです ※':
                continue
            
            if danmaku['vpos'] < 0:
                continue
            
            # 屏蔽关键词
            if any(kw in danmaku['text'] for kw in self.config.filter_keywords if kw):
                continue
            
            # 调整运营弹幕时间
            if danmaku['date'] == 0 and danmaku['date_usec'] == 0 and danmaku['premium'] == '2':
                danmaku['vpos'] = danmaku['vpos'] * 100
            
            # 处理运营弹幕
            if danmaku['user_id'] in self.office_ids:
                office_line = self._process_office_danmaku(danmaku)
                if office_line:
                    office_lines.append(office_line)
                continue
            
            # 处理AA弹幕（长文本）
            if len(danmaku['text']) >= 70:
                aa_line = self._process_aa_danmaku(danmaku)
                if aa_line:
                    aa_lines.append(aa_line)
                continue
            
            # 处理底部弹幕
            if 'shita' in danmaku['mail'] or danmaku.get('type') == 'official':
                shita_line = self._process_shita_danmaku(danmaku)
                if shita_line:
                    shita_lines.append(shita_line)
                continue
            
            # 过滤非会员
            if self.config.filter_outsider and danmaku['premium'] == '25':
                continue
            
            # 处理普通弹幕
            if danmaku['text'].startswith('/'):
                continue
            
            normal_line = self._process_normal_danmaku(
                danmaku, 
                danmaku_passageway,
                danmaku_passageway_width,
                danmaku_passageway_speed,
                danmaku_passageway_finish
            )
            if normal_line:
                normal_lines.append(normal_line)
        
        # 组合所有弹幕
        result = ass_header + "\n"
        
        if office_lines:
            result += "Comment: 0,0:00:00.00,0:00:00.00,Office,,0,0,0,,运营弹幕\n"
            result += "".join(office_lines)
            result += "Comment: 0,0:00:00.00,0:00:00.00,Office,,0,0,0,,\n"
        
        if shita_lines:
            result += "Comment: 0,0:00:00.00,0:00:00.00,Shita,,0,0,0,,底部弹幕\n"
            result += "".join(shita_lines)
            result += "Comment: 0,0:00:00.00,0:00:00.00,Shita,,0,0,0,,\n"
        
        if aa_lines:
            result += "Comment: 0,0:00:00.00,0:00:00.00,AA,,0,0,0,,AA弹幕\n"
            result += "".join(aa_lines)
            result += "Comment: 0,0:00:00.00,0:00:00.00,AA,,0,0,0,,\n"
        
        result += "".join(normal_lines)
        
        return result
    
    def _generate_ass_header(self) -> str:
        """生成ASS文件头部"""
        aa_size = 20
        office_size = 20
        danmaku_size = self.config.danmaku_size
        
        header = f"""[Script Info]
; Script generated by NicoXML2ASS Python
ScriptType: v4.00+
PlayResX: {self.VIDEO_WIDTH}
PlayResY: {self.VIDEO_HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,微软雅黑,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,30,30,120,0
Style: Alternate,微软雅黑,36,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,30,30,84,0
Style: AA,Yu Gothic,{aa_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,2,2,30,30,84,0
Style: Office,MS PGothic,{office_size},&H00FFFFFF,&H00FFFFFF,&H14000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,30,30,30,0
Style: Shita,MS PGothic,{danmaku_size},&H00FFFFFF,&H00FFFFFF,&H14000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,30,30,0,0
Style: Danmaku,MS PGothic,{danmaku_size},&H00FFFFFF,&H00FFFFFF,&H14000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,30,30,30,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""
        
        return header
    
    def _process_office_danmaku(self, danmaku: dict) -> Optional[str]:
        """处理运营弹幕"""
        text = danmaku['text']
        
        # 跳过特殊命令
        if any(x in text for x in ['/vote', '/nicoad', '/gift', '/spi', '/info', '/clear']):
            return None
        
        # 处理链接
        if text.startswith('/'):
            space_idx = text.find(' ')
            if space_idx > 0:
                text = text[space_idx + 1:]
        
        if text.startswith('<'):
            # 简单处理HTML标签
            text = re.sub(r'<[^>]+>', '', text)
        
        # 转换换行和链接
        text = text.replace('\n', r'\N').replace('http', r'\N{\u1\1c&HFFCF00&}http')
        
        start_time = self._format_time(danmaku['vpos'] / 100)
        end_time = self._format_time(danmaku['vpos'] / 100 + 10)
        
        office_bg_height = 32
        lines = text.split(r'\N')
        office_bg_height = office_bg_height + office_bg_height * (len(lines) - 1)
        
        office_bg = f"m 0 0 l {self.VIDEO_WIDTH + 20} 0 l {self.VIDEO_WIDTH + 20} {office_bg_height} l 0 {office_bg_height}"
        
        bg_line = f"Dialogue: 5,{start_time},{end_time},Office,,0,0,0,,{{\\an5\\p1\\pos({self.VIDEO_WIDTH//2},{office_bg_height//2})\\bord0\\1c&H000000&\\1a&H78&}}{office_bg}\n"
        text_line = f"Dialogue: 5,{start_time},{end_time},Office,,0,0,0,,{{\\an5\\fscx90\\fscy90\\pos({self.VIDEO_WIDTH//2},{office_bg_height//2})\\bord0\\1c&HFFFFFF&}}{text}\n"
        
        return bg_line + text_line
    
    def _process_aa_danmaku(self, danmaku: dict) -> Optional[str]:
        """处理AA弹幕（ASCII艺术）"""
        if danmaku['text'].startswith('/'):
            return None
        
        start_time = self._format_time(danmaku['vpos'] / 100)
        end_time = self._format_time(danmaku['vpos'] / 100 + 8)
        
        color_ass = self._get_color_ass(danmaku['mail'])
        
        aa_lines = danmaku['text'].split('\n')
        aa_size = 20
        aa_high_adjust = 80
        
        result = ""
        
        # 检查是否是固定位置
        is_fixed = any(x in danmaku['mail'] for x in ['shita', 'ue', 'naka'])
        
        for i, line in enumerate(aa_lines):
            y_pos = (aa_size - 6) * i + aa_high_adjust
            
            if is_fixed:
                # 固定在中间
                dialogue = f"Dialogue: 4,{start_time},{end_time},AA,,0,0,0,,{{\\an4\\fsp-1\\pos({self.VIDEO_WIDTH//2 - 250}, {y_pos})\\1c&{color_ass}&}}{line}\n"
            else:
                # 滚动
                dialogue = f"Dialogue: 4,{start_time},{end_time},AA,,0,0,0,,{{\\an4\\fsp-1\\move({self.VIDEO_WIDTH}, {y_pos}, {-64*10}, {y_pos})\\1c&{color_ass}&}}{line}\n"
            
            result += dialogue
        
        # 记录AA时间
        aa_time = self._format_time_mm_ss(danmaku['vpos'] / 100)
        if aa_time not in self.aa_start_times:
            self.aa_start_times.append(aa_time)
        
        return result
    
    def _process_shita_danmaku(self, danmaku: dict) -> Optional[str]:
        """处理底部弹幕"""
        start_time = self._format_time(danmaku['vpos'] / 100)
        end_time = self._format_time(danmaku['vpos'] / 100 + 6)
        
        color_ass = self._get_color_ass(danmaku['mail'])
        
        return f"Dialogue: 2,{start_time},{end_time},Shita,,0,0,0,,{{\\an2\\1c&{color_ass}&}}{danmaku['text']}\n"
    
    def _process_normal_danmaku(self, danmaku: dict, passageway: list, 
                                passageway_width: list, passageway_speed: list,
                                passageway_finish: list) -> Optional[str]:
        """处理普通滚动弹幕"""
        # 计算时间
        start_seconds = danmaku['vpos'] / 100 + self.config.start_time_adjust
        start_time = self._format_time(start_seconds)
        end_seconds = danmaku['vpos'] / 100 + 16 + self.config.start_time_adjust
        end_time = self._format_time(end_seconds)
        
        # 计算文本宽度
        text_length = self._calc_text_length(danmaku['text'])
        text_width = text_length * (self.config.danmaku_size + 2)
        
        # 计算速度
        real_speed = 6000 + 1000 * self.config.danmaku_speed_adjust
        
        if self.config.use_speed_a:
            # 速度算法
            short_length = 4
            long_length = 12
            
            if text_length <= short_length:
                real_speed = (6000 - short_length * (self.config.danmaku_size + 2)) + \
                            int(short_length * (self.config.danmaku_size + 2) * (text_length / short_length)) + \
                            1000 * self.config.danmaku_speed_adjust
            elif text_length >= long_length:
                real_speed = 6000 + int(2 * (self.config.danmaku_size + 2) * (text_length - long_length)) + \
                            1000 * self.config.danmaku_speed_adjust
        
        average_speed = (self.VIDEO_WIDTH + text_width) / (real_speed / 1000)
        
        # 查找可用通道
        passageway_index = -1
        
        for i in range(len(passageway)):
            if passageway[i] == 0:
                passageway[i] = start_seconds
                passageway_width[i] = text_width
                passageway_speed[i] = average_speed
                passageway_finish[i] = self.VIDEO_WIDTH / average_speed
                passageway_index = i
                break
            
            # 检查碰撞
            range_dist = (start_seconds - passageway[i]) * passageway_speed[i] + self.config.danmaku_density
            
            if range_dist >= passageway_width[i]:
                if passageway_width[i] >= text_width:
                    passageway[i] = start_seconds
                    passageway_width[i] = text_width
                    passageway_speed[i] = average_speed
                    passageway_finish[i] = self.VIDEO_WIDTH / average_speed
                    passageway_index = i
                    break
                else:
                    catch_time = (range_dist - passageway_width[i]) / (average_speed - passageway_speed[i])
                    if catch_time > 0 and (passageway_finish[i] - (start_seconds - passageway[i])) < catch_time:
                        passageway[i] = start_seconds
                        passageway_width[i] = text_width
                        passageway_speed[i] = average_speed
                        passageway_finish[i] = self.VIDEO_WIDTH / average_speed
                        passageway_index = i
                        break
        
        # 没有可用通道，跳过此弹幕
        if passageway_index == -1:
            return None
        
        # 计算位置
        danmaku_line_height = 64
        sy = danmaku_line_height // 2 + danmaku_line_height * passageway_index
        ey = sy
        sx = self.VIDEO_WIDTH
        ex = -text_width
        
        # 获取颜色
        color_ass = "HFFFFFF"
        if self.config.use_ass_colors and danmaku['mail']:
            color_ass = self._get_color_ass(danmaku['mail'])
        
        # 处理会员透明度
        alpha_ass = ""
        if self.config.difficult_vip and danmaku['premium'] == '25':
            alpha_ass = r"\alpha&H80&"
        
        # ASS代码
        ass_code = self.config.ass_code
        
        return f"Dialogue: 1,{start_time},{end_time},Danmaku,,0,0,0,,{{\\an4\\move({sx},{sy},{ex},{ey},0,{real_speed})}}{{\\1c&{color_ass}&}}{{{alpha_ass}}}{{{ass_code}}}{danmaku['text']}\n"
    
    def _get_color_ass(self, mail: str) -> str:
        """从mail字段提取颜色并转换为ASS格式"""
        if not mail:
            return "HFFFFFF"
        
        parts = mail.split(' ')
        
        for part in parts:
            # 处理#开头的颜色
            if part.startswith('#') and len(part) == 7:
                return f"H{part[5:7]}{part[3:5]}{part[1:3]}"
            
            # 处理CSS颜色名
            color_name = re.sub(r'\d+', '', part)
            if color_name in self.CSS2ASS:
                hex_color = self.CSS2ASS[color_name]
                return f"H{hex_color[5:7]}{hex_color[3:5]}{hex_color[1:3]}"
        
        return "HFFFFFF"
    
    def _calc_text_length(self, text: str) -> int:
        """计算文本长度（考虑全角字符）"""
        length = 0
        for char in text:
            if ord(char) > 127:
                length += 2
            else:
                length += 2
        return length // 2
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间为 HH:MM:SS.CS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centisecs = int((seconds % 1) * 100)
        return f"{hours:01d}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
    
    def _format_time_mm_ss(self, seconds: float) -> str:
        """格式化时间为 MM:SS (用于AA时间显示)"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def save_ass(self, output_path: str):
        """保存ASS文件"""
        ass_content = self.convert_to_ass()
        
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            f.write(ass_content)
        
        print(f"✓ 转换完成: {output_path}")
        print(f"✓ 标题: {self.title}")
        if self.office_ids:
            print(f"✓ 运营ID: {', '.join(self.office_ids)}")
        if self.aa_start_times:
            print(f"✓ AA弹幕时间: {' '.join([f'【{t}】' for t in self.aa_start_times])}")


def main():
    parser = argparse.ArgumentParser(description='Niconico弹幕XML转ASS工具')
    parser.add_argument('input', help='输入XML文件路径')
    parser.add_argument('-o', '--output', help='输出ASS文件路径（默认：同名.ass）')
    parser.add_argument('--lines', type=int, default=11, help='弹幕行数限制（默认：11）')
    parser.add_argument('--size', type=int, default=46, help='弹幕大小（默认：46）')
    parser.add_argument('--density', type=int, default=10, help='弹幕密度（默认：10）')
    parser.add_argument('--time-offset', type=float, default=0, help='时间偏移秒数（默认：0）')
    parser.add_argument('--speed-adjust', type=float, default=1, help='速度调整秒数（默认：1）')
    parser.add_argument('--no-color', action='store_true', help='不使用弹幕颜色')
    parser.add_argument('--filter-outsider', action='store_true', help='过滤非会员弹幕')
    parser.add_argument('--use-speed-algo', action='store_true', help='使用速度算法')
    parser.add_argument('--office-ids', help='手动添加运营ID（逗号分隔）')
    parser.add_argument('--filter-keywords', help='屏蔽关键词（逗号分隔）')
    
    args = parser.parse_args()
    
    # 构建配置
    config = Config(
        limit_line_amount=args.lines,
        danmaku_size=args.size,
        danmaku_density=args.density,
        start_time_adjust=args.time_offset,
        danmaku_speed_adjust=args.speed_adjust,
        use_ass_colors=not args.no_color,
        filter_outsider=args.filter_outsider,
        use_speed_a=args.use_speed_algo,
        manual_add_office_id=args.office_ids.split(',') if args.office_ids else [],
        filter_keywords=args.filter_keywords.split(',') if args.filter_keywords else []
    )
    
    # 确定输出路径
    output_path = args.output
    if not output_path:
        output_path = args.input.rsplit('.', 1)[0] + '.ass'
    
    # 转换
    converter = NicoXML2ASS(config)
    converter.load_xml(args.input)
    converter.save_ass(output_path)


if __name__ == '__main__':
    main()
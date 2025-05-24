import subprocess
import os
import shutil
import sys
import tempfile
import logging
from typing import List, Tuple

# Configure logger for minimal output (message only)
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)


def load_config(config_file: str = "config.txt") -> dict:
    """加载配置文件"""
    if not os.path.exists(config_file):
        default_content = """# 视频剪辑配置文件
# 输入视频文件
input_video = input.mp4
# 输出视频文件  
output_video = output.mp4
# ffmpeg路径
ffmpeg_path = ffmpeg
# 是否合并输出的视频片段 (true/false)
merge_output = true
# 时间片段，每行一个，格式：开始时间 , 结束时间
# 00:03:15 , 00:05:12
# 00:15:11 , 00:22:33
# 01:01:23 , 01:35:12
"""
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(default_content)
        # These logs are for the first run when config is created.
        logger.info(f"已创建默认配置文件: {config_file}")
        logger.info("请编辑配置文件后重新运行")
        return None
    
    config = {
        "input_video": "input.mp4",
        "output_video": "output.mp4", 
        "ffmpeg_path": "ffmpeg",
        "merge_output": True,
        "segments": []
    }
    
    with open(config_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                if key in config:
                    if key == "merge_output":
                        config[key] = value.lower() == 'true'
                    else:
                        config[key] = value
            else:
                parts = line.split(',')
                if len(parts) >= 2:
                    start_time = parts[0].strip()
                    end_time = parts[1].strip()
                    config["segments"].append([start_time, end_time])
    return config


class VideoProcessor:
    def __init__(self, config: dict):
        self.input_video = config["input_video"]
        self.output_video = config["output_video"] 
        self.ffmpeg_path = config["ffmpeg_path"]
        self.segments = config["segments"]
        self.merge_output = config["merge_output"]
        self.temp_dir = None
        
    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="video_", dir=".")
        logger.info(f"创建临时目录: {self.temp_dir}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir and os.path.exists(self.temp_dir):
            if self.merge_output: 
                shutil.rmtree(self.temp_dir)
                logger.info(f"已删除临时目录: {self.temp_dir}")
            # else: no log if not deleting and not merging

    def check_ffmpeg(self) -> bool:
        if shutil.which(self.ffmpeg_path) is None:
            print(f"错误: 未找到 FFmpeg: {self.ffmpeg_path}") # Using print for critical errors
            return False
        return True

    def run_command(self, cmd: List[str]) -> bool:
        try:
            process = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
            return True
        except subprocess.CalledProcessError as e:
            print(f"错误: 命令执行失败: {' '.join(cmd)}")
            print(f"错误详情: {e.stderr if e.stderr else str(e)}")
            return False

    def extract_segment(self, start: str, end: str, output: str, num: int) -> bool:
        logger.info(f"提取片段 {num}: {start} - {end} 到 {output}")
        cmd = [
            self.ffmpeg_path, "-i", self.input_video,
            "-ss", start, "-to", end,
            "-c", "copy", "-y", output
        ]
        return self.run_command(cmd)

    def merge_segments(self, segment_files: List[str]) -> bool:
        list_file = os.path.join(self.temp_dir, "list.txt")
        with open(list_file, 'w', encoding='utf-8') as f:
            for file_path in segment_files:
                f.write(f"file '{os.path.abspath(file_path)}'\n")
        
        logger.info(f"合并片段到: {self.output_video}")
        cmd = [
            self.ffmpeg_path, "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", "-y", self.output_video
        ]
        return self.run_command(cmd)

    def process(self) -> bool:
        if not os.path.exists(self.input_video):
            print(f"错误: 输入文件不存在: {self.input_video}")
            return False
        if not self.segments:
            print("错误: 没有设置时间片段")
            return False
            
        segment_files = []
        for i, (start, end) in enumerate(self.segments, 1):
            if not self.temp_dir: 
                print("错误: 临时目录未初始化")
                return False
            output_file = os.path.join(self.temp_dir, f"part_{i}.mp4")
            if not self.extract_segment(start, end, output_file, i):
                return False
            segment_files.append(output_file)
        
        if self.merge_output:
            if not self.merge_segments(segment_files):
                return False
        # No summary message here for either case
        return True


def main():
    config_file_path = "config.txt" # Define to use consistently
    try:
        # Handle first run config creation separately for cleaner subsequent runs
        if not os.path.exists(config_file_path):
            # Call load_config to create the default file.
            # The logs from load_config itself will be printed.
            load_config(config_file_path)
            return 1 # Exit after creating default config, user needs to edit it.

        config = load_config(config_file_path)
        if config is None: 
            # This case should ideally not be hit if we check os.path.exists first,
            # unless load_config has other reasons to return None.
            return 1
            
        logger.info(f"输入: {config['input_video']}")
        logger.info(f"是否合并片段: {config['merge_output']}")
        logger.info(f"片段数: {len(config['segments'])}")
        
        with VideoProcessor(config) as processor:
            if not processor.check_ffmpeg():
                return 1
                
            if processor.process():
                # logger.info("finished") # REMOVED
                return 0 # Success, no final message
            else:
                # Errors should have been printed by process or its sub-methods
                return 1
                
    except KeyboardInterrupt:
        print("用户中断")
        return 1
    except Exception as e:
        print(f"发生未处理的错误: {e}")
        # import traceback # Uncomment for debugging if needed
        # traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
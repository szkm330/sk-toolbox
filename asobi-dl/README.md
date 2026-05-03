## requirements

- pip install
    - requests
    - pywidevine

- ffmpeg
- [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE)
- [mp4decrypt](https://www.bento4.com/downloads/)


## 视频下载
```
N_m3u8DL-RE "mpd-url" --header "User-Agent: xxx" --header "Referer: xxx" --save-name "manifest"
```

## 视频处理

### 获取密钥
```
python get_key.py
```

### 解密
```
# 视频
mp4decrypt --key xxx manifest.mp4 video_dec.mp4

# 音频
mp4decrypt --key xxx manifest.und.m4a audio_dec.m4a
```
### 合并
```
ffmpeg -i video_dec.mp4 -i audio_dec.m4a -c copy output.mp4
```

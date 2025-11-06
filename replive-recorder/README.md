# Replive Recorder

Replive直播录制工具

本项目基于 [nsy_chat_live](https://github.com/huangwg2529/nsy_chat_live) 进行开发



## 依赖

- Python
  - `pip install requests`

- FFmpeg

- [Charles](https://www.charlesproxy.com/download/)

  

## 使用方法

### 前期准备

#### 获取refresh token

##### PC端

- 修改Charles代理端口（`Proxy -> Proxy Settings`）
  - 设置Port为8888，并勾选下方的`Support  HTTP/2` 和`Enable transparent HTTP proxying`
- 修改SSL代理（`Proxy -> SSL Proxying Settings`）
  - 勾选`Enable SSL Proxying`
  - 在Include侧添加：Host为`api.replive.com`，Port为443
- 安装证书（`Help -> SSL Proxying -> Install Charles Root Certificate`）
  - 自定义证书存储位置，选择`受信任的根证书颁发机构`
  - 安装完成后，重启Charles
- 记录PC的IP地址
  - 终端输入`ipconfig`，找到IPv4地址

##### 手机端（iPhone）

- 与PC连接同一Wi-Fi

- 配置iPhone代理（`设置 -> Wi-Fi`）
  - 点击当前Wi-Fi旁边的 i 图标，滚动到最下，选择`HTTP代理 -> 手动`
    - 服务器：刚才记录的IPv4地址
    - 端口：8888

- 安装Charles证书，设置信任

  - Safari浏览器中访问`chls.pro/ssl`，下载配置文件

  - `设置 -> 通用 -> VPN与设备管理`，找到Charles Proxy SSL Proxying描述文件，点击安装

  - `设置 -> 通用 -> 关于本机`，向下滚动到`证书信任设置`，找到Charles Proxy Custom Root Certificate，打开右侧的开关

##### 抓包步骤

- 在Charles的Filter输入`replive.com`
- 在 iPhone 上打开 Replive App，进行登录操作
- 在 Charles 左侧列表中找到包含 `RefreshAccessToken` 的请求
- 在右侧的面板中，选择 Contents 标签页，然后选择 `Request -> Text`
- 记录refresh token（把第1个字符去掉）



### 录制流程

- 编辑 `replive_recorder.py`

```
# ==================== CONFIG ====================
REFRESH_TOKEN = "" // 抓取的refresh token
FFMPEG_PATH = "ffmpeg.exe" // 如果不在同一文件夹，修改为实际路径
# ==============================================
```

- 运行

```
python replive_recorder.py
```

- 运行结果示例

```
Token 刷新成功
过期时间: 2024-11-06 20:30:00

初始化成功，开始监控直播...

==================================================
主播A 开始直播
标题: 直播标题
录制到: 主播A_20241106_123456.mp4
==================================================
录制开始，进程 ID: 123456

...
```

- 停止程序

```
Ctrl + C
```

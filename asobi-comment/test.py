import asyncio
import websockets
import json
import msgpack

# --- 配置区 ---
uri = "wss://archive.cmsv.asobistore.jp/shinycolors_283_uka_imago3_ch1/archive"  # 替换为你的实际 WebSocket URI
count = 10000  # 最大请求次数
output_filename = "downloaded_comments.json"  # 输出文件名
# --- 配置区结束 ---

async def download_comments():
    print(f"连接到评论服务器: {uri}")
    all_comments_data = []
    
    async with websockets.connect(uri, compression=None) as websocket:
        # 接收并忽略初始消息
        await websocket.recv()
        print("开始下载...")

        nonecount = 0  # 连续空数据计数
        stop_after_none_streak = 20  # 连续20次空数据后停止
        
        for i in range(count):
            # 构建并发送请求
            send_payload = {"func": "archive-get", "time": str(5 * i)}
            sendtxt = json.dumps(send_payload)
            await websocket.send(sendtxt)
            
            # 接收数据
            comment_data_bytes = await websocket.recv()
            
            # 使用msgpack解包数据
            unpacked_data = msgpack.unpackb(comment_data_bytes, raw=False)
            
            # 检查是否有有效的评论数据
            has_valid_data = False
            if unpacked_data and isinstance(unpacked_data.get('archive'), list) and unpacked_data['archive']:
                has_valid_data = True
                
            # 保存数据
            all_comments_data.append(unpacked_data)
                
            # 处理连续空数据的情况
            if has_valid_data:
                nonecount = 0
            else:
                nonecount += 1
                
            if nonecount >= stop_after_none_streak:
                print(f"\n已连续 {nonecount} 次没有收到评论数据，停止下载。")
                break
                
            # 显示进度
            print(f"下载中... 请求: {i+1}/{count}, 时间: {5*i}秒, 空数据连续次数: {nonecount}", end="\r", flush=True)
    
    # 保存到文件
    print(f"\n保存 {len(all_comments_data)} 条数据到 '{output_filename}'...")
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(all_comments_data, f, ensure_ascii=False, indent=2)
    print("保存完成。")

if __name__ == "__main__":
    asyncio.run(download_comments())
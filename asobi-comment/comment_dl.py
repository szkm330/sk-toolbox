import asyncio
import websockets
import json
import msgpack

# --- 配置区 ---
uri = "wss://ac-replay-api.asobistore.jp/eozntzzte2aa/archive"
time_step = 5
max_requests = 10000
stop_after_empty = 20
output_filename = "channel.json"
# --- 配置区结束 ---

async def download_comments():
    print(f"连接到: {uri}")
    all_comments = []
    seen_comment_ids = set()
    
    async with websockets.connect(uri, compression=None) as websocket:
        print("连接成功，开始下载...")
        
        # 接收并忽略初始消息
        await websocket.recv()
        
        empty_count = 0
        
        for i in range(max_requests):
            current_time = time_step * i
            
            # 发送请求
            request = {"func": "archive-get", "time": str(current_time)}
            await websocket.send(json.dumps(request))
            
            # 接收数据
            data = await websocket.recv()
            
            # 自动识别格式并解析
            try:
                if isinstance(data, bytes):
                    # msgpack 格式
                    parsed_data = msgpack.unpackb(data, raw=False)
                else:
                    # JSON 格式
                    parsed_data = json.loads(data)
            except Exception as e:
                print(f"\n解析失败: {e}")
                empty_count += 1
                if empty_count >= stop_after_empty:
                    break
                continue
            
            # 提取评论
            comments_batch = parsed_data.get('archive', []) if parsed_data else []
            
            if comments_batch:
                new_count = 0
                for comment in comments_batch:
                    # 生成唯一ID并去重
                    comment_id = f"{comment.get('playtime', '')}_{comment.get('time', '')}"
                    if comment_id not in seen_comment_ids:
                        seen_comment_ids.add(comment_id)
                        all_comments.append(comment)
                        new_count += 1
                
                if new_count > 0:
                    empty_count = 0
                    print(f"已下载 {len(all_comments)} 条", end="\r", flush=True)
                else:
                    empty_count += 1
            else:
                empty_count += 1
            
            if empty_count >= stop_after_empty:
                print(f"\n连续 {empty_count} 次无新数据，下载完成")
                break
            
            await asyncio.sleep(0.05)
    
    # 保存文件
    if all_comments:
        print(f"\n保存到 '{output_filename}'...")
        sorted_comments = sorted(all_comments, key=lambda x: x.get('playtime', 0))
        
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(sorted_comments, f, ensure_ascii=False, indent=2)
        
        print(f"保存完成，共 {len(all_comments)} 条评论")
    else:
        print("\n未下载到任何评论")

if __name__ == "__main__":
    try:
        asyncio.run(download_comments())
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
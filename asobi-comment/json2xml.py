import json
import sys
import datetime
from decimal import Decimal, ROUND_HALF_UP

def convert_json_to_xml(input_json_filename, output_xml_filename):
    """
    将包含ASOBISTAGE评论的JSON文件转换为NicoNico XML评论文件
    """
    print(f"开始转换: {input_json_filename} -> {output_xml_filename}")

    # 读取JSON文件
    with open(input_json_filename, 'r', encoding='UTF-8') as json_file:
        comments_list = json.load(json_file)

    # 开始写入XML文件
    with open(output_xml_filename, 'w', encoding='UTF-8') as f_out:
        f_out.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<packet>\n")

        xml_comment_number = 0  # 评论编号

        # 处理每条评论
        for comment_event in comments_list:
            xml_comment_number += 1
            
            # 构建XML评论属性
            chat_attributes = [f"no=\"{xml_comment_number}\""]

            # 处理播放时间
            playtime_value = comment_event.get('playtime')
            vpos_str = "0" 
            if playtime_value is not None:
                vpos_decimal = Decimal(str(float(playtime_value))) * Decimal('100')
                vpos_str = str(vpos_decimal.quantize(Decimal('0'), rounding=ROUND_HALF_UP))
            chat_attributes.append(f"vpos=\"{vpos_str}\"")

            # 处理时间戳
            time_value_str = comment_event.get('time')
            date_unix_ts_str = "0" 
            date_usec_str = "0"    
            if time_value_str:
                time_str_for_parsing = str(time_value_str)[:26]
                try:
                    dt_object = datetime.datetime.strptime(time_str_for_parsing, '%Y-%m-%d %H:%M:%S.%f')
                    date_unix_ts_str = str(int(dt_object.timestamp()))
                    date_usec_str = dt_object.strftime('%f')
                except ValueError as e:
                    print(f"警告: 无法解析时间 '{time_value_str}': {e}")
            chat_attributes.append(f"date=\"{date_unix_ts_str}\"")
            
            # 处理评论数据
            comment_data_obj = comment_event.get('data', {})
            user_name_escaped = "anonymous" 
            user_color_str = "#FFFFFF"      
            comment_text_escaped = ""
            
            # 处理用户名
            if isinstance(comment_data_obj, dict):
                raw_user_name = str(comment_data_obj.get('userName', 'anonymous'))
                user_name_escaped = xml_escape(raw_user_name)
                
                # 处理颜色
                user_color_str = str(comment_data_obj.get('color', '#FFFFFF'))
                if not user_color_str.startswith("#"):
                    user_color_str = "#FFFFFF"

                # 处理评论文本
                comment_list = comment_data_obj.get('comment', [])
                if isinstance(comment_list, list) and len(comment_list) > 0:
                    comment_text_escaped = xml_escape(str(comment_list[0]))

            # 添加其他必要属性
            chat_attributes.append("mail=\"184\"") 
            chat_attributes.append("user_id=\"\"") 
            chat_attributes.append(f"user_name=\"{user_name_escaped}\"")
            chat_attributes.append(f"user_color=\"{user_color_str}\"")
            chat_attributes.append("anonymity=\"1\"") 
            chat_attributes.append(f"date_usec=\"{date_usec_str}\"")

            # 写入XML评论
            f_out.write(f"<chat {' '.join(chat_attributes)}>")
            f_out.write(comment_text_escaped)
            f_out.write("</chat>\n")

        f_out.write("</packet>\n")
    
    print(f"转换完成。共写入 {xml_comment_number} 条评论到 '{output_xml_filename}'。")

def xml_escape(text):
    """转义XML特殊字符"""
    return (str(text).replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\"", "&quot;")
                    .replace("'", "&apos;")
                    .replace("\u3000", "　"))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python convert_script_name.py <input_json_file>")
        print("示例: python convert_script_name.py downloaded_comments.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    if input_file.lower().endswith(".json"):
        output_file = input_file[:-5] + ".xml"
    else:
        output_file = input_file + ".xml"
        
    convert_json_to_xml(input_file, output_file)
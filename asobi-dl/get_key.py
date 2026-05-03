import requests
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH


WVD_PATH = ".wvd"

# mpd response <cenc:pssh>
PSSH_STRING = ""

# license
LICENSE_URL = "https://asobistage-api.asobistore.jp/api/v1/drm/widevine"
HEADERS = {
    "content-type": "application/octet-stream",
    "x-condition": "",
    "cookie": ""
}

def main():
    # 挂载WVD设备
    device = Device.load(WVD_PATH)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()

    # 解析PSSH并生成Challenge
    pssh = PSSH(PSSH_STRING)
    challenge = cdm.get_license_challenge(session_id, pssh)

    # 发送请求给服务器
    print("正在向 Asobi Store 请求解密密钥...")
    response = requests.post(LICENSE_URL, headers=HEADERS, data=challenge)
    
    if response.status_code != 200:
        print(f"请求失败！状态码: {response.status_code}")
        print(f"服务器返回信息: {response.text}")
        return

    # 解析许可证并提取密钥
    cdm.parse_license(session_id, response.content)
    
    print("\n===== 成功获取密钥 =====")
    for key in cdm.get_keys(session_id):
        if key.type == 'CONTENT':
            print(f"--key {key.kid.hex}:{key.key.hex()}")

    cdm.close(session_id)

if __name__ == "__main__":
    main()
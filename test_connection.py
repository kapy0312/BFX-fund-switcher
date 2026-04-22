import requests
import hashlib
import hmac
import time
import json
import os

# 讀取環境變數
from pathlib import Path

def load_env():
    env_path = Path('.env')
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

load_env()

API_KEY = os.environ.get('BFX_API_KEY', '')
API_SECRET = os.environ.get('BFX_API_SECRET', '')

def bfx_request(endpoint, body={}):
    nonce = str(int(time.time() * 1000))
    body_json = json.dumps(body)
    signature_payload = f'/api{endpoint}{nonce}{body_json}'
    
    sig = hmac.new(
        API_SECRET.encode('utf-8'),
        signature_payload.encode('utf-8'),
        hashlib.sha384
    ).hexdigest()
    
    headers = {
        'bfx-nonce': nonce,
        'bfx-apikey': API_KEY,
        'bfx-signature': sig,
        'content-type': 'application/json'
    }
    
    response = requests.post(
        f'https://api.bitfinex.com{endpoint}',
        headers=headers,
        json=body
    )
    return response.json()

# 測試：查詢錢包餘額
print('正在測試 API 連線...')
result = bfx_request('/v2/auth/r/wallets')

# if isinstance(result, list):
#     print('✅ 連線成功！錢包餘額：')
#     for wallet in result:
#         wallet_type = wallet[0]
#         currency = wallet[1]
#         balance = wallet[2]
#         if balance and balance > 0:
#             print(f'  {wallet_type} | {currency} | ${balance:.4f}')
# else:
#     print('❌ 連線失敗：', result)

if isinstance(result, list):
    print('✅ 連線成功！錢包餘額：')
    for wallet in result:
        wallet_type = wallet[0]
        currency = wallet[1]
        balance = wallet[2]        # 總餘額（含掛單中）
        available = wallet[4]      # 實際可動用
        if balance and balance > 0:
            print(f'  {wallet_type} | {currency} | 總計: ${balance:.4f} | 可動用: ${available:.4f}')
else:
    print('❌ 連線失敗：', result)
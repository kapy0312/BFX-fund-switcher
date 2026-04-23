from flask import Flask, jsonify, request, render_template
import requests
import hashlib
import hmac
import time
import json
import os
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

# 加這兩行確認有沒有讀到
print("API_KEY loaded:", API_KEY[:8] + "..." if API_KEY else "❌ 空的")
print("API_SECRET loaded:", API_SECRET[:8] + "..." if API_SECRET else "❌ 空的")

app = Flask(__name__)


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


def get_available():
    result = bfx_request('/v2/auth/r/wallets')
    wallets = {}
    for w in result:
        key = f"{w[0]}_{w[1]}"
        wallets[key] = w[4] if w[4] is not None else 0
    return wallets


def get_funding_offers():
    usd_credits = bfx_request('/v2/auth/r/funding/credits/fUSD')
    ust_credits = bfx_request('/v2/auth/r/funding/credits/fUST')

    # print("USD credits:", usd_credits)
    # print("UST credits:", ust_credits)

    def parse_credits(credits):        # ← parse_credits 要在函式裡面
        if not isinstance(credits, list):
            return []
        result = []
        for o in credits:
            if isinstance(o, list) and len(o) > 10:
                result.append({
                    'amount': round(abs(o[5]), 4),
                    'rate':   round(o[11] * 100 * 365, 4),
                    'period': o[12],
                })
        return result

    return {                           # ← return 要加回來
        'USD': parse_credits(usd_credits),
        'UST': parse_credits(ust_credits),
    }


def transfer(from_wallet, to_wallet, currency, amount):
    body = {
        'from': from_wallet,
        'to': to_wallet,
        'currency': currency,
        'amount': str(amount)
    }
    return bfx_request('/v2/auth/w/transfer', body)


def market_order(symbol, amount):
    body = {
        'type': 'EXCHANGE MARKET',
        'symbol': symbol,
        'amount': str(amount)
    }
    return bfx_request('/v2/auth/w/order/submit', body)


def do_transfer_with_retry(from_w, to_w, currency, amount):
    """重試迴圈，最多 10 次，每次間隔 3 秒"""
    for attempt in range(10):
        r = transfer(from_w, to_w, currency, amount)
        if isinstance(r, list) and r[0] == 'error':
            time.sleep(3)
        else:
            return {'success': True, 'result': r}
    return {'success': False, 'error': f'重試 10 次仍失敗，請手動執行 transfer {from_w}→{to_w} {currency} {amount}'}

# ==========================================
# API 路由
# ==========================================


@app.route('/api/balances')
def api_balances():
    try:
        w = get_available()
        return jsonify({
            'funding_USD': w.get('funding_USD', 0),
            'funding_UST': w.get('funding_UST', 0),
            'exchange_USD': w.get('exchange_USD', 0),
            'exchange_UST': w.get('exchange_UST', 0),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/offers')
def api_offers():
    try:
        offers = get_funding_offers()
        return jsonify(offers)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/switch', methods=['POST'])
def api_switch():
    data = request.json
    direction = data.get('direction')  # 'ust_to_usd' 或 'usd_to_ust'
    amount_input = data.get('amount')  # 數字或 'all'

    logs = []

    try:
        w = get_available()

        if direction == 'ust_to_usd':
            avail = w.get('funding_UST', 0)
            amount = avail if amount_input == 'all' else float(amount_input)

            if amount > avail:
                return jsonify({'success': False, 'error': f'超過可動用金額 ${avail:.4f}'}), 400

            logs.append('步驟 1/4：Funding UST → Exchange UST')
            r = transfer('funding', 'exchange', 'UST', amount)
            logs.append(f'  SUCCESS' if 'SUCCESS' in str(r) else f'  失敗: {r}')
            time.sleep(1)

            logs.append('步驟 2/4：Exchange UST 市價賣出換 USD')
            r = market_order('tUSTUSD', -amount)
            logs.append(f'  SUCCESS' if 'SUCCESS' in str(r) else f'  失敗: {r}')

            logs.append('步驟 3/4：等待市價單結算 (8秒)...')
            time.sleep(8)
            w2 = get_available()
            usd_bal = w2.get('exchange_USD', 0)
            logs.append(f'  Exchange USD 可動用: ${usd_bal:.4f}')

            if usd_bal <= 0:
                return jsonify({'success': False, 'logs': logs, 'error': 'Exchange USD 餘額為 0'})

            logs.append('步驟 4/4：Exchange USD → Funding USD')
            result = do_transfer_with_retry(
                'exchange', 'funding', 'USD', usd_bal)
            logs.append(
                '  SUCCESS' if result['success'] else f'  {result["error"]}')

        elif direction == 'usd_to_ust':
            avail = w.get('funding_USD', 0)
            amount = avail if amount_input == 'all' else float(amount_input)

            if amount > avail:
                return jsonify({'success': False, 'error': f'超過可動用金額 ${avail:.4f}'}), 400

            logs.append('步驟 1/4：Funding USD → Exchange USD')
            r = transfer('funding', 'exchange', 'USD', amount)
            logs.append(f'  SUCCESS' if 'SUCCESS' in str(r) else f'  失敗: {r}')
            time.sleep(1)

            logs.append('步驟 2/4：Exchange USD 市價買 UST')
            safe_amount = round(amount * 0.9990, 2)
            r = market_order('tUSTUSD', safe_amount)
            logs.append(f'  SUCCESS' if 'SUCCESS' in str(r) else f'  失敗: {r}')

            logs.append('步驟 3/4：等待市價單結算 (8秒)...')
            time.sleep(8)
            w2 = get_available()
            ust_bal = w2.get('exchange_UST', 0)
            logs.append(f'  Exchange UST 可動用: ${ust_bal:.4f}')

            if ust_bal <= 0:
                return jsonify({'success': False, 'logs': logs, 'error': 'Exchange UST 餘額為 0'})

            logs.append('步驟 4/4：Exchange UST → Funding UST')
            result = do_transfer_with_retry(
                'exchange', 'funding', 'UST', ust_bal)
            logs.append(
                '  SUCCESS' if result['success'] else f'  {result["error"]}')

        else:
            return jsonify({'success': False, 'error': '無效的操作方向'}), 400

        return jsonify({'success': result['success'], 'logs': logs})

    except Exception as e:
        logs.append(f'❌ 發生錯誤: {str(e)}')
        return jsonify({'success': False, 'logs': logs, 'error': str(e)}), 500


@app.route('/')
def index():
    return render_template('index.html')


def debug_api():
    print("\n" + "="*60)
    print("📋 診斷：錢包資料")
    print("="*60)
    wallets = bfx_request('/v2/auth/r/wallets')
    for w in wallets:
        print(w)

    print("\n" + "="*60)
    print("📋 診斷：fUSD 掛單")
    print("="*60)
    usd = bfx_request('/v2/auth/r/funding/offers/fUSD')
    print("筆數:", len(usd) if isinstance(usd, list) else "非陣列")
    for i, o in enumerate(usd if isinstance(usd, list) else []):
        print(f"  [{i}] {o}")

    print("\n" + "="*60)
    print("📋 診斷：fUST 掛單")
    print("="*60)
    ust = bfx_request('/v2/auth/r/funding/offers/fUST')
    print("筆數:", len(ust) if isinstance(ust, list) else "非陣列")
    for i, o in enumerate(ust if isinstance(ust, list) else []):
        print(f"  [{i}] {o}")

    print("\n" + "="*60)
    print("📋 診斷：fUSDT 掛單")
    print("="*60)
    usdt = bfx_request('/v2/auth/r/funding/offers/fUSDT')
    print("筆數:", len(usdt) if isinstance(usdt, list) else "非陣列")
    for i, o in enumerate(usdt if isinstance(usdt, list) else []):
        print(f"  [{i}] {o}")


if __name__ == '__main__':
    # debug_api()   # ← 加這行
    app.run(debug=True, port=5000)

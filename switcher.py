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


def show_balances():
    w = get_available()
    print('\n📊 目前可動用餘額：')
    print(f"  Funding  USD : ${w.get('funding_USD', 0):.4f}")
    print(f"  Funding  UST : ${w.get('funding_UST', 0):.4f}")
    print(f"  Exchange USD : ${w.get('exchange_USD', 0):.4f}")
    print(f"  Exchange UST : ${w.get('exchange_UST', 0):.4f}")
    return w


def confirm(msg):
    ans = input(f'\n{msg} (y/n): ').strip().lower()
    return ans == 'y'


def ust_to_usd(wallets):
    avail = wallets.get('funding_UST', 0)
    if avail <= 0:
        print('❌ Funding UST 沒有可動用資金')
        return

    print(f'\n可動用 Funding UST: ${avail:.4f}')
    amount_str = input('金額 (輸入 all 代表全部): ').strip()
    amount = avail if amount_str == 'all' else float(amount_str)

    if amount > avail:
        print(f'❌ 超過可動用金額 ${avail:.4f}')
        return

    if not confirm(f'將 ${amount:.4f} UST 融資 → USD 融資？'):
        return

    print('\n步驟 1/4：Funding UST → Exchange UST')
    r = transfer('funding', 'exchange', 'UST', amount)
    print(f'  結果: {r}')
    time.sleep(1)

    print('步驟 2/4：Exchange UST 市價賣出換 USD')
    r = market_order('tUSTUSD', -amount)
    print(f'  結果: {r}')

    print('步驟 3/4：等待市價單結算...')
    time.sleep(8)
    w = get_available()
    usd_bal = w.get('exchange_USD', 0)
    print(f'  Exchange USD 可動用: ${usd_bal:.4f}')

    if usd_bal <= 0:
        print('❌ Exchange USD 餘額為 0，請確認市價單是否成交')
        return

    print('步驟 4/4：Exchange USD → Funding USD')
    # 重試迴圈，最多重試 10 次，每次間隔 3 秒
    for attempt in range(10):
        r = transfer('exchange', 'funding', 'USD', usd_bal)
        if isinstance(r, list) and r[0] == 'error':
            print(f'  第 {attempt + 1} 次嘗試失敗，3 秒後重試...')
            time.sleep(3)
        else:
            print(f'  結果: {r}')
            print('\n✅ 完成！')
            break
    else:
        print(
            f'❌ 步驟 4 重試 10 次仍失敗，請手動執行 transfer exchange→funding USD {usd_bal}')


def usd_to_ust(wallets):
    avail = wallets.get('funding_USD', 0)
    if avail <= 0:
        print('❌ Funding USD 沒有可動用資金')
        return

    print(f'\n可動用 Funding USD: ${avail:.4f}')
    amount_str = input('金額 (輸入 all 代表全部): ').strip()
    amount = avail if amount_str == 'all' else float(amount_str)

    if amount > avail:
        print(f'❌ 超過可動用金額 ${avail:.4f}')
        return

    if not confirm(f'將 ${amount:.4f} USD 融資 → UST 融資？'):
        return

    print('\n步驟 1/4：Funding USD → Exchange USD')
    r = transfer('funding', 'exchange', 'USD', amount)
    print(f'  結果: {r}')
    time.sleep(1)

    print('步驟 2/4：Exchange USD 市價買 UST')
    # 預留手續費與滑點，避免金額不足，0.9990 比 0.9995 更保守
    safe_amount = round(amount * 0.9990, 2)
    r = market_order('tUSTUSD', safe_amount)
    print(f'  結果: {r}')

    print('步驟 3/4：等待市價單結算...')
    time.sleep(8)  # 從 5 秒改為 8 秒
    w = get_available()
    ust_bal = w.get('exchange_UST', 0)
    print(f'  Exchange UST 可動用: ${ust_bal:.4f}')

    if ust_bal <= 0:
        print('❌ Exchange UST 餘額為 0，請確認市價單是否成交')
        return

    print('步驟 4/4：Exchange UST → Funding UST')
    for attempt in range(10):
        r = transfer('exchange', 'funding', 'UST', ust_bal)
        if isinstance(r, list) and r[0] == 'error':
            print(f'  第 {attempt + 1} 次嘗試失敗，3 秒後重試...')
            time.sleep(3)
        else:
            print(f'  結果: {r}')
            print('\n✅ 完成！')
            break
    else:
        print(
            f'❌ 步驟 4 重試 10 次仍失敗，請手動執行 transfer exchange→funding UST {ust_bal}')


def main():
    print('=== BFX Fund Switcher ===')

    while True:
        wallets = show_balances()

        print('\n選擇操作：')
        print('  1. UST融資 → USD融資')
        print('  2. USD融資 → UST融資')
        print('  0. 離開')

        choice = input('\n請輸入選項: ').strip()

        if choice == '0':
            print('Bye!')
            break
        elif choice == '1':
            ust_to_usd(wallets)
        elif choice == '2':
            usd_to_ust(wallets)
        else:
            print('無效選項')


if __name__ == '__main__':
    main()

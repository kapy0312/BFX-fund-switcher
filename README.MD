```markdown
# BFX Fund Switcher

Bitfinex 雙幣種融資資金快速切換工具，支援 USD ↔ UST 一鍵切換，並以原生視窗介面呈現。

## 功能

- 查看 Funding / Exchange 錢包可動用餘額
- 查看目前計息中的融資掛單（USD / UST）
- 一鍵切換：UST 融資 → USD 融資（市價賣出）
- 一鍵切換：USD 融資 → UST 融資（市價買入）
- API Key 以 AES-256 加密儲存於本機，不上傳任何伺服器

## 檔案結構

```
BFX-fund-switcher/
├── app.py               # Flask 主程式 + API 路由
├── launcher.py          # pywebview 原生視窗入口
├── templates/
│   └── index.html       # 前端介面
├── requirements.txt     # 套件清單
├── build.bat            # Windows 一鍵打包
└── bfx_config.db        # 執行後自動產生，加密儲存 API Key
```

## 安裝與執行（開發模式）

### 前置需求

- Python 3.11
- Bitfinex API Key（需要 Wallets 讀取、Orders 讀寫權限）

### 步驟

```bash
# 建立虛擬環境
py -3.11 -m venv venv
venv\Scripts\activate

# 安裝套件
pip install -r requirements.txt pywebview

# 執行
python launcher.py
```

## 打包成 exe（Windows）

```bash
雙擊執行 build.bat
```

完成後 exe 在 `dist\BFX_Fund_Switcher.exe`

## 首次使用

1. 執行 exe 或 `python launcher.py`
2. 自動彈出 API Key 設定視窗
3. 輸入 Bitfinex API Key 及 Secret 後儲存
4. 頁面自動重新載入，開始正常使用

## 安全說明

| 項目       | 說明                                          |
| ---------- | --------------------------------------------- |
| 加密演算法 | AES-256 (Fernet)                              |
| 金鑰來源   | 機器 hostname + 使用者名稱，PBKDF2 衍生       |
| 儲存位置   | exe 同目錄的 `bfx_config.db`                  |
| 網路傳輸   | API Key 不會離開本機，僅用於呼叫 Bitfinex API |

> ⚠️ `bfx_config.db` 綁定目前機器，換電腦需重新輸入 Key

## 注意事項

- 執行期間請勿關閉背景程式
- 支援金額輸入或勾選「全部可動用金額」
- 切換操作約需 15~30 秒完成
```
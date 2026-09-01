# Market Trading Hours Bot
NYSE(뉴욕증권거래소)와 LSE(런던증권거래소)의 개장 및 폐장 시간 알림을 텔레그램 채널에 전송합니다.

## 기능
- 매일 KST 09:00 당일 거래 시간 안내 메시지 전송
- 장 개장 / 폐장 시각에 실시간 알림 전송
- 공휴일 및 휴장일 감지
- 재시작 시 중복 알림 방지 (JSON 상태 저장)

## 알림 예시
```
🕛 Today's Trading Hours

#NYSE
22:30 ~ 05:00 KST 🇰🇷

#LSE
17:00 ~ 01:30 KST 🇰🇷
```

```
🟢 #NYSE Market Open
🔴 #LSE Market Close
```

## 기술 스택
- Python 3.12
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [pandas-market-calendars](https://github.com/rsheftel/pandas_market_calendars)
- [holidays](https://github.com/vacanza/python-holidays)
- Docker + uv

## 시작하기
### 1. 환경 변수 설정
`src/.env.example`을 복사하여 `src/.env`를 생성하고 값을 채웁니다.

```bash
cp src/.env.example src/.env
```

```env
TELEGRAM_TOKEN=your_telegram_bot_token
CHAT_ID=@your_channel_id
```

> 텔레그램 봇 토큰은 [@BotFather](https://t.me/BotFather)에서 발급받을 수 있습니다.

### 2. Docker 이미지 빌드
```bash
docker build -t market-trading-hours .
```

### 3. 컨테이너 실행
```bash
docker run -d \
  --name market-bot \
  --restart unless-stopped \
  --env-file ./src/.env \
  -v market_data:/app/data \
  market-trading-hours
```

`market_data` named volume에 상태 파일이 저장되므로, 컨테이너 재시작 시에도 알림이 중복 전송되지 않습니다.

### 로그 확인
```bash
docker logs -f market-bot
```

## 프로젝트 구조
```
market-trading-hours/
├── src/
│   ├── app.py          # 봇 메인 코드
│   ├── .env            # 환경 변수 (git 제외)
│   └── .env.example    # 환경 변수 템플릿
├── Dockerfile
├── requirements.txt
└── .gitignore
```

## 지원 거래소
| 거래소 | 이름 | 현지 거래 시간 |
|--------|------|----------------|
| NYSE | 뉴욕증권거래소 | 09:30 ~ 16:00 ET |
| LSE | 런던증권거래소 | 08:00 ~ 16:30 GMT |

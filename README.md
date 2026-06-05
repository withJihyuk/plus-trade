# plus-trade

`plus-trade`는 한국투자증권 기반 자동 트레이딩 서비스를 만들기 위한
uv 기반 Python CLI 프로젝트입니다. 첫 버전은 운영에 필요한 기본 배관에
집중합니다. 설정 로딩, KIS 클라이언트 생성, 토큰 저장, 미국장 상태 확인,
FX 캐시, SQLite 상태 저장, Discord 알림이 포함됩니다.

아직 실제 거래 전략 실행이나 주문 제출은 구현하지 않습니다.

## 설정

```bash
uv sync
cp .env.example .env
```

실행할 모드에 맞는 KIS 인증 정보를 `.env`에 채웁니다.

```dotenv
PLUS_TRADE_ENV=local
PLUS_TRADE_LOG_LEVEL=INFO

KIS_VIRTUAL=true

KIS_REAL_HTS_ID=
KIS_REAL_ACCOUNT_NO=
KIS_REAL_APP_KEY=
KIS_REAL_APP_SECRET=

KIS_VIRTUAL_HTS_ID=
KIS_VIRTUAL_ACCOUNT_NO=
KIS_VIRTUAL_APP_KEY=
KIS_VIRTUAL_APP_SECRET=

FX_BASE_CURRENCY=USD
FX_QUOTE_CURRENCY=KRW
FX_RATE_TTL_SECONDS=3600

DISCORD_WEBHOOK_URL=
```

## 명령어

```bash
uv run plus-trade doctor
uv run plus-trade notify-test
uv run plus-trade run --once
uv run plus-trade backtest ingest-yfinance --universe configs/universes/us-core.yaml --start 2026-01-01 --end 2026-03-31 --timeframe 1h
uv run plus-trade backtest ingest --universe configs/universes/us-core.yaml --start-time 09:30 --end-time 16:00
uv run plus-trade backtest import-bars --input data/AAPL.csv --symbol AAPL
uv run plus-trade backtest run --config configs/backtests/example.yaml
```

`doctor`는 로컬 런타임 디렉터리와 SQLite 상태를 초기화한 뒤, 어떤 인증
정보와 연동이 설정되어 있는지 출력합니다.

`notify-test`는 `DISCORD_WEBHOOK_URL`이 있으면 Discord 메시지를 보냅니다.
웹훅이 없으면 아무 작업 없이 성공 종료합니다.

`run --once`는 KIS 클라이언트를 만들고, 현재 NYSE 정규장 상태를 확인하고,
USD/KRW FX 캐시가 만료됐으면 갱신하고, 런타임 상태를 저장합니다. Discord
웹훅이 설정되어 있으면 요약 알림도 보냅니다.

`backtest ingest-yfinance`는 yfinance에서 과거 OHLCV 봉 데이터를 받아 로컬
Parquet으로 저장합니다. 기본 백테스트 시간축은 `1h`입니다. 무료 데이터로
몇 달 단위 intraday 검증을 하기 위한 현실적인 절충안입니다. yfinance
intraday 데이터는 Yahoo의 보관 기간 제한을 받으므로, 해당 범위를 벗어난
요청은 provider 에러를 그대로 보여주며 실패합니다.

`backtest ingest`는 오늘의 KIS 1분봉 차트 데이터를 받아 로컬 Parquet으로
저장합니다. KIS 분봉 endpoint는 당일 intraday 용도이므로, 기본 과거
백테스트 데이터 소스가 아니라 운영 데이터 경로입니다. 외부 CSV 또는
Parquet 데이터는 `backtest import-bars`로 넣을 수 있습니다. `backtest run`은
로컬 Parquet만 읽고, long-only target-weight 전략 신호, 다음 봉 시가 체결,
비용, 슬리피지, OOS, 레짐 요약을 적용합니다.

## 백테스트 출력

`portfolio summary`를 가장 먼저 봅니다. 설정된 모든 종목에 자본을 동일하게
배분한 뒤 합산한 포트폴리오 결과입니다. `symbol breakdown`은 성과가 여러
종목에서 고르게 나온 것인지, 특정 종목 하나에 끌려간 것인지 보여줍니다.

주요 필드:

- `total return`: 설정 기간 동안의 전체 포트폴리오 수익률입니다.
- `cagr`: 연율화 수익률입니다. 짧은 백테스트에서는 숫자가 과장될 수
  있습니다.
- `sharpe` / `sortino`: 위험 대비 수익률입니다. 음수면 리스크를 감수했지만
  전략이 손실을 냈다는 뜻입니다.
- `mdd`: 포트폴리오 고점 대비 최대 낙폭입니다.
- `calmar`: CAGR을 최대 낙폭의 절댓값으로 나눈 값입니다.
- `turnover`: 거래 notional을 초기 자본으로 나눈 회전율입니다.
- `trades`: 시뮬레이션 체결 횟수입니다.

현재 예제 전략은 파이프라인 확인용입니다. 포트폴리오 수익률이 음수이고,
Sharpe가 음수이고, turnover가 높고, 횡보장이나 하락장 레짐에서 손실이
난다면 데이터나 엔진 문제가 아니라 전략 실패로 봅니다. 이동평균 샘플
전략이 whipsaw에 걸리고, 신호 품질 대비 너무 많은 비용을 내고 있다는
뜻입니다.

과최적화 여부를 판단할 때는 전체 기간 요약보다
`portfolio walk-forward OOS summary`가 더 중요합니다.
`portfolio regime breakdown`은 시장 상태별로 전략이 어디서 벌고 어디서
잃는지 보여줍니다. `uptrend_*` 레짐에서만 작동하는 전략은 실제 후보로
보기 전에 필터, 현금 대기 규칙, 리스크 제어가 필요합니다.

전략 인터페이스, 체결 가정, 지표 정의, 전략 승격 체크리스트는
`docs/strategy-development.md`를 참고합니다.

## 런타임 경로

런타임 파일 경로는 의도적으로 코드에 고정되어 있습니다.

- `var/plus_trade.sqlite3`
- `var/kis_tokens`
- `var/data/bars/1m/{SYMBOL}.parquet`
- `var/data/bars/1h/{SYMBOL}.parquet`
- `var/logs`

KIS 토큰 저장과 갱신은 `python-kis`의 `keep_token=var/kis_tokens`로 항상
활성화됩니다. v1에서는 WebSocket 사용을 항상 비활성화합니다.

## 백테스트 데이터 계약

가져오는 봉 데이터는 다음 컬럼을 포함해야 합니다.

```text
timestamp,symbol,open,high,low,close,volume
```

timestamp는 UTC로 정규화됩니다. 백테스트 실행은 KIS나 yfinance를 직접
호출하지 않습니다. 먼저 설정된 timeframe의 로컬 Parquet을 읽고, 해당
timeframe 캐시가 없으면 로컬 `1m` 데이터를 리샘플링합니다.

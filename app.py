import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="투자 포트 & 매매일지 MVP", layout="wide")

st.title("투자 포트 자동 해석기 + 매매일지 분석기")
st.caption("수동 입력 기반 MVP | 숫자 변환 안정화 버전")

# -----------------------------
# 유틸
# -----------------------------
def safe_numeric(series):
    return pd.to_numeric(series, errors="coerce")

def score_growth(x):
    if pd.isna(x):
        return 0
    if x >= 80:
        return 25
    elif x >= 50:
        return 22
    elif x >= 30:
        return 18
    elif x >= 15:
        return 12
    elif x >= 5:
        return 7
    return 3

def score_psr(x):
    if pd.isna(x):
        return 0
    if x <= 3:
        return 20
    elif x <= 6:
        return 17
    elif x <= 10:
        return 13
    elif x <= 15:
        return 8
    elif x <= 25:
        return 4
    return 1

def score_tam(x):
    if pd.isna(x):
        return 0
    x = max(1, min(10, x))
    return x * 2

def score_margin(x):
    if pd.isna(x):
        return 0
    if x >= 25:
        return 15
    elif x >= 15:
        return 12
    elif x >= 5:
        return 8
    elif x >= 0:
        return 5
    elif x >= -20:
        return 2
    return 0

def score_balance(x):
    """
    순부채/현금:
    양수 = 순현금 쪽으로 가정
    음수 = 순부채 쪽으로 가정
    """
    if pd.isna(x):
        return 0
    if x >= 1.0:
        return 15
    elif x >= 0.3:
        return 12
    elif x >= 0:
        return 9
    elif x >= -0.5:
        return 5
    elif x >= -1.0:
        return 2
    return 0

def total_score(row):
    return (
        score_growth(row["매출성장률(%)"])
        + score_psr(row["PSR"])
        + score_tam(row["TAM점수(1-10)"])
        + score_margin(row["영업이익률(%)"])
        + score_balance(row["순부채/현금"])
    )

def score_comment(score):
    if score >= 80:
        return "매우 강함: 고성장 + 밸류/재무 균형이 꽤 좋음"
    elif score >= 65:
        return "좋음: 성장성 뚜렷, 일부 밸류 부담 감안 가능"
    elif score >= 50:
        return "보통 이상: 강점은 있으나 약점도 분명함"
    elif score >= 35:
        return "애매함: 선택적 접근 필요"
    return "주의: 숫자상 리스크가 큼"

def safe_bool_ratio(series):
    if len(series) == 0:
        return 0.0
    mapped = series.astype(str).str.strip().str.lower().map(
        {
            "true": 1,
            "false": 0,
            "1": 1,
            "0": 0,
            "yes": 1,
            "no": 0,
            "y": 1,
            "n": 0,
            "예": 1,
            "아니오": 0,
        }
    )
    return mapped.fillna(0).mean()

# -----------------------------
# 기본 데이터
# -----------------------------
default_portfolio = pd.DataFrame(
    [
        {
            "종목": "RKLB",
            "매출성장률(%)": 45,
            "PSR": 11,
            "TAM점수(1-10)": 9,
            "영업이익률(%)": -18,
            "순부채/현금": 0.4,
            "메모": "launch backlog platform founder-led",
        },
        {
            "종목": "MSTR",
            "매출성장률(%)": 70,
            "PSR": 30,
            "TAM점수(1-10)": 8,
            "영업이익률(%)": -120,
            "순부채/현금": -0.5,
            "메모": "bitcoin leverage vehicle",
        },
        {
            "종목": "CEG",
            "매출성장률(%)": 18,
            "PSR": 4,
            "TAM점수(1-10)": 7,
            "영업이익률(%)": 18,
            "순부채/현금": 1.1,
            "메모": "power recurring contract",
        },
    ]
)

default_trades = pd.DataFrame(
    [
        {
            "날짜": "2026-03-01",
            "종목": "RKLB",
            "수익률(%)": 12,
            "추격매수": "False",
            "계획준수": "True",
            "손절규칙준수": "True",
            "메모": "분할매수 잘함",
        },
        {
            "날짜": "2026-03-05",
            "종목": "MSTR",
            "수익률(%)": -8,
            "추격매수": "True",
            "계획준수": "False",
            "손절규칙준수": "False",
            "메모": "흥분해서 추격",
        },
        {
            "날짜": "2026-03-10",
            "종목": "CEG",
            "수익률(%)": 6,
            "추격매수": "False",
            "계획준수": "True",
            "손절규칙준수": "True",
            "메모": "계획대로 보유",
        },
    ]
)

# -----------------------------
# 탭 구성
# -----------------------------
tab1, tab2 = st.tabs(["포트 자동 해석기", "매매일지 분석기"])

# =============================
# 1. 포트 자동 해석기
# =============================
with tab1:
    st.subheader("포트 CSV 업로드 또는 직접 입력")

    uploaded_port = st.file_uploader("포트 CSV 업로드", type=["csv"], key="portfolio_csv")

    if uploaded_port is not None:
        try:
            portfolio_df = pd.read_csv(uploaded_port)
        except Exception as e:
            st.error(f"CSV 읽기 실패: {e}")
            portfolio_df = default_portfolio.copy()
    else:
        portfolio_df = default_portfolio.copy()

    required_port_cols = [
        "종목",
        "매출성장률(%)",
        "PSR",
        "TAM점수(1-10)",
        "영업이익률(%)",
        "순부채/현금",
        "메모",
    ]

    for col in required_port_cols:
        if col not in portfolio_df.columns:
            portfolio_df[col] = "" if col in ["종목", "메모"] else 0

    portfolio_df = portfolio_df[required_port_cols]

    edited_port = st.data_editor(
        portfolio_df,
        num_rows="dynamic",
        use_container_width=True,
        key="portfolio_editor",
    )

    numeric_cols = [
        "매출성장률(%)",
        "PSR",
        "TAM점수(1-10)",
        "영업이익률(%)",
        "순부채/현금",
    ]

    # 여기서 안전하게 숫자 변환
    for col in numeric_cols:
        edited_port[col] = safe_numeric(edited_port[col])

    edited_port["종목"] = edited_port["종목"].astype(str).fillna("")
    edited_port["메모"] = edited_port["메모"].astype(str).fillna("")

    # 종목 빈값 제거
    scored_df = edited_port.copy()
    scored_df = scored_df[scored_df["종목"].str.strip() != ""]

    if len(scored_df) == 0:
        st.info("종목을 1개 이상 입력해줘.")
    else:
        scored_df["총점"] = scored_df.apply(total_score, axis=1)
        scored_df["해석"] = scored_df["총점"].apply(score_comment)
        scored_df = scored_df.sort_values("총점", ascending=False).reset_index(drop=True)

        st.subheader("점수 결과")
        st.dataframe(scored_df, use_container_width=True)

        st.subheader("상위 종목 코멘트")
        for _, row in scored_df.iterrows():
            st.markdown(
                f"""
**{row['종목']}** — {row['총점']}점  
- 성장률: {row['매출성장률(%)']}
- PSR: {row['PSR']}
- TAM: {row['TAM점수(1-10)']}
- 영업이익률: {row['영업이익률(%)']}
- 순부채/현금: {row['순부채/현금']}
- 메모: {row['메모']}
- 판단: {row['해석']}
"""
            )

# =============================
# 2. 매매일지 분석기
# =============================
with tab2:
    st.subheader("매매일지 CSV 업로드 또는 직접 입력")

    uploaded_trade = st.file_uploader("매매일지 CSV 업로드", type=["csv"], key="trade_csv")

    if uploaded_trade is not None:
        try:
            trades_df = pd.read_csv(uploaded_trade)
        except Exception as e:
            st.error(f"CSV 읽기 실패: {e}")
            trades_df = default_trades.copy()
    else:
        trades_df = default_trades.copy()

    required_trade_cols = [
        "날짜",
        "종목",
        "수익률(%)",
        "추격매수",
        "계획준수",
        "손절규칙준수",
        "메모",
    ]

    for col in required_trade_cols:
        if col not in trades_df.columns:
            trades_df[col] = ""

    trades_df = trades_df[required_trade_cols]

    edited_trades = st.data_editor(
        trades_df,
        num_rows="dynamic",
        use_container_width=True,
        key="trade_editor",
    )

    edited_trades["수익률(%)"] = safe_numeric(edited_trades["수익률(%)"])
    edited_trades["종목"] = edited_trades["종목"].astype(str).fillna("")
    edited_trades["메모"] = edited_trades["메모"].astype(str).fillna("")

    analyzed = edited_trades.copy()
    analyzed = analyzed[analyzed["종목"].str.strip() != ""]
    analyzed = analyzed.dropna(subset=["수익률(%)"])

    if len(analyzed) == 0:
        st.info("매매일지를 1개 이상 입력해줘.")
    else:
        total_trades = len(analyzed)
        win_rate = (analyzed["수익률(%)"] > 0).mean() * 100
        avg_return = analyzed["수익률(%)"].mean()
        chase_ratio = safe_bool_ratio(analyzed["추격매수"]) * 100
        plan_ratio = safe_bool_ratio(analyzed["계획준수"]) * 100
        stop_ratio = safe_bool_ratio(analyzed["손절규칙준수"]) * 100

        c1, c2, c3 = st.columns(3)
        c1.metric("총 매매 수", total_trades)
        c2.metric("승률", f"{win_rate:.1f}%")
        c3.metric("평균 수익률", f"{avg_return:.2f}%")

        c4, c5, c6 = st.columns(3)
        c4.metric("추격매수 비율", f"{chase_ratio:.1f}%")
        c5.metric("계획준수율", f"{plan_ratio:.1f}%")
        c6.metric("손절규칙 준수율", f"{stop_ratio:.1f}%")

        st.subheader("패턴 해석")

        insights = []

        if chase_ratio >= 40:
            insights.append("추격매수 비율이 높음 → 고점 진입 습관 점검 필요")
        else:
            insights.append("추격매수 비율이 낮은 편 → 진입 통제는 비교적 양호")

        if plan_ratio < 60:
            insights.append("계획준수율이 낮음 → 시나리오 없이 매매하는 비중이 있음")
        else:
            insights.append("계획준수율이 괜찮음 → 사전 기준을 잘 지키는 편")

        if stop_ratio < 60:
            insights.append("손절규칙 준수율이 낮음 → 손실 통제가 흔들릴 가능성")
        else:
            insights.append("손절규칙 준수율이 양호 → 리스크 관리 습관 괜찮음")

        if avg_return < 0:
            insights.append("평균 수익률이 음수 → 진입보다 청산 규칙 재점검 필요")
        else:
            insights.append("평균 수익률이 플러스 → 기본 매매 구조는 나쁘지 않음")

        if win_rate < 50 and avg_return > 0:
            insights.append("승률은 낮아도 손익비가 좋을 수 있음")
        elif win_rate > 50 and avg_return < 0:
            insights.append("승률은 높지만 크게 잃는 매매가 섞였을 수 있음")

        for text in insights:
            st.write(f"- {text}")

        st.subheader("원본 매매일지")
        st.dataframe(analyzed, use_container_width=True)

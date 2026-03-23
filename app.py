import math
from io import StringIO

import pandas as pd
import streamlit as st

st.set_page_config(page_title='투자 포트 & 매매일지 MVP', layout='wide')

st.title('투자 포트 해석기 + 매매일지 분석기')
st.caption('수동 입력/CSV 업로드 기반의 가벼운 바이브 코딩 MVP')


def to_num(x, default=0.0):
    try:
        if pd.isna(x):
            return default
        if isinstance(x, str):
            x = x.replace('%', '').replace(',', '').strip()
        return float(x)
    except Exception:
        return default


def clamp(x, low=0, high=100):
    return max(low, min(high, x))


def growth_score(g):
    # 0~100, 50% 성장률이면 매우 높게 반영
    return clamp(g * 1.6)


def psr_score(psr):
    # 낮을수록 유리. 고성장주 감안해 완전 저PSR 편향은 줄임
    if psr <= 2:
        return 95
    if psr <= 4:
        return 85
    if psr <= 7:
        return 72
    if psr <= 10:
        return 58
    if psr <= 15:
        return 40
    return 22


def tam_score(tam):
    # 사용자가 1~10으로 넣는다고 가정
    return clamp(tam * 10)


def margin_score(m):
    # 영업이익률 -20~30 범위를 0~100으로 단순 매핑
    return clamp((m + 20) * 2)


def leverage_penalty(net_debt_to_cash):
    # 순현금이면 음수 또는 0, 부채가 높을수록 패널티
    if net_debt_to_cash <= 0:
        return 0
    if net_debt_to_cash <= 0.5:
        return 5
    if net_debt_to_cash <= 1.0:
        return 10
    if net_debt_to_cash <= 2.0:
        return 18
    return 28


def conviction_bonus(note: str):
    text = (note or '').lower()
    bonus = 0
    keywords = {
        'backlog': 4,
        'contract': 4,
        'founder-led': 3,
        'recurring': 4,
        'moat': 5,
        'platform': 3,
        'fcf': 4,
        'launch': 3,
        'satellite': 3,
        'ai': 3,
        'bitcoin': 3,
        'smr': 3,
    }
    for k, v in keywords.items():
        if k in text:
            bonus += v
    return min(bonus, 12)


def risk_flag_text(row):
    flags = []
    if row['PSR'] >= 10:
        flags.append('고밸류')
    if row['영업이익률(%)'] < 0:
        flags.append('적자')
    if row['순부채/현금'] > 1:
        flags.append('재무부담')
    if row['매출성장률(%)'] < 15:
        flags.append('성장둔화')
    return ', '.join(flags) if flags else '양호'


def score_company(row):
    gs = growth_score(row['매출성장률(%)'])
    ps = psr_score(row['PSR'])
    ts = tam_score(row['TAM점수(1-10)'])
    ms = margin_score(row['영업이익률(%)'])
    penalty = leverage_penalty(row['순부채/현금'])
    bonus = conviction_bonus(row.get('메모', ''))

    score = 0.34 * gs + 0.20 * ps + 0.20 * ts + 0.16 * ms + bonus - penalty
    score = round(clamp(score), 1)

    if score >= 80:
        verdict = '강한 후보'
    elif score >= 65:
        verdict = '관심 유지'
    elif score >= 50:
        verdict = '선별 접근'
    else:
        verdict = '보수적 접근'

    return pd.Series({
        '성장점수': round(gs, 1),
        '밸류점수': round(ps, 1),
        '시장점수': round(ts, 1),
        '수익성점수': round(ms, 1),
        '최종점수': score,
        '판정': verdict,
        '리스크체크': risk_flag_text(row),
    })


def analyze_trades(df):
    x = df.copy()
    x['수익률(%)'] = x['수익률(%)'].apply(to_num)
    x['보유일수'] = x['보유일수'].apply(lambda v: int(to_num(v, 0)))
    x['추격매수'] = x['추격매수'].astype(str).str.lower().isin(['1', 'true', 'y', 'yes'])
    x['계획준수'] = x['계획준수'].astype(str).str.lower().isin(['1', 'true', 'y', 'yes'])
    x['손절규칙준수'] = x['손절규칙준수'].astype(str).str.lower().isin(['1', 'true', 'y', 'yes'])

    total = len(x)
    win_rate = (x['수익률(%)'] > 0).mean() * 100 if total else 0
    avg_return = x['수익률(%)'].mean() if total else 0
    avg_win = x.loc[x['수익률(%)'] > 0, '수익률(%)'].mean() if (x['수익률(%)'] > 0).any() else 0
    avg_loss = x.loc[x['수익률(%)'] <= 0, '수익률(%)'].mean() if (x['수익률(%)'] <= 0).any() else 0
    plan_rate = x['계획준수'].mean() * 100 if total else 0
    stop_rate = x['손절규칙준수'].mean() * 100 if total else 0
    chase_rate = x['추격매수'].mean() * 100 if total else 0

    bad_chase = x.loc[x['추격매수'], '수익률(%)'].mean() if x['추격매수'].any() else float('nan')
    calm_trade = x.loc[~x['추격매수'], '수익률(%)'].mean() if (~x['추격매수']).any() else float('nan')

    insights = []
    if chase_rate >= 35:
        insights.append('추격매수 비중이 높음 → 진입 기준선/분할매수 규칙 필요')
    if plan_rate < 60:
        insights.append('사전 계획 없이 들어간 비중이 큼 → 매수 이유/손절 기준을 먼저 적기')
    if stop_rate < 60:
        insights.append('손절 규칙 준수율이 낮음 → 최대 손실 허용치 사전 설정 필요')
    if avg_loss < -8:
        insights.append('평균 손실폭이 큼 → 손실은 짧게, 확신은 분할로')
    if avg_win > 0 and avg_loss < 0 and abs(avg_win) < abs(avg_loss):
        insights.append('손익비가 아쉬움 → 익절보다 손절 관리가 먼저')
    if total >= 5 and not math.isnan(bad_chase) and not math.isnan(calm_trade) and bad_chase < calm_trade:
        insights.append('추격매수 성과가 비추격보다 낮음 → 눌림/리테스트 구간 선호 전략 검토')
    if not insights:
        insights.append('기록 패턴은 비교적 안정적. 더 많은 샘플이 쌓이면 정확도가 올라감')

    summary = {
        '총 매매 수': int(total),
        '승률(%)': round(win_rate, 1),
        '평균 수익률(%)': round(avg_return, 2),
        '평균 이익(%)': round(avg_win, 2) if not pd.isna(avg_win) else 0,
        '평균 손실(%)': round(avg_loss, 2) if not pd.isna(avg_loss) else 0,
        '계획준수율(%)': round(plan_rate, 1),
        '손절규칙준수율(%)': round(stop_rate, 1),
        '추격매수비율(%)': round(chase_rate, 1),
        '추격매수 평균 수익률(%)': round(bad_chase, 2) if not pd.isna(bad_chase) else None,
        '비추격매수 평균 수익률(%)': round(calm_trade, 2) if not pd.isna(calm_trade) else None,
    }
    return summary, insights


def parse_csv(uploaded_file, default_df):
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    return default_df.copy()


sample_portfolio = pd.DataFrame([
    {'종목': 'RKLB', '매출성장률(%)': 45, 'PSR': 11, 'TAM점수(1-10)': 9, '영업이익률(%)': -18, '순부채/현금': 0.4, '메모': 'launch backlog platform founder-led'},
    {'종목': 'IONQ', '매출성장률(%)': 70, 'PSR': 30, 'TAM점수(1-10)': 8, '영업이익률(%)': -120, '순부채/현금': -0.5, '메모': 'ai moat platform'},
    {'종목': 'CEG', '매출성장률(%)': 18, 'PSR': 4, 'TAM점수(1-10)': 7, '영업이익률(%)': 18, '순부채/현금': 1.1, '메모': 'power recurring contract'},
])

sample_trades = pd.DataFrame([
    {'날짜': '2026-03-01', '종목': 'RKLB', '수익률(%)': 12, '보유일수': 24, '추격매수': False, '계획준수': True, '손절규칙준수': True, '메모': '리테스트 매수'},
    {'날짜': '2026-03-03', '종목': 'IONQ', '수익률(%)': -9, '보유일수': 7, '추격매수': True, '계획준수': False, '손절규칙준수': False, '메모': '급등 따라감'},
    {'날짜': '2026-03-08', '종목': 'BTC', '수익률(%)': 5, '보유일수': 11, '추격매수': False, '계획준수': True, '손절규칙준수': True, '메모': '분할 진입'},
    {'날짜': '2026-03-12', '종목': 'OKLO', '수익률(%)': -14, '보유일수': 5, '추격매수': True, '계획준수': False, '손절규칙준수': False, '메모': '뉴스 보고 진입'},
    {'날짜': '2026-03-16', '종목': 'RDW', '수익률(%)': 7, '보유일수': 18, '추격매수': False, '계획준수': True, '손절규칙준수': True, '메모': '눌림 매수'},
])


tab1, tab2 = st.tabs(['1) 포트 해석기', '2) 매매일지 분석기'])

with tab1:
    st.subheader('포트 자동 해석기')
    st.write('종목별 성장/밸류/시장/수익성을 점수화해서 빠르게 보는 용도야.')

    uploaded = st.file_uploader('포트 CSV 업로드', type=['csv'], key='portfolio')
    df = parse_csv(uploaded, sample_portfolio)
    st.data_editor(df, num_rows='dynamic', use_container_width=True, key='portfolio_editor')

    edited = st.session_state['portfolio_editor']
    for col in ['매출성장률(%)', 'PSR', 'TAM점수(1-10)', '영업이익률(%)', '순부채/현금']:
        edited[col] = edited[col].apply(to_num)

    scored = pd.concat([edited, edited.apply(score_company, axis=1)], axis=1)
    scored = scored.sort_values('최종점수', ascending=False)

    c1, c2, c3 = st.columns(3)
    c1.metric('평균 점수', round(scored['최종점수'].mean(), 1))
    c2.metric('최고 점수 종목', scored.iloc[0]['종목'])
    c3.metric('강한 후보 수', int((scored['최종점수'] >= 80).sum()))

    st.dataframe(scored, use_container_width=True)

    csv_data = scored.to_csv(index=False).encode('utf-8-sig')
    st.download_button('점수 결과 CSV 다운로드', data=csv_data, file_name='portfolio_scored.csv', mime='text/csv')

with tab2:
    st.subheader('매매일지 분석기')
    st.write('추격매수/계획준수/손절규칙 패턴을 잡아주는 용도야.')

    uploaded2 = st.file_uploader('매매일지 CSV 업로드', type=['csv'], key='trades')
    tdf = parse_csv(uploaded2, sample_trades)
    st.data_editor(tdf, num_rows='dynamic', use_container_width=True, key='trades_editor')
    edited_t = st.session_state['trades_editor']

    summary, insights = analyze_trades(edited_t)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('총 매매 수', summary['총 매매 수'])
    c2.metric('승률', f"{summary['승률(%)']}%")
    c3.metric('평균 수익률', f"{summary['평균 수익률(%)']}%")
    c4.metric('추격매수 비율', f"{summary['추격매수비율(%)']}%")

    st.write('### 요약 지표')
    st.json(summary)

    st.write('### 패턴 인사이트')
    for item in insights:
        st.write(f'- {item}')

    out = pd.DataFrame({'인사이트': insights})
    st.download_button('인사이트 TXT 다운로드', data='\n'.join(insights), file_name='trade_insights.txt', mime='text/plain')

with st.expander('CSV 형식 가이드'):
    st.markdown('''
**포트 CSV 컬럼**  
종목, 매출성장률(%), PSR, TAM점수(1-10), 영업이익률(%), 순부채/현금, 메모

**매매일지 CSV 컬럼**  
날짜, 종목, 수익률(%), 보유일수, 추격매수, 계획준수, 손절규칙준수, 메모
''')

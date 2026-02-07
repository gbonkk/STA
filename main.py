# -*- coding: utf-8 -*-
"""
주식 분석 프로그램 - Yahoo Finance API 기반
- 요청 종목의 주가 및 과거 데이터 분석
- 주가 방향성, 기술적 지표 제공
- Flet + yfinance + Plotly
"""

import os
import shutil

# ==========================================
# [긴급 패치] SSL 인증서 경로 오류 해결 (Windows 한글 경로 대응, Android에서는 미적용)
# ==========================================
def fix_ssl_korean_path():
    if os.name != "nt":
        return
    try:
        import certifi
        original_cert_path = certifi.where()
        safe_dir = "C:\\Temp_Cert"
        if not os.path.exists(safe_dir):
            os.makedirs(safe_dir)
        safe_cert_path = os.path.join(safe_dir, "cacert.pem")
        shutil.copy(original_cert_path, safe_cert_path)
        os.environ["SSL_CERT_FILE"] = safe_cert_path
        os.environ["REQUESTS_CA_BUNDLE"] = safe_cert_path
    except Exception:
        pass


fix_ssl_korean_path()

import flet as ft
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta


# ========== 지표 계산 함수 ==========
def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    ma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = ma + (std * std_dev)
    lower = ma - (std * std_dev)
    return ma, upper, lower


def get_direction_analysis(price: float, ma20: float, ma60: float, rsi: float) -> dict:
    result = {"opinion": "관망 필요", "details": []}
    if pd.isna(ma20) or pd.isna(rsi):
        result["details"].append("데이터 부족으로 분석 제한")
        return result

    if price > ma20 and price > ma60:
        result["details"].append("주가가 20일·60일 이평선 위 (상승 추세)")
    elif price < ma20 and price < ma60:
        result["details"].append("주가가 20일·60일 이평선 아래 (하락 추세)")
    else:
        result["details"].append("이평선 근처 구간 (추세 모호)")

    if rsi >= 70:
        result["details"].append(f"RSI {rsi:.0f} - 과매수 구간 (조정 가능성)")
    elif rsi <= 30:
        result["details"].append(f"RSI {rsi:.0f} - 과매도 구간 (반등 가능성)")
    else:
        result["details"].append(f"RSI {rsi:.0f} - 중립 구간")

    above_ma = price > ma20
    overbought = rsi >= 70
    oversold = rsi <= 30
    if above_ma and not overbought:
        result["opinion"] = "상승 추세"
    elif not above_ma and not oversold:
        result["opinion"] = "하락 추세"
    elif overbought:
        result["opinion"] = "관망 필요 (과매수)"
    elif oversold:
        result["opinion"] = "관망 필요 (과매도)"
    return result


# ========== 차트 생성 함수 ==========
def build_chart1_html(df: pd.DataFrame) -> str:
    """주가 + 거래량 + RSI"""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
        row_heights=[0.65, 0.35], subplot_titles=("주가 및 거래량", "RSI (14)"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
    )
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name="주가", increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        ), row=1, col=1, secondary_y=False
    )
    fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA20", line=dict(color="#2196F3", width=2)), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=df.index, y=df["MA60"], name="MA60", line=dict(color="#FF9800", width=2)), row=1, col=1, secondary_y=False)
    colors = ["#26a69a" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "#ef5350" for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="거래량", marker_color=colors, opacity=0.5), row=1, col=1, secondary_y=True)
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="#9C27B0", width=2)), row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.6, row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.6, row=2, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_white", height=500, margin=dict(l=40, r=20, t=40, b=40))
    fig.update_yaxes(title_text="주가", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="거래량", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    return fig.to_html(include_plotlyjs="cdn", config={"displayModeBar": True, "responsive": True}, full_html=False)


def build_chart2_html(df: pd.DataFrame) -> str:
    """MACD"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color="#2196F3")))
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_Signal"], name="Signal", line=dict(color="#FF9800")))
    colors_hist = ["#26a69a" if v >= 0 else "#ef5350" for v in df["MACD_Hist"]]
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], name="Histogram", marker_color=colors_hist, opacity=0.7))
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(template="plotly_white", height=400, title="MACD (12, 26, 9)", margin=dict(l=40, r=20, t=40, b=40))
    return fig.to_html(include_plotlyjs="cdn", config={"displayModeBar": True, "responsive": True}, full_html=False)


def build_chart3_html(df: pd.DataFrame) -> str:
    """볼린저 밴드"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="종가", line=dict(color="#333")))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], name="상단밴드", line=dict(color="#ef5350", dash="dash")))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Middle"], name="중간(20일)", line=dict(color="#2196F3")))
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], name="하단밴드", line=dict(color="#26a69a", dash="dash")))
    fig.update_layout(template="plotly_white", height=400, title="볼린저 밴드 (20일, 2σ)", margin=dict(l=40, r=20, t=40, b=40))
    return fig.to_html(include_plotlyjs="cdn", config={"displayModeBar": True, "responsive": True}, full_html=False)


# ========== 메인 앱 ==========
def main(page: ft.Page):
    page.title = "AAPL - 주식 분석 대시보드"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    # Android APK 호환: window_min_* 제거 (모바일에서는 무의미)

    # 메인 컨텐츠 영역
    main_column = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

    def load_data_and_display(t: str, p: int):
        try:
            stock = yf.Ticker(t)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=p)
            df = stock.history(start=start_date, end=end_date, auto_adjust=True)
            info = stock.info

            if df.empty or len(df) < 60:
                page.show_snack_bar(ft.SnackBar(content=ft.Text("데이터가 부족합니다. 티커를 확인 후 다시 시도하세요."), open=True))
                return

            df["MA20"] = df["Close"].rolling(window=20).mean()
            df["MA60"] = df["Close"].rolling(window=60).mean()
            df["RSI"] = calc_rsi(df["Close"], 14)
            macd_line, signal_line, hist = calc_macd(df["Close"])
            df["MACD"] = macd_line
            df["MACD_Signal"] = signal_line
            df["MACD_Hist"] = hist
            bb_ma, bb_upper, bb_lower = calc_bollinger(df["Close"])
            df["BB_Middle"] = bb_ma
            df["BB_Upper"] = bb_upper
            df["BB_Lower"] = bb_lower

            company_name = info.get("longName") or info.get("shortName") or t
            last = df.iloc[-1]
            current_price = last["Close"]
            ma20_val = last["MA20"]
            ma60_val = last["MA60"]
            rsi_val = last["RSI"]
            analysis = get_direction_analysis(current_price, ma20_val, ma60_val, rsi_val)

            # 진단 색상
            if "상승 추세" in analysis["opinion"]:
                opinion_color = ft.Colors.GREEN
            elif "하락 추세" in analysis["opinion"]:
                opinion_color = ft.Colors.RED
            else:
                opinion_color = ft.Colors.ORANGE

            rsi_color = ft.Colors.GREEN if rsi_val <= 30 else (ft.Colors.RED if rsi_val >= 70 else ft.Colors.AMBER)
            ma20_str = f"${ma20_val:,.2f}" if not pd.isna(ma20_val) else "-"
            ma60_str = f"${ma60_val:,.2f}" if not pd.isna(ma60_val) else "-"

            content = ft.Column(
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                controls=[
                    ft.Container(
                        content=ft.Column([
                            ft.Text(f"📈 {company_name} ({t}) 주식 분석", size=22, weight=ft.FontWeight.BOLD),
                            ft.Text(f"기준일: {df.index[-1].strftime('%Y-%m-%d')} | 기간: 최근 {p}일 | 데이터: Yahoo Finance", size=12, color=ft.Colors.GREY_600),
                        ], spacing=4),
                        padding=ft.padding.only(bottom=16),
                    ),
                    ft.Text("📊 주가 방향성 분석", size=16, weight=ft.FontWeight.W_600),
                    ft.Container(height=8),
                    ft.Row([
                        ft.Container(
                            content=ft.Column([
                                ft.Text("현재가", size=12, color=ft.Colors.GREY_600),
                                ft.Text(f"${current_price:,.2f}", size=18, weight=ft.FontWeight.BOLD),
                            ], spacing=2),
                            padding=12, border_radius=8, bgcolor=ft.Colors.SURFACE_VARIANT, expand=True,
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("20일 이평", size=12, color=ft.Colors.GREY_600),
                                ft.Text(ma20_str, size=18, weight=ft.FontWeight.BOLD),
                            ], spacing=2),
                            padding=12, border_radius=8, bgcolor=ft.Colors.SURFACE_VARIANT, expand=True,
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("60일 이평", size=12, color=ft.Colors.GREY_600),
                                ft.Text(ma60_str, size=18, weight=ft.FontWeight.BOLD),
                            ], spacing=2),
                            padding=12, border_radius=8, bgcolor=ft.Colors.SURFACE_VARIANT, expand=True,
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("RSI(14)", size=12, color=ft.Colors.GREY_600),
                                ft.Text(f"{rsi_val:.1f}", size=18, weight=ft.FontWeight.BOLD, color=rsi_color),
                            ], spacing=2),
                            padding=12, border_radius=8, bgcolor=ft.Colors.SURFACE_VARIANT, expand=True,
                        ),
                    ], spacing=12),
                    ft.Container(height=12),
                    ft.Container(
                        content=ft.Text(f"진단: {analysis['opinion']}", size=14, weight=ft.FontWeight.W_600, color=opinion_color),
                        padding=8, border_radius=8, bgcolor=ft.Colors.SURFACE_VARIANT,
                    ),
                    ft.Container(height=4),
                    ft.Column([ft.Text(f"• {d}", size=12) for d in analysis["details"]], spacing=2),
                    ft.Container(height=20),
                    ft.Text("📉 기술적 지표", size=16, weight=ft.FontWeight.W_600),
                    ft.Container(height=8),
                    ft.Tabs(
                        selected_index=0,
                        tabs=[
                            ft.Tab(
                                text="주가 + 거래량 + RSI",
                                content=ft.Container(
                                    content=ft.Html(build_chart1_html(df), expand=True),
                                    height=520,
                                ),
                            ),
                            ft.Tab(
                                text="MACD",
                                content=ft.Container(
                                    content=ft.Html(build_chart2_html(df), expand=True),
                                    height=420,
                                ),
                            ),
                            ft.Tab(
                                text="볼린저 밴드",
                                content=ft.Container(
                                    content=ft.Html(build_chart3_html(df), expand=True),
                                    height=420,
                                ),
                            ),
                        ],
                        expand=1,
                    ),
                ],
                spacing=8,
            )
            main_column.controls.clear()
            main_column.controls.append(content)
            page.update()
        except Exception as e:
            page.show_snack_bar(ft.SnackBar(content=ft.Text(f"데이터 로드 오류: {e}"), open=True))
            page.update()

    def on_analyze(e):
        t = (ticker_input.value or "AAPL").strip().upper()
        p = int(period_slider.value)
        page.title = f"{t} - 주식 분석 대시보드"
        main_column.controls.clear()
        main_column.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.ProgressRing(width=48, height=48),
                    ft.Text(f"{t} 데이터 로딩 중...", size=14, color=ft.Colors.GREY_600),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=16, expand=True),
                alignment=ft.alignment.center,
                expand=True,
            )
        )
        page.update()
        load_data_and_display(t, p)

    # 사이드바
    ticker_input = ft.TextField(
        label="종목 티커 입력",
        value="AAPL",
        hint_text="예: AAPL, TSLA, MSFT, 005930.KS",
        width=220,
    )
    period_slider = ft.Slider(
        min=90, max=365, value=365, divisions=27,
        label="분석 기간 (일)",
    )
    analyze_btn = ft.ElevatedButton("분석 시작", icon=ft.Icons.PLAY_ARROW, on_click=on_analyze, width=220)

    sidebar = ft.Container(
        content=ft.Column([
            ft.Text("📌 종목 선택", size=16, weight=ft.FontWeight.BOLD),
            ft.Container(height=12),
            ticker_input,
            ft.Container(height=8),
            period_slider,
            ft.Container(height=16),
            analyze_btn,
            ft.Container(height=24),
            ft.Divider(),
            ft.Text("사용법", size=14, weight=ft.FontWeight.W_600),
            ft.Text("1. 종목 티커 입력", size=12),
            ft.Text("2. 분석 시작 클릭", size=12),
            ft.Text("3. 차트·지표 확인", size=12),
        ], expand=True, scroll=ft.ScrollMode.AUTO),
        width=260,
        padding=16,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.border.only(right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
    )

    # 메인 영역 초기 상태
    main_column.controls.append(
        ft.Container(
            content=ft.Column([
                ft.Text("종목을 입력하고 '분석 시작'을 클릭하세요.", size=14, color=ft.Colors.GREY_600),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, expand=True),
            alignment=ft.alignment.center,
            expand=True,
        )
    )

    page.add(
        ft.Row([
            sidebar,
            ft.Container(
                content=main_column,
                expand=True,
                padding=16,
            ),
        ], expand=True),
    )

    # 초기 로드
    load_data_and_display("AAPL", 365)


if __name__ == "__main__":
    ft.app(target=main)

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from chinese_calendar import is_workday, is_holiday
import pywencai


def safe_float(value):
    """Safely convert a value to float, returning 0 if conversion fails"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
def get_previous_trading_day(date):
    previous_date = date - timedelta(days=1)
    while not is_workday(previous_date) or is_holiday(previous_date):
        previous_date -= timedelta(days=1)
    return previous_date
def analyze_limit_up_reason(df, date):
    # 提取连续涨停天数列和涨停原因类别列
    reason_col = f'涨停原因类别[{date.strftime("%Y%m%d")}]'
    # 确保涨停原因类别列存在
    if reason_col not in df.columns:
        df[reason_col] = '未知'
    # 按'+'分割涨停原因并展开
    reasons = df[reason_col].str.split('+').explode().reset_index(drop=True)
    concept_counts = reasons.value_counts().reset_index()
    # 过滤掉出现次数小于2的项
    concept_counts.columns = ['概念', '出现次数']
    max_count = concept_counts['出现次数'].mode().iloc[0] + 1
    concept_counts = concept_counts[concept_counts['出现次数'] > max_count]
    return concept_counts


# Page config
st.set_page_config(page_title="涨停复盘", page_icon="📈", layout="wide")

# Helper functions
@st.cache_data(ttl=300)
def get_market_data(date):
    """获取指定日期的涨停数据"""
    try:
        limit_up_query = f"{date}涨停，非ST，上市时间大于1个月，炸板次数，连续涨停天数排序"
        limit_up_df = pywencai.get(query=limit_up_query, sort_key='连续涨停天数', sort_order='desc', loop=True)
        return limit_up_df
    except Exception as e:
        st.error(f"获取数据失败: {e}")
        return None

def calculate_metrics(limit_up_df, date):
    """计算市场指标"""
    if limit_up_df is None:
        return {}
    date_str = date.strftime("%Y%m%d")
    try:
        metrics = {
            "涨停数量": len(limit_up_df),
        "连板率": round(
            len(limit_up_df[limit_up_df[f'连续涨停天数[{date_str}]'].apply(safe_float) > 1]) / len(limit_up_df) * 100,
                2) if len(limit_up_df) > 0 else 0,
        }
        return metrics
    except Exception as e:
        st.error("该日期无数据")
        return None
    

# Main app
def app():
    st.title("涨停复盘")

    # Date selection
    beijing_time = ZoneInfo('Asia/Shanghai')
    today = datetime.now(beijing_time).date()
    default_date = today
    selected_date = st.date_input(
        label="选择日期",
        value=default_date,
        max_value=today,
        label_visibility="hidden"
    )

    if selected_date:
        # 获取数据
        previous_date = get_previous_trading_day(selected_date)
        limit_up_df = get_market_data(selected_date)
        previous_df = get_market_data(previous_date)

        if limit_up_df is not None:
            # 计算指标
            metrics = calculate_metrics(limit_up_df, selected_date)
            if metrics is None:
                return
            chart_data = analyze_limit_up_reason(limit_up_df, selected_date)
            if not chart_data.empty:
                st.markdown("---")
                # 显示主要指标
                selected_total = len(limit_up_df)
                previous_total = len(previous_df)
                change = selected_total - previous_total

                # 创建两列布局：左侧饼图，右侧指标
                left_col, right_col = st.columns([1, 1])
                
                # 左侧列显示饼图
                with left_col:
                    fig = {
                        "data": [{
                            "values": chart_data['出现次数'].tolist(),
                            "labels": chart_data['概念'].tolist(),
                            "type": "pie",
                            "textinfo": "label+percent",
                            "textposition": "inside",
                            "automargin": True,
                            "textfont": {
                                "size": 13,
                                "weight": "bold"
                            },
                            "marker": {
                                "colors": None,
                                "line": {"color": "white", "width": 2}
                            },
                        }],
                        "layout": {
                            "height": 300,
                            "showlegend": False,
                            "margin": {"t": 0, "l": 0, "r": 0, "b": 0},
                            "paper_bgcolor": "rgba(0,0,0,0)",
                            "plot_bgcolor": "rgba(0,0,0,0)",
                        }
                    }
                    st.plotly_chart(fig, use_container_width=True)
                
                # 右侧列分为上下两行显示指标，添加垂直间距实现居中效果
                with right_col:
                    # 添加上方空白
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    
                    # 上行显示两个指标
                    col2, col3 = st.columns(2)
                    with col2:
                        st.metric("今日涨停数量", metrics["涨停数量"])
                    with col3:
                        st.metric("前一交易日涨停数", previous_total)
                    
                    # 添加行间距
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # 下行显示两个指标
                    col4, col5 = st.columns(2)
                    with col4:
                        st.metric("变化", change, f"{change:+d}", delta_color="inverse")
                    with col5:
                        st.metric("连板率", f"{metrics['连板率']}%")

            # 涨停股票列表
            st.markdown("---")
            date_str = selected_date.strftime("%Y%m%d")
            
            # 处理数据并按连板天数分组
            df_processed = limit_up_df[['股票代码','股票简称','最新价',f'最终涨停时间[{date_str}]',
                                      f'涨停开板次数[{date_str}]', f'连续涨停天数[{date_str}]', 
                                      f'涨停类型[{date_str}]',f'涨停原因类别[{date_str}]']].rename(
                columns={
                    '股票代码': '代码',
                    '股票简称': '名称',
                    '最新价': '现价',
                    f'最终涨停时间[{date_str}]': '涨停时间',
                    f'涨停开板次数[{date_str}]': '炸板次数',
                    f'连续涨停天数[{date_str}]': '连板数',
                    f'涨停类型[{date_str}]': '涨停类型',
                    f'涨停原因类别[{date_str}]': '涨停原因'
                }
            )
            
            # 按连板数分组并排序
            grouped = df_processed.groupby('连板数', sort=True)
            
            # 按组显示数据
            for days, group in sorted(grouped, key=lambda x: float(x[0]) if isinstance(x[0], str) else x[0], reverse=True):
                # 根据连板天数显示不同的文本
                display_text = "首板" if days == 1 else f"{days}连板"
                group_count = len(group)
                display_count = f" ({group_count})" if group_count >= 10 else ""
                st.markdown(f"### {display_text}{display_count}")
                # 在显示之前删除'连板数'列
                display_group = group.drop(columns=['连板数'])
                st.dataframe(
                    display_group,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "涨停原因": st.column_config.TextColumn(
                            "涨停原因",
                            width="large",
                            help="涨停原因类别"
                        )
                    }
                )

            # 下载数据按钮
            # col1, col2 = st.columns(2)
            # with col1:
            #     csv_limit_up = limit_up_df.to_csv(index=False)
            #     st.download_button(
            #         label="下载涨停股票数据",
            #         data=csv_limit_up,
            #         file_name=f"limit_up_stocks_{selected_date}.csv",
            #         mime="text/csv",
            #     )
        else:
            st.warning(f"未找到 {selected_date} 的市场数据")

if __name__ =="__main__":
    app()

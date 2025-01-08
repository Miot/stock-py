import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pywencai


def safe_float(value):
    """Safely convert a value to float, returning 0 if conversion fails"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


# Page config
st.set_page_config(page_title="涨停复盘", page_icon="📈", layout="wide")


# Helper functions
@st.cache_data(ttl=300)
def get_market_data(date):
    """获取指定日期的涨停数据"""
    try:
        limit_up_query = f"{date}涨停，非ST，上市时间大于1个月，炸板次数，连续涨停天数排序"
        limit_up_df = pywencai.get(query=limit_up_query, sort_key='连续涨停天数', sort_order='desc', loop=True)
        return limit_up_df, None
        # , limit_down_df
    except Exception as e:
        st.error(f"获取数据失败: {e}")
        return None, None


def calculate_metrics(limit_up_df, limit_down_df, date):
    """计算市场指标"""
    # if limit_up_df is None or limit_down_df is None:
    if limit_up_df is None:
        return {}

    date_str = date.strftime("%Y%m%d")
    try:
        metrics = {
            "涨停数量": len(limit_up_df),
            # "跌停数量": len(limit_down_df),
        # "涨停比": f"{len(limit_up_df)}:{len(limit_down_df)}",
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
    today = datetime.now().date()
    default_date = today - timedelta(days=1)  # 默认显示昨天的数据
    selected_date = st.date_input(
        label="选择日期",
        value=default_date,
        max_value=today,
        label_visibility="hidden"
    )

    if selected_date:
        # 获取数据
        limit_up_df, limit_down_df = get_market_data(selected_date)

        if limit_up_df is not None:
            # 计算指标
            metrics = calculate_metrics(limit_up_df, limit_down_df, selected_date)
            if metrics is None:
                return
            # 显示主要指标
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("涨停数量", metrics["涨停数量"])
            with col2:
                st.metric("连板率", f"{metrics['连板率']}%")
            

            # 涨停股票列表
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
                    f'涨停开板次数[{date_str}]': '炸板数',
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
                st.markdown(f"### {display_text} ({len(group)})")
                st.dataframe(
                    group,
                    hide_index=True,
                    use_container_width=True
                )

            # 跌停股票列表
            # st.subheader("今日跌停股票")
            # st.dataframe(
            #     limit_down_df[
            #         ['股票代码','股票简称','最新价','最新涨跌幅', f'成交额[{date_str}]']],
            #     hide_index=True
            # )

            # 下载数据按钮
            col1, col2 = st.columns(2)
            with col1:
                csv_limit_up = limit_up_df.to_csv(index=False)
                st.download_button(
                    label="下载涨停股票数据",
                    data=csv_limit_up,
                    file_name=f"limit_up_stocks_{selected_date}.csv",
                    mime="text/csv",
                )
            # with col2:
            #     csv_limit_down = limit_down_df.to_csv(index=False)
            #     st.download_button(
            #         label="下载跌停股票数据",
            #         data=csv_limit_down,
            #         file_name=f"limit_down_stocks_{selected_date}.csv",
            #         mime="text/csv",
            #     )

        else:
            st.warning(f"未找到 {selected_date} 的市场数据")


if __name__ =="__main__":
    app()
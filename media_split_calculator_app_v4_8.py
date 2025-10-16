
import streamlit as st
import pandas as pd
import numpy as np

def allocate_budget(df, total_budget=240, alpha=1.6, beta=1.0, other_share=10.0):
    df = df.copy()

    # Заполняем пустые значения
    df['commercial priority'] = pd.to_numeric(df['commercial priority'], errors='coerce').fillna(0.25)
    df['category priority'] = pd.to_numeric(df['category priority'], errors='coerce').fillna(5)
    df['placement priority'] = pd.to_numeric(df['placement priority'], errors='coerce').fillna(5)
    df['minimum spend'] = pd.to_numeric(df['minimum spend'], errors='coerce').fillna(0)
    df['maximum spend'] = pd.to_numeric(df['maximum spend'], errors='coerce').fillna(1e9)

    other_mask = df['category'].astype(str).str.lower() == 'other'
    other_budget = total_budget * (other_share / 100)
    main_budget = total_budget - other_budget

    df_main = df[(df['category priority'] <= 3) & (df['placement priority'] <= 2) & (~other_mask)].copy()
    if df_main.empty:
        st.error('Нет площадок, удовлетворяющих условиям фильтрации.')
        return df, pd.DataFrame()

    df_main['W'] = (df_main['commercial priority'] ** alpha) * ((1 / df_main['placement priority']) ** beta)
    df_main['recommended budget'] = df_main['minimum spend']
    remaining = main_budget - df_main['recommended budget'].sum()

    if remaining < 0:
        st.error('Минимальные пороги превышают основной бюджет.')
        return df, pd.DataFrame()

    for _ in range(100):
        if remaining <= 1e-6:
            break
        df_main['available'] = df_main['maximum spend'] - df_main['recommended budget']
        eligible = df_main['available'] > 0
        total_w = df_main.loc[eligible, 'W'].sum()
        if total_w == 0:
            break
        increments = (df_main.loc[eligible, 'W'] / total_w) * remaining
        increments = np.minimum(increments, df_main.loc[eligible, 'available'])
        df_main.loc[eligible, 'recommended budget'] += increments
        remaining = main_budget - df_main['recommended budget'].sum()

    df_main['recommended budget'] = (df_main['recommended budget'] / df_main['recommended budget'].sum()) * main_budget

    df_other = df[other_mask].copy()
    if not df_other.empty:
        df_other['recommended budget'] = other_budget / len(df_other)

    df_rest = df[~df.index.isin(df_main.index) & ~df.index.isin(df_other.index)].copy()
    df_rest['recommended budget'] = np.nan

    df_final = pd.concat([df_main, df_other, df_rest], ignore_index=True)

    summary = df_final.groupby('category', as_index=False)['recommended budget'].sum()
    summary['share_%'] = (summary['recommended budget'] / total_budget) * 100

    return df_final, summary

st.set_page_config(page_title='Media Split Calculator v4.8', layout='wide')
st.title('📊 Media Split Calculator — Fixed Bounds (v4.8)')

FILE_PATH = 'калькулятор.xlsx'
df = pd.read_excel(FILE_PATH)

st.subheader('⚙️ Calculation Parameters')
col1, col2, col3, col4 = st.columns(4)
with col1:
    total_budget = st.number_input('Total Budget (mln ₽)', min_value=10.0, value=240.0, step=10.0)
with col2:
    alpha = st.slider('α — Agency Profit Weight', 1.0, 2.5, 1.6, 0.1)
with col3:
    beta = st.slider('β — Client Priority Weight', 0.5, 2.0, 1.0, 0.1)
with col4:
    other_share = st.slider('Free Float Share (%)', 0.0, 30.0, 10.0, 1.0)

st.markdown('---')

if 'mode' not in st.session_state:
    st.session_state.mode = 'default'

if st.session_state.mode == 'default':
    colA, colB = st.columns(2)
    with colA:
        if st.button('🧮 Calculate'):
            st.session_state.mode = 'calculate'
    with colB:
        if st.button('✏️ Edit Input Data'):
            st.session_state.mode = 'edit'

elif st.session_state.mode == 'edit':
    st.subheader('✏️ Edit Input Data')
    edited_df = st.data_editor(df, num_rows='dynamic', use_container_width=True, key='edit_table')
    if st.button('⬆️ Back to Main Menu'):
        st.session_state.mode = 'default'
        st.session_state.edited_df = edited_df

elif st.session_state.mode == 'calculate':
    df_to_use = st.session_state.get('edited_df', df)
    df_result, summary = allocate_budget(df_to_use, total_budget, alpha, beta, other_share)

    total_sum = df_result['recommended budget'].sum()
    st.success(f'✅ Бюджет успешно распределён: {total_sum:.2f} млн ₽ (100%)')

    st.subheader('📈 Recommended Split by Placement')
    visible_cols = [c for c in ['placement', 'category', 'recommended budget'] if c in df_result.columns]
    st.dataframe(df_result[visible_cols].round(2), use_container_width=True)

    st.subheader('📊 Summary by Category')
    st.dataframe(summary.round(2), use_container_width=True)

    csv = df_result.to_csv(index=False).encode('utf-8')
    st.download_button('💾 Download Result (CSV)', data=csv, file_name='media_split_result_v4_8.csv', mime='text/csv')

    if st.button('⬆️ Back to Edit Mode'):
        st.session_state.mode = 'edit'

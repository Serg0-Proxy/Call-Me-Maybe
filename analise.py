from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from scipy import stats

BASE = Path(__file__).parent
DATA_DIR = BASE / 'data'
OUT_DIR = BASE / 'resultados'

MIN_RECEBIDAS = 10  # mínimo de chamadas recebidas pra entrar no ranking


def formatar_p(p):
    # p-valor muito pequeno em notação científica
    return f'{p:.2e}' if p < 0.0001 else f'{p:.4f}'


def salvar_grafico(fig, nome):
    fig.tight_layout()
    fig.savefig(OUT_DIR / nome, dpi=120)
    plt.close(fig)


def carregar_dados():
    clients = pd.read_csv(DATA_DIR / 'telecom_clients.csv')
    data = pd.read_csv(DATA_DIR / 'telecom_dataset_new.csv')
    print('clientes:', clients.shape, '| chamadas:', data.shape)
    return clients, data


def limpar_dados(clients, data):
    # cada linha é um agregado diário, linha igual em tudo não acrescenta nada
    print('linhas duplicadas removidas:', data.duplicated().sum())
    data = data.drop_duplicates().copy()

    # a data já vem em ISO, dá pra ordenar como texto
    dias = data['date'].str[:10]
    print('período:', dias.min(), 'a', dias.max())

    # sem operator_id (chamadas que ninguém atendeu) ou sem internal fica
    # fora da análise por operador
    sem_operador = data['operator_id'].isna().sum()
    print('linhas sem operator_id:', sem_operador,
          '| sem internal:', data['internal'].isna().sum())
    data_op = data.dropna(subset=['operator_id', 'internal']).copy()
    data_op['operator_id'] = data_op['operator_id'].astype(int)
    data_op = data_op.merge(clients, on='user_id', how='left')

    # durações acima do percentil 99 são limitadas no teto (clip)
    for col in ['call_duration', 'total_call_duration']:
        data_op[col] = data_op[col].clip(upper=data_op[col].quantile(0.99))

    data_op['wait_time'] = (
        data_op['total_call_duration'] - data_op['call_duration']).clip(lower=0)
    print('linhas usadas na análise por operador:', data_op.shape[0])
    return data_op


def metricas_por_operador(data_op):
    # chamadas recebidas
    recebidas = data_op[data_op['direction'] == 'in']
    por_op = recebidas.groupby('operator_id').agg(
        total_received=('is_missed_call', 'size'),
        missed_received=('is_missed_call', 'sum'),
        avg_wait_time=('wait_time', 'mean')
    ).reset_index()
    por_op['missed_rate'] = por_op['missed_received'] / \
        por_op['total_received'] * 100

    # chamadas ativas (saída, externas)
    saida = data_op[(data_op['direction'] == 'out') &
                    (~data_op['internal'].astype(bool))]
    ativas = saida.groupby('operator_id')[
        'calls_count'].sum().reset_index(name='active_calls')

    planos = data_op[['operator_id', 'tariff_plan']].drop_duplicates()

    ops = por_op.merge(ativas, on='operator_id', how='outer').merge(
        planos, on='operator_id', how='left')
    ops['active_calls'] = ops['active_calls'].fillna(0)
    ops['total_received'] = ops['total_received'].fillna(0)
    return ops


def hipotese_1(ops_valid):
    # existe um grupo de operadores com taxa de perdidas bem acima da média?
    q1, q3 = ops_valid['missed_rate'].quantile([0.25, 0.75])
    limite = q3 + 1.5 * (q3 - q1)
    outliers = ops_valid[ops_valid['missed_rate'] > limite]
    print(
        f'H1: {outliers.shape[0]} de {ops_valid.shape[0]} operadores acima de {limite:.2f}%')

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(ops_valid['missed_rate'], bins=30,
            color='#1B7A8C', edgecolor='white')
    ax.axvline(limite, color='#F2A93B', linestyle='--',
               label=f'limite IQR, {limite:.2f}%')
    ax.set_xlabel('taxa de chamadas perdidas (%)')
    ax.set_ylabel('número de operadores')
    ax.set_title('distribuição da taxa de chamadas perdidas por operador')
    ax.legend()
    salvar_grafico(fig, 'h1_histograma.png')

    return [{'hipotese': 'H1', 'teste': 'IQR',
             'resultado': f'{outliers.shape[0]} de {ops_valid.shape[0]} acima de {limite:.2f}%', 'p_valor': ''}]


def hipotese_2(ops_valid):
    # espera longa anda junto com mais chamadas perdidas?
    corr, p_corr = stats.spearmanr(
        ops_valid['avg_wait_time'], ops_valid['missed_rate'])

    p75 = ops_valid['avg_wait_time'].quantile(0.75)
    espera_alta = ops_valid[ops_valid['avg_wait_time'] > p75]['missed_rate']
    espera_baixa = ops_valid[ops_valid['avg_wait_time'] <= p75]['missed_rate']
    _, p_mw = stats.mannwhitneyu(
        espera_alta, espera_baixa, alternative='greater')

    print(f'H2: spearman {corr:.3f} (p = {formatar_p(p_corr)})')
    print(
        f'    perdidas, espera alta: {espera_alta.mean():.2f}% | espera baixa: {espera_baixa.mean():.2f}% (mann-whitney p = {formatar_p(p_mw)})')

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.scatter(ops_valid['avg_wait_time'],
               ops_valid['missed_rate'], alpha=0.5, color='#1B7A8C')
    ax.set_xlabel('tempo médio de espera (segundos)')
    ax.set_ylabel('taxa de chamadas perdidas (%)')
    ax.set_title('tempo de espera por taxa de chamadas perdidas, por operador')
    salvar_grafico(fig, 'h2_dispersao.png')

    return [{'hipotese': 'H2', 'teste': 'Spearman', 'resultado': f'correlação {corr:.2f}', 'p_valor': formatar_p(p_corr)},
            {'hipotese': 'H2', 'teste': 'Mann-Whitney',
             'resultado': f'{espera_alta.mean():.2f}% (espera alta) vs {espera_baixa.mean():.2f}%', 'p_valor': formatar_p(p_mw)}]


def hipotese_3(ops_valid):
    # poucas chamadas ativas também indica pior desempenho?
    saida = ops_valid[ops_valid['active_calls'] > 0]
    mediana = saida['active_calls'].median()
    baixo = saida[saida['active_calls'] <= mediana]['missed_rate']
    alto = saida[saida['active_calls'] > mediana]['missed_rate']
    _, p = stats.mannwhitneyu(baixo, alto, alternative='greater')

    print(
        f'H3: {saida.shape[0]} operadores de saída | mediana de chamadas ativas: {mediana}')
    print(
        f'    perdidas, baixo volume: {baixo.mean():.2f}% | alto volume: {alto.mean():.2f}% (p = {formatar_p(p)})')

    return [{'hipotese': 'H3', 'teste': 'Mann-Whitney',
             'resultado': f'{baixo.mean():.2f}% (baixo volume) vs {alto.mean():.2f}%', 'p_valor': formatar_p(p)}]


def hipotese_4(ops_valid):
    # a taxa de perdidas muda conforme o plano tarifário?
    planos = ['A', 'B', 'C']
    grupos = [ops_valid[ops_valid['tariff_plan'] == p]['missed_rate'].dropna()
              for p in planos]
    h, p = stats.kruskal(*grupos)
    medias = ops_valid.groupby('tariff_plan')['missed_rate'].mean()

    print(f'H4: kruskal-wallis H = {h:.3f} (p = {formatar_p(p)})')
    print(medias.round(2).to_string())

    fig, ax = plt.subplots(figsize=(8, 4))
    ops_valid.boxplot(column='missed_rate', by='tariff_plan', ax=ax)
    ax.set_xlabel('plano tarifário')
    ax.set_ylabel('taxa de chamadas perdidas (%)')
    ax.set_title('taxa de chamadas perdidas por plano tarifário')
    fig.suptitle('')
    salvar_grafico(fig, 'h4_boxplot.png')

    return [{'hipotese': 'H4', 'teste': 'Kruskal-Wallis',
             'resultado': ' | '.join(f'{k}: {v:.2f}%' for k, v in medias.items()), 'p_valor': formatar_p(p)}]


def indice_ineficiencia(ops_valid):
    # percentil de cada operador nos três critérios (mesma escala)
    ops_valid = ops_valid.copy()
    ops_valid['rank_missed'] = ops_valid['missed_rate'].rank(pct=True)
    ops_valid['rank_wait'] = ops_valid['avg_wait_time'].rank(pct=True)
    ops_valid['rank_active'] = ops_valid['active_calls'].rank(pct=True)
    ops_valid['indice_ineficiencia'] = ops_valid['rank_missed'] + \
        ops_valid['rank_wait'] - ops_valid['rank_active']

    # top 10% do índice entra como prioridade alta
    limite = ops_valid['indice_ineficiencia'].quantile(0.90)
    prioridade = ops_valid[ops_valid['indice_ineficiencia'] >= limite].sort_values(
        'indice_ineficiencia', ascending=False)
    prioridade = prioridade[['operator_id', 'missed_rate',
                             'avg_wait_time', 'active_calls', 'indice_ineficiencia']]

    print(
        f'\nprioridade alta: {prioridade.shape[0]} de {ops_valid.shape[0]} operadores (índice >= {limite:.2f})')
    print(prioridade.head(5).round(2).to_string(index=False))
    prioridade.to_csv(OUT_DIR / 'prioridade_alta.csv', index=False)


def operadores_fora_do_ranking(ops):
    # menos de 10 chamadas recebidas, inclui quem só faz chamada de saída
    fora = ops[ops['total_received'] < MIN_RECEBIDAS]
    so_saida = fora[fora['active_calls'] > 0]
    sem_atividade = fora[fora['active_calls'] == 0]

    mediana = ops[ops['active_calls'] > 0]['active_calls'].median()
    baixa_prod = so_saida[so_saida['active_calls']
                          <= mediana].sort_values('active_calls')

    print(f'\nfora do ranking: {fora.shape[0]} operadores')
    print(
        f'  com chamadas ativas: {so_saida.shape[0]} (baixa produtividade: {baixa_prod.shape[0]})')
    print(f'  sem atividade relevante: {sem_atividade.shape[0]}')
    baixa_prod[['operator_id', 'active_calls']].to_csv(
        OUT_DIR / 'baixa_produtividade.csv', index=False)


def main():
    OUT_DIR.mkdir(exist_ok=True)

    clients, data = carregar_dados()
    data_op = limpar_dados(clients, data)

    ops = metricas_por_operador(data_op)
    ops_valid = ops[ops['total_received'] >= MIN_RECEBIDAS].copy()
    print(
        f'operadores: {ops.shape[0]} | válidos (>= {MIN_RECEBIDAS} chamadas recebidas): {ops_valid.shape[0]}\n')

    resumo = []
    for hipotese in (hipotese_1, hipotese_2, hipotese_3, hipotese_4):
        resumo += hipotese(ops_valid)

    indice_ineficiencia(ops_valid)
    operadores_fora_do_ranking(ops)

    resumo = pd.DataFrame(resumo)
    resumo.to_csv(OUT_DIR / 'resumo_hipoteses.csv', index=False)
    print('\n', resumo.to_string(index=False))


if __name__ == '__main__':
    main()

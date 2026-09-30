# CallMeMaybe - Identificação de Operadores Ineficientes

Projeto final de análise de dados. A CallMeMaybe é um serviço de telefonia virtual, e o objetivo é ajudar os supervisores a identificar operadores ineficientes: os que perdem muitas chamadas recebidas, deixam o cliente esperando demais ou fazem poucas chamadas ativas (de saída).

[![Ver no Tableau Public](https://img.shields.io/badge/Ver%20gr%C3%A1ficos-Tableau%20Public-1F77B4?style=for-the-badge&logo=tableau&logoColor=white)](https://public.tableau.com/app/profile/sergio.christofoli.pereira/viz/CallMeMaybeOperadoresIneficientes/CallMeMaybeOperadoresIneficientes)

## Dados

Dois arquivos na pasta `data/`:

- `telecom_clients.csv`: 732 clientes com plano tarifário (A, B ou C) e data de início
- `telecom_dataset_new.csv`: 53.902 registros de chamadas (agregados diários por operador), de agosto a novembro de 2019, com 1.092 operadores distintos

Antes da análise, os dados são tratados:

- remoção das linhas totalmente duplicadas (4.900, cerca de 9%)
- chamadas sem `operator_id` (quase todas nunca foram atendidas) ficam de fora da análise por operador
- durações acima do percentil 99 são limitadas nesse teto
- só entram no ranking os operadores com 10 chamadas recebidas ou mais

## Hipóteses

1. Existe um grupo de operadores com taxa de chamadas perdidas bem acima da média
2. Espera longa nas chamadas recebidas anda junto com mais chamadas perdidas
3. Baixo volume de chamadas ativas também indica pior desempenho geral
4. A taxa de chamadas perdidas muda conforme o plano tarifário do cliente

## Estrutura do projeto

```
callmemaybe/
├── data/                  # arquivos csv de clientes e chamadas
├── docs/
│   └── callmemaybe_apresentacao.pdf
├── resultados/            # gráficos e listas geradas pelo script
├── analise.py             # análise completa
├── requirements.txt
└── README.md
```

## Tecnologias

- Python 3
- pandas
- SciPy (Spearman, Mann-Whitney e Kruskal-Wallis)
- Matplotlib
- Tableau

## Como executar

1. Clone o repositório:
   ```powershell
   git clone https://github.com/Serg0-Proxy/CallMeMaybe.git
   cd CallMeMaybe
   ```

2. Crie e ative um ambiente virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Instale as dependências:
   ```powershell
   pip install -r requirements.txt
   ```

4. Execute a análise:
   ```powershell
   python analise.py
   ```

Os resultados são mostrados no terminal, e os gráficos e listas ficam na pasta `resultados/`.

## Resultados

| Hipótese | Resultado | Situação |
|---|---|---|
| 1 | 24 de 363 operadores (7%) com taxa de perdidas acima de 18,45% | Confirmada |
| 2 | Espera alta: 10,92% de perdidas, contra 2,92% na espera baixa (Spearman 0,41) | Confirmada |
| 3 | Baixo volume: 5,32% de perdidas, contra 5,73% no alto volume (p = 0,93) | Não confirmada |
| 4 | Plano A: 7,37%, plano B: 4,57%, plano C: 3,38% (Kruskal-Wallis, p = 0,0068) | Confirmada |

**Índice de ineficiência:** combina o percentil de cada operador em chamadas perdidas e tempo de espera (pesam a favor da ineficiência) e em chamadas ativas (pesa contra). Com o corte no percentil 90, 37 operadores ficam com prioridade alta (`resultados/prioridade_alta.csv`).

**Operadores fora do ranking:** dos 1.092 operadores, 30 só fizeram chamadas internas e ficam fora de qualquer métrica. Dos 1.062 restantes, 699 têm menos de 10 chamadas recebidas. Entre eles, 327 fazem só chamadas de saída, com volume abaixo da mediana, e formam uma segunda lista para o supervisor (`resultados/baixa_produtividade.csv`).

## Apresentação

O resumo do projeto está em [`docs/callmemaybe_apresentacao.pdf`](docs/callmemaybe_apresentacao.pdf).

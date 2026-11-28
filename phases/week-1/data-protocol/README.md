# Settimana 1 · Dati e protocollo (persona A)

S&P 500 point-in-time (2006-2025) e 12 ETF, costruito per testare la stat arb PCA di Avellaneda-Lee senza
survivorship bias né look-ahead. Il codice è in [`statarb/`](../../../statarb), le scelte di metodo e i limiti in
[`docs/data_choices.md`](../../../docs/data_choices.md), i controlli end-to-end in
[`notebooks/01_data_qa.ipynb`](../../../notebooks/01_data_qa.ipynb). PR #2.

## Stato rispetto ai task della settimana

| # | Task | Stato |
|---|---|---|
| 1 | Accesso WRDS / CRSP | Non usato: scelti Tiingo e fonti gratuite (piano B) |
| 2 | Piano B: S&P 500 storico e titoli usciti mancanti | Fatto, e il buco è stato riempito: copertura 99,97% |
| 3 | Decisione sui dati per iscritto | Fatto, in `docs/data_choices.md` |
| 4 | Download di SPY e degli ETF di settore | Fatto, da Tiingo |
| 5 | Holdout 2023-2025 sigillato | Fatto: [`docs/protocol.md`](../../../docs/protocol.md), tag `holdout-sealed` |
| 6 | Monte Carlo del massimo di N normali contro la formula di Gumbel | Fatto: [`notebooks/02_gumbel_check.ipynb`](../../../notebooks/02_gumbel_check.ipynb) |

## Perché servono dati "onesti"

- **Survivorship bias**: l'universo è ricostruito giorno per giorno con i titoli che erano davvero nell'indice
  quel giorno. Sono circa 950 società nel periodo, circa 500 al giorno.
- **Look-ahead**: ogni stima (settore, spread) usa finestre che finiscono a t-1.

## Fonti

| Fonte | Contenuto | Uso |
|---|---|---|
| fja05680/sp500 (GitHub, MIT) | Composizione storica dell'indice | Universo point-in-time |
| Tiingo (piano Power) | Prezzi giornalieri, dividendi e split di titoli ed ETF | Fonte principale, circa 92% dei dati |
| Quandl WIKI (mirror Kaggle) | Prezzi giornalieri fino al 2018 | Controllo incrociato e riempimento |
| Johnbrick123/sp500-data | Titoli usciti dall'indice 2006-2012, in gran parte da CRSP | Riempie l'ultimo buco |
| FRED | T-bill a 3 mesi (DTB3) e VIX (VIXCLS) | Risk-free e regime di volatilità |
| Kenneth French | Fattori FF5 e momentum giornalieri | Esposizione a fattori noti |

Gli ETF sono gli 11 settoriali SPDR più SPY. L'universo sono i membri dell'S&P 500, senza un filtro separato sulla
market cap.

## Pulizia

- **Ticker riciclati o rinominati**: trovati cercando correlazioni basse tra i rendimenti delle diverse fonti e
  corretti a mano in [`reference/ticker_overrides.csv`](../../../reference/ticker_overrides.csv), circa 70 casi.
- **Aziende fuse per errore** nella lista dell'indice (AGN, CB, JCI): separate in
  [`reference/membership_fixes.csv`](../../../reference/membership_fixes.csv).
- **Una fonte per serie**: i rendimenti si calcolano dentro una sola fonte e un solo simbolo, senza incollare prezzi
  di fonti diverse.
- **Delisting veri**: per SVB e Signature Bank (marzo 2023) si usa il prezzo OTC reale, circa -99,6% e -99,8%
  ([`reference/delistings.csv`](../../../reference/delistings.csv)).

## Variabili costruite

- **Settore**: l'ETF settoriale con l'R² massimo sugli ultimi 252 giorni (finestra fino a t-1), al posto del GICS
  storico.
- **Spread**: stima di Abdi-Ranaldo (2017) su 21 giorni di barre giornaliere. La mediana è circa 23 bps, contro i
  2-10 bps quotati: è una stima conservativa, e nel report faremo un'analisi di sensibilità ai costi.

## Controlli di qualità

| Controllo | Risultato |
|---|---|
| Copertura dei giorni-titolo dell'indice | 99,97% |
| Titoli per giorno (min / mediana) | 488 / 503 |
| Salti anomali nei giorni di split | 0 |
| Ticker in disaccordo tra fonti | 0 |
| Correlazione SPY contro titoli dell'indice (anno peggiore) | 0,82 |

Ogni file grezzo è registrato con data, URL e sha256 in `data/raw/manifest.csv`. Il comando
`uv run python -m statarb` ricostruisce tutto.

## Holdout sigillato

Il periodo 2023-2025 non si guarda fino alla milestone M4: niente grafici, statistiche o backtest. Lo sviluppo usa
solo il 2006-2022. Le regole e l'apertura a M4 sono in [`docs/protocol.md`](../../../docs/protocol.md); lo stato
del repo al momento del sigillo è marcato dal tag git `holdout-sealed`.

## Formula di Gumbel

Il DSR usa come soglia il massimo atteso di N Sharpe ottenuti per caso, approssimato con la formula di Gumbel del
paper. Su 10 000 simulazioni per ogni N, confrontate anche con il valore esatto:

| N | Simulato | Formula | Errore |
|---|---|---|---|
| 10 | 1,539 | 1,575 | +0,036 (2,3%) |
| 100 | 2,508 | 2,531 | +0,023 (0,9%) |
| 1000 | 3,241 | 3,255 | +0,014 (0,4%) |

È in linea con il paper: la formula sovrastima poco, e sempre meno al crescere di N. Lo "0,006 a N = 1000" del paper
è la cella più bassa di una heatmap rumorosa; l'errore vero è 0,014. Sul DSR vale circa 0,01 di Sharpe annuo in più
nella soglia, quindi un errore piccolo e dalla parte prudente.

## Limiti

- Fonti comunitarie invece di CRSP.
- Settore come proxy statistica, con circa 2,9 cambi per titolo all'anno.
- Spread stimato, non osservato.
- Paramount 2019-2025 rappresentata dalla classe A.
- Costo del prestito titoli non osservato: sarà un parametro.

Tutte le scelte sono state fissate prima di qualsiasi backtest.

## Dati

I dati non sono nel repo: il repo è pubblico e le licenze di Tiingo e CRSP non permettono di ridistribuirli. Le
tabelle di `data/processed/` si condividono in privato tra i collaboratori.

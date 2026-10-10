# Price band metrics (MEASURED, as_of=2026-10-09)

Rolling-origin: up to 4×14-day test folds; train strictly before each fold; one-step-ahead FQP (Rs/maund).

## Per commodity (rolling aggregate)

   commodity  n_test  mae_naive  mae_recent_median  mae_model  mape_naive  mape_recent_median  mape_model  coverage_recent_pct  coverage_model_pct  model_beats_naive
       Onion      42 338.095238         541.904762 390.517597    4.954564            7.834063    5.759632             59.52381           40.476190              False
Potato Fresh       0        NaN                NaN        NaN         NaN                 NaN         NaN                  NaN                 NaN              False
Potato Store       0        NaN                NaN        NaN         NaN                 NaN         NaN                  NaN                 NaN              False
      Tomato      41 380.487805         685.365854 422.851221    6.232919           11.796573    6.882715             78.04878           34.146341              False
       Wheat       1   0.000000           0.000000   0.000000    0.000000            0.000000    0.000000            100.00000          100.000000              False

## Per commodity × city (rolling)

   commodity       city  n_test   mae_naive  mae_recent_median   mae_model  mape_naive  mape_recent_median  mape_model  coverage_recent_pct  coverage_model_pct  model_beats_naive
       Onion Faisalabad       1 2400.000000        2400.000000 2400.366171   36.923077           36.923077   36.928710              0.00000            0.000000              False
       Onion Gujranwala       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
       Onion     Lahore      41  287.804878         496.585366  341.496900    4.174844            7.124575    4.999410             60.97561           41.463415              False
       Onion     Multan       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
       Onion      Okara       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
       Onion Rawalpindi       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
       Onion   Sargodha       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
Potato Fresh Faisalabad       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
Potato Store Faisalabad       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
Potato Store   Sargodha       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
      Tomato Faisalabad       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
      Tomato Gujranwala       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
      Tomato     Lahore      41  380.487805         685.365854  422.851221    6.232919           11.796573    6.882715             78.04878           34.146341              False
      Tomato     Multan       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
      Tomato      Okara       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
      Tomato Rawalpindi       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
      Tomato   Sargodha       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
       Wheat Faisalabad       1    0.000000           0.000000    0.000000    0.000000            0.000000    0.000000            100.00000          100.000000              False
       Wheat Rawalpindi       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False
       Wheat   Sargodha       0         NaN                NaN         NaN         NaN                 NaN         NaN                  NaN                 NaN              False

## Calibration (nominal vs observed 80% band coverage)

              band  nominal_pct  observed_pct
     model_q10_q90         80.0     38.095238
recent_median_band         80.0     69.047619

## Largest model errors (top 10)

commodity       city target_date  actual  model_pred   err_model
    Onion Faisalabad  2026-09-24  6500.0 4099.633829 2400.366171
   Tomato     Lahore  2026-09-06  6500.0 5352.962879 1147.037121
   Tomato     Lahore  2026-10-02  6000.0 4885.339323 1114.660677
    Onion     Lahore  2026-09-28  6400.0 7496.683563 1096.683563
   Tomato     Lahore  2026-08-25  5400.0 6485.372290 1085.372290
   Tomato     Lahore  2026-09-26  5400.0 6416.018426 1016.018426
   Tomato     Lahore  2026-10-04  6200.0 5221.709870  978.290130
    Onion     Lahore  2026-09-26  7200.0 8123.589843  923.589843
   Tomato     Lahore  2026-08-30  6100.0 5216.997234  883.002766
   Tomato     Lahore  2026-09-07  7300.0 6471.192700  828.807300

## Model vs naive (rolling, per commodity)
- **Onion**: model does NOT beat naive
- **Potato Fresh**: skipped (thin / no test rows)
- **Potato Store**: skipped (thin / no test rows)
- **Tomato**: model does NOT beat naive
- **Wheat**: model does NOT beat naive

## Legacy single holdout (backward compatible)

   commodity  n_test  mae_naive  mae_recent_median  mae_model  mape_naive  mape_recent_median  mape_model  coverage_recent_pct  coverage_model_pct  model_beats_naive  skipped_little_data
       Onion      15 413.333333         680.000000 549.607089    6.224680           10.214412    8.332698                 60.0           40.000000              False                   12
Potato Fresh       0        NaN                NaN        NaN         NaN                 NaN         NaN                  NaN                 NaN              False                    0
Potato Store       0        NaN                NaN        NaN         NaN                 NaN         NaN                  NaN                 NaN              False                   13
      Tomato      14 300.000000         457.142857 325.613309    5.274228            8.173716    5.696494                100.0           57.142857              False                   13
       Wheat       0        NaN                NaN        NaN         NaN                 NaN         NaN                  NaN                 NaN              False                   14
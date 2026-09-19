# 26.18 四英雄上路模型基准

截至 2026-09-18；候选是固定对手策略和 seeds [0,1] 下的 robust 排名，不是实战胜率。

## Garen_vs_Darius

- 候选 32，试验 64
- 模型最稳候选：grasp / short_trade / slow_push / Q E W E E R / ['1055']
- 均值分 470.72，最差分 323.09，胜出率 100%，补刀差 4.5，击杀差 0.5

## Darius_vs_Garen

- 候选 32，试验 64
- 模型最稳候选：conqueror / short_trade / slow_push / Q E W Q Q R / ['1055']
- 均值分 458.19，最差分 457.97，胜出率 100%，补刀差 -0.5，击杀差 1.0

## Jax_vs_Malphite

- 候选 32，试验 64
- 模型最稳候选：conqueror / short_trade / slow_push / Q E W Q Q R / ['1055']
- 均值分 165.9，最差分 157.92，胜出率 100%，补刀差 0.0，击杀差 0.0

## Malphite_vs_Jax

- 候选 32，试验 64
- 模型最稳候选：grasp / short_trade / slow_push / Q E W Q Q R / ['1056']
- 均值分 554.75，最差分 517.42，胜出率 100%，补刀差 -5.0，击杀差 1.0

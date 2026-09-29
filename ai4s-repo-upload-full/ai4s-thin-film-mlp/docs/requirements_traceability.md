# 作业要求 ↔ 交付物对照表（Requirements traceability）

学号 **2020276134** ｜ N = 34 ｜ **λtarget = 480 nm**（= 450 + 10 × (34 mod 31)）｜ **seed = 276134** ｜ **design_seed = 276135**

本文件把《AI4S 课程大作业说明》中的每一条要求映射到仓库中的具体位置，便于自查与批改。

## 一、统一研究对象（说明第 2 节）

| 要求 | 实现位置 | 实测值 |
|---|---|---|
| 膜系 Air/H/L/H/L/Glass，共 4 层 | `src/config.py: STACK = ("H","L","H","L")` | 4 层 |
| nH = 2.30, nL = 1.45, ns = 1.52 | `src/config.py: N_H/N_L/N_S` | 同 |
| 每层膜厚 40–180 nm | `src/config.py: D_MIN_NM/D_MAX_NM` | 均匀采样 |
| 波长 400–800 nm，步长 10 nm，41 点 | `src/config.py: WAVELENGTHS_NM` | 41 点，λtarget 为第 8 点 |
| 数据集 5000 组 = 4000 + 500 + 500 | `src/data.py: build_dataset()` | 4000/500/500（固定索引） |
| MLP 输入 4 个膜厚，输出 41 点反射率 | `src/train_utils.py: MLPSurrogate` | 4–128–128–64–41 |

## 二、个性化参数（说明第 3 节）

| 要求 | 实现位置 | 实测值 |
|---|---|---|
| λtarget = 450 + 10 × (N mod 31) nm | `src/config.py: LAMBDA_TARGET_NM` | **480 nm** |
| seed = 学号后 6 位 | `src/config.py: SEED` | **276134** |
| design_seed = seed + 1 | `src/config.py: DESIGN_SEED` | **276135** |
| 代码中显式设置随机种子 | `src/runtime.py: seed_everything()` | random / numpy / torch 三处均显式设置 |

## 三、必须完成的四项工作（说明第 4 节）

| # | 要求 | 实现位置 | 产物 |
|---|---|---|---|
| 1 | TMM 与数据生成 | `src/tmm.py`, `src/data.py` | `data/dataset.npz`, `results/dataset_fingerprint.json` |
| 2 | MLP 光谱预测 | `src/train_mlp.py` | `figures/fig4_loss_curve.*`, `figures/fig5_prediction_test_samples.*` |
| 3 | 数据量影响（500/1000/2000/4000） | `src/train_sizes.py` | `figures/fig6_training_size.*`, `results/tables/training_size_results.csv` |
| 4 | MLP 辅助设计（design_seed 生成 10000 候选 → Top10 TMM 验证） | `src/screening.py` | `figures/fig7_design.*`, `results/tables/table1_top5.md` |

## 四、三个科研问题（说明第 5 节）

| 问题 | 论文位置 | 定量答案 |
|---|---|---|
| Q1 MLP 能否准确预测光谱？ | 3.1 / 4 / 5 | 测试 RMSE = **0.00891**（= 平均反射率的 3.0 %）；λtarget 处 MAE = 0.00776 |
| Q2 数据量增加后误差如何变化？ | 3.2 / 4 / 5 | 500→4000 组：RMSE 0.02886 → 0.00891；逐次翻倍的 MSE 降幅 65.5 % → 53.2 % → **41.1 %**（边际递减） |
| Q3 MLP 能否辅助快速筛选？ | 3.3 / 4 / 5 | 10000 候选筛选 MLP ≈0.008 s vs TMM ≈0.11 s（**×13–14**）；最优设计经 TMM 验证 R(480 nm) = **0.6566**（池内 99.9 分位 = 0.6492）。注意：MLP 自己排第一的候选被 TMM 降到第 2 名（0.6674→0.6527），真正最优者的 MLP 排名为第 2 |

## 五、论文与 GitHub（说明第 6 节）

| 要求 | 位置 |
|---|---|
| 使用课程单栏 Research Article 模板 | `paper/AI4S_Research_Article_2020276134.docx`（沿用模板 styles/header/footer/section 设置）、`...pdf` |
| Abstract / Introduction / Materials and Methods / Results / Discussion / Conclusions / Data and Code Availability / References | 全部齐备 |
| 总体框架图 | Figure 1（`figures/fig1_workflow.png`） |
| TMM/数据示意图 | Figure 2（`figures/fig2_model_and_data.png`） |
| MLP 结构图 | Figure 3（`figures/fig3_mlp_architecture.png`） |
| 训练、预测、数据量影响、辅助设计结果 | Figures 4–7 |
| **必须保留并分析失败案例** | Figure 8 + 正文 3.4 节（测试集最差样本，逐项分析误差来源） |
| Table 1：Top 5 的 d1–d4 / MLP Rtarget / TMM Rtarget | 论文 Table 1 = `results/tables/table1_top5.md` |
| README 写明 λtarget / seed / design_seed + 环境 / 数据生成 / 训练 / 复现 / 筛选方法 | `README.md` |
| requirements.txt（或 environment.yml） | `requirements.txt` |
| 复现论文主要结果所需脚本 | `src/` 下 4 个入口脚本，`README.md` 给出逐条命令 |
| 参考文献 8–12 篇真实文献，覆盖光学薄膜/TMM 与 ML 辅助设计 | 12 篇，含 Macleod、Born & Wolf、Byrnes(TMM)、iScience 综述、OptoGPT、needle/GA、Adam、He 初始化、SciPy |

## 六、提交物（说明第 7 节）

1. `paper/AI4S_Research_Article_2020276134.docx` + `.pdf`（英文正文稿）
2. `paper/AI4S_研究论文_中文稿_2020276134.docx` + `.pdf`（中文正文稿，图表标签亦为中文）
3. GitHub 仓库链接：**https://github.com/Jfzz-KK/123435**（已写入论文的 Data and Code Availability 与 README）

> 说明：本机沙箱禁止 Word COM 自动化（HRESULT 0x800A13E9），无法由 docx 直接导出 PDF。
> PDF 由 `src/make_pdf.py` / `src/make_pdf_zh.py` 用 reportlab 重新排版，内容与 Word 稿取自同一批
> `results/*.json`，因此两种格式、两种语言的数字完全一致。

## 七、AI 使用与学术诚信（说明第 8 节）

- 论文中的每一个数字都来自 `results/*.json`，由 `src/*.py` 生成；`README.md` 记录了数据集 sha256 指纹，可校验数据未被改动。
- 所有文献均为真实可查条目，未编造。
- AI 仅用于代码调试、结构组织与语言润色；运行结果由本仓库脚本实际产生。

## 八、复现命令（约 9 分钟，单核 CPU）

```bash
python tests/test_tmm.py      # TMM 物理自检（6 项）
python src/data.py            # 数据集 + 固定划分
python src/train_mlp.py       # 主实验（图 1-5、8，英文图）
python src/train_sizes.py     # 数据量实验（图 6、表 2）
python src/screening.py       # 筛选实验（图 7、表 1）
python src/make_paper.py      # 生成英文 Word 稿件
python src/make_pdf.py        # 生成英文 PDF 稿件
# 中文稿（图内标签也中文化）
python src/train_mlp.py    --lang zh
python src/train_sizes.py  --lang zh
python src/screening.py    --lang zh
python src/make_paper_zh.py
python src/make_pdf_zh.py
```

一键复现：`python run_all.py`（加 `--quick` 可跳过最慢的数据量实验）。

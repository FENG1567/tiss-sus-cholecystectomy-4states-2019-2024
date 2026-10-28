# TISS–SUS 胆囊切除术式编码构成

项目ID：`TISS_SUS_CHOLECYSTECTOMY_4UF_2019_2024_STANDARDIZED_V1`。

本目录复现 Amazonas（AM）、Pernambuco（PE）、Rio Grande do Sul（RS）和
São Paulo（SP）在2019年及2024年的聚合行政记录比较，范围限于术式编码构成。
TISS计数单位是事件，SIH/SUS计数单位是授权；二者都不等同于独立患者数。

## 重建主表

需要 Python 3.10 或更高版本。核心代码仅使用 Python 标准库。

Windows 在仓库根目录运行：

```powershell
python scripts\reproduce.py --out out
```

macOS 或 Linux：

```sh
python3 scripts/reproduce.py --out out
```

默认运行需要 `data/extensions/joint_counts_known.csv`。程序根据已知年龄池、
性别及择期/急诊组合重新筛选共同支持集：只有两来源严格记录数均不少于20的
分层才纳入 H。之后逐格与已发表的 `core/reference/H_STRATA.csv` 对照，
再计算标准化结果。未知或未映射的联合分类不会被推测填补。

所有结果都写入 `--out` 指定目录：

- `core/table1_source_composition.csv`：由基线、年龄、性别及急择期聚合计数
  重建的16行Table 1；各百分比以对应来源严格N为分母。
- `core/table2_standardized_results.csv`：8个州年标准化比例、差距、条件情景端点
  及H覆盖率。
- `core/reselected_H_strata_with_weights.csv`：从已知联合计数重筛得到的123个分层，
  含两来源L/O/B/N/A计数及精确、十进制H权重，可用于重建分层补充表。
- `core/reconstructed_comparisons.csv`：未舍入的数值重建结果；与州年参考表和
  测量情景参考表按绝对误差 `1e-9` 比较。
- `extensions/`：默认运行中的H、A、来源流程及其他聚合复核结果。
- `figures/`：请求绘图后保存PDF、PNG、SVG三种格式的图片。

可选参数 `--ciha` 会运行独立的CIHA/SIH聚合bootstrap复现，并将输出放在
`ciha/`。需先安装额外Python依赖：`python -m pip install -r requirements-ciha.txt`。
默认核心复现不会安装或导入这些可选包。若要同时重建图形和运行CIHA，
请在上面的绘图命令中同时加入 `--figures` 和 `--ciha`。

如果开发时暂时没有联合已知分类表，可显式同时加入
`--use-supplied-H --core-only`。程序会直接使用已接受的 `H_STRATA.csv`，不重筛H；
由于扩展模块仍需联合计数，这个组合会跳过扩展复核。

## 重建图形

本机绘图运行环境为 R 4.3.1、支持 Cairo 的 PDF 输出、Arial 字体及
`requirements-R.csv` 中列出的固定包版本。安装固定版本：

```sh
Rscript --vanilla install_R_dependencies.R
```

程序按 `--rscript`、`R_SCRIPT` 环境变量、`PATH` 的顺序查找 Rscript。Windows 示例：

```powershell
python scripts\reproduce.py --out out --figures --rscript (Get-Command Rscript).Source
```

如果Rscript不在 `PATH`，请将 `--rscript` 或 `R_SCRIPT` 环境变量设为本机
Rscript可执行文件路径。示例不假定安装目录或R版本。

macOS 或 Linux 示例：

```sh
python3 scripts/reproduce.py --out ./out --figures --rscript "$(command -v Rscript)"
```

当前修订版绘图脚本生成主图1–5和补充图S1–S5，共10组图，每组导出PDF、PNG、
SVG三种格式。仓库保存绘图代码、聚合CSV输入和22份面板参考数据，渲染后的
图片文件在运行脚本时生成。

本机测试环境为 R 4.3.1，`requirements-R.csv` 中列出的包版本均已测试；
其他R或包版本尚未在本包中测试。

## 估计目标与解释

严格分母为 `N = L + O + B`：L表示仅编码腹腔镜家族，O表示仅编码对照家族，
B表示两家族都有编码。O不能临床验证为开放术式，B也不能确认中转。TISS中符合
其他条件但数量字段有歧义的记录A在N之外，并进入指定编码情景。

共同支持集H按年龄池×已知性别×择期/急诊构建。每个州年内，分层权重为TISS在H
中比例与SUS在H中比例的平均值。计算先用精确有理数，再转换为CSV数值。结果与
`STATE_YEAR_TABLE_8.csv` 和 `MEASUREMENT_SCENARIOS_8.csv` 比较。

固定H情景范围依据文中公式重新分类歧义数量和双编码记录。它是条件编码情景，
不是置信区间、因果效应或全部偏倚的界限。SP 2024的范围包含零（约−1.57至
10.67个百分点），也不能解释为统计不确定性区间。本包不生成p值或显著性结论。

本聚合包不含原始记录，也不声称完成临床病历验证或独立重新提取数据。未知协变量
组合不进入已知联合分类表；全来源分母及覆盖率继续来自基线聚合计数。

## 数据、代码许可与引用

复现代码使用MIT许可，见 `LICENSE`。衍生聚合输入仍受上游数据来源的访问和复用
条款约束；来源说明见 `DATA_SOURCES.md`。包中不含ANS或DATASUS原始记录，也不授予
上游数据的额外使用权。

当前论文作者列于 `CITATION.cff`。公开仓库为
https://github.com/FENG1567/tiss-sus-cholecystectomy-4states-2019-2024。
代码可用性声明见 `CODE_AVAILABILITY.md`，版本化代码快照为 `v1.0.0`。

## 文件与结果对应

上传文件及补齐项目见[整理与补齐说明](整理与补齐说明_中文.md)；运行环境见[ENVIRONMENT](docs/ENVIRONMENT.md)，输入定义见[INPUTS](docs/INPUTS.md)，逐图表对应见[RESULTS_MAP](docs/RESULTS_MAP.csv)。CIHA可选依赖要求Python 3.12或更高版本。

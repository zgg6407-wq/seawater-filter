# 本机验证记录

验证日期：2026-10-04（Asia/Shanghai）。

- 独立目录 E:\市场状态过滤器，独立 Python 3.12.7 虚拟环境。
- `pip install -e .` 安装成功，CLI 控制台入口可运行，`pip check` 无依赖冲突。
- `python -m unittest discover -s tests -v`：13 项全部通过。
- `market-state-filter demo`：1,200 根合成 K 线，573 条候选线；384 条成熟训练样本、177 条留出样本。成功生成 JSON、Markdown、HTML 和 SVG。
- 源码与运行产物分离，输出、数据库和虚拟环境由 `.gitignore` 排除。
- API 测试只运行临时目录下的回环地址测试实例，测试结束关闭；没有常驻公网服务、模型调用或交易请求。

演示结果仅证明工程链路可运行，不能证明真实市场有效性或盈利。真实数据研究、多轮 walk-forward、概率校准、任务自动执行、公网生产部署未验收。

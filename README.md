# 知枢 · zhishu-adaptive-knowledge-companion

把任何学习材料——一个知识点、一组题、一份课件、一本书、多本书——变成"按依赖带你走、答错倒推根因、难点从零推透"的单文件交互学习网页。

## 特性

- 自动识别输入形态（知识点/题目/课件/书/多书），走最轻流水线
- 概念依赖力导向图（vis-network），点击跳转
- 答错沿前置链倒推根因 + 误解卡片纠偏
- FSRS 间隔重复抽认卡
- 掌握度概率估计（简化 BKT）
- 学习热力图 + 连续 streak
- 错题本自动收集
- KaTeX 公式、滚动淡入、字号调节、阅读进度条、打印/PDF 导出
- Pico CSS 美化，深色模式

## 使用

这是一个 Doubao 工作模式 skill，不是独立 Web 应用。把整个目录放进 `~/.doubao/agent_mode/workspace/.user_skills/` 即可在对话中调用。

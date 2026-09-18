from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUT = Path("/Users/bytedance/Desktop/bench/DataAgentBench_项目进展汇报_TODO强化版_20260607.docx")

BLUE = RGBColor(46, 116, 181)
DARK_BLUE = RGBColor(31, 77, 120)
INK = RGBColor(31, 41, 55)
MUTED = RGBColor(90, 99, 115)
LIGHT_GRAY = "F2F4F7"
CALLOUT = "F4F6F9"
WHITE = "FFFFFF"
TABLE_WIDTH = 9360
TABLE_INDENT = 120


def set_font(run, size=None, bold=None, italic=None, color=None, name="Calibri"):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:ascii"), name)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), name)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def set_para_format(paragraph, before=0, after=6, line_spacing=1.10):
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.line_spacing = line_spacing


def setup_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.10

    for name, size, color, before, after in [
        ("Heading 1", 16, BLUE, 16, 8),
        ("Heading 2", 13, BLUE, 12, 6),
        ("Heading 3", 12, DARK_BLUE, 8, 4),
    ]:
        style = doc.styles[name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.color.rgb = color
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.10

    for name in ("List Bullet", "List Number"):
        style = doc.styles[name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(11)
        style.paragraph_format.left_indent = Inches(0.5)
        style.paragraph_format.first_line_indent = Inches(-0.25)
        style.paragraph_format.space_after = Pt(8)
        style.paragraph_format.line_spacing = 1.167


def setup_page(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.right_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    header = section.header
    hp = header.paragraphs[0]
    hp.text = ""
    hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_para_format(hp, after=0)
    r = hp.add_run("DataAgentBench | 项目进展汇报")
    set_font(r, size=9, color=MUTED)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_para_format(fp, after=0)
    r = fp.add_run("2026-06-06")
    set_font(r, size=9, color=MUTED)


def shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, bottom=80, start=120, end=120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    mar = tc_pr.first_child_found_in("w:tcMar")
    if mar is None:
        mar = OxmlElement("w:tcMar")
        tc_pr.append(mar)
    for side, value in (("top", top), ("bottom", bottom), ("start", start), ("end", end)):
        node = mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def table_geometry(table, widths):
    table.autofit = False
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(TABLE_WIDTH))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(TABLE_INDENT))
    tbl_ind.set(qn("w:type"), "dxa")

    grid = tbl.tblGrid
    if grid is None:
        grid = OxmlElement("w:tblGrid")
        tbl.insert(0, grid)
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)

    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            cell.width = Inches(widths[idx] / 1440)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = tc_pr.find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW")
                tc_pr.append(tc_w)
            tc_w.set(qn("w:w"), str(widths[idx]))
            tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def set_table_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "4")
        node.set(qn("w:space"), "0")
        node.set(qn("w:color"), "D9DEE7")


def fill_cell_text(cell, text, bold=False, color=INK, size=9.4):
    cell.text = ""
    p = cell.paragraphs[0]
    set_para_format(p, after=0, line_spacing=1.10)
    r = p.add_run(str(text))
    set_font(r, size=size, bold=bold, color=color)


def add_table(doc, headers, rows, widths, font_size=9.4):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table_geometry(table, widths)
    set_table_borders(table)
    for idx, header in enumerate(headers):
        shade_cell(table.rows[0].cells[idx], LIGHT_GRAY)
        fill_cell_text(table.rows[0].cells[idx], header, bold=True, size=font_size)
    for row in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            fill_cell_text(cells[idx], value, size=font_size)
    doc.add_paragraph()
    return table


def add_heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    return p


def add_para(doc, text="", bold_prefix=None):
    p = doc.add_paragraph()
    set_para_format(p)
    if bold_prefix and text.startswith(bold_prefix):
        r = p.add_run(bold_prefix)
        set_font(r, bold=True)
        r = p.add_run(text[len(bold_prefix):])
        set_font(r)
    else:
        r = p.add_run(text)
        set_font(r)
    return p


def add_bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    r = p.add_run(text)
    set_font(r)
    return p


def add_callout(doc, label, text):
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    table_geometry(table, [TABLE_WIDTH])
    set_table_borders(table)
    cell = table.cell(0, 0)
    shade_cell(cell, CALLOUT)
    set_cell_margins(cell, top=120, bottom=120, start=160, end=160)
    p = cell.paragraphs[0]
    set_para_format(p, after=0, line_spacing=1.15)
    r = p.add_run(f"{label}: ")
    set_font(r, size=10.5, bold=True, color=DARK_BLUE)
    r = p.add_run(text)
    set_font(r, size=10.5, color=INK)
    doc.add_paragraph()


def add_title_block(doc):
    p = doc.add_paragraph()
    set_para_format(p, before=8, after=2)
    r = p.add_run("DataAgentBench 项目进展汇报")
    set_font(r, size=23, bold=True, color=RGBColor(0, 0, 0))
    p = doc.add_paragraph()
    set_para_format(p, after=14)
    r = p.add_run("Benchmark / Evaluation Paper 进展、已优化点与 Todo 优先级")
    set_font(r, size=13.5, color=MUTED)
    rows = [
        ("汇报对象", "导师讨论 / 论文推进会"),
        ("更新时间", "2026-06-07"),
        ("当前状态", "已完成 Bench / TaskGen 分离、verified smoke set 和 validity 修复第一阶段"),
        ("推荐主线", "SIGMOD / CIKM 风格的 Benchmark and Resource Paper"),
    ]
    add_table(doc, ["项目", "内容"], rows, [1700, 7660], font_size=9.7)


def build_doc():
    doc = Document()
    setup_page(doc)
    setup_styles(doc)
    add_title_block(doc)

    add_heading(doc, "1. 本轮核心结论", 1)
    add_callout(
        doc,
        "当前判断",
        "项目已经从“直接扩跑模型”切换到“优先修复 benchmark validity”。旧 pilot20/121 任务因 GT 可信度不足，仅作为 debug 参考；正式结论将基于 verified tasks 重跑。",
    )
    for item in [
        "已完成 Bench / TaskGen 同仓模块分离：Bench 只消费 verified 静态任务，TaskGen 负责生成、验证和打包。",
        "GT 只能由 deterministic verifier 从 dataset.csv + task_manifest.json 复算得到，LLM 不拥有 GT 设置权。",
        "已生成 12 个 clean verified tasks 和 15 个 paired redteam verified tasks，全部通过 replay 和默认加载检查。",
        "下一步不是继续解释旧分数，而是在 verified set 上做模型和处理策略 sanity check。",
    ]:
        add_bullet(doc, item)

    add_heading(doc, "2. 已优化点：本轮已经修好的关键问题", 1)
    add_callout(
        doc,
        "优化重点",
        "本轮不是单纯扩展任务数量，而是把 benchmark 的可信边界、GT 生成机制、redteam 公平性和正式评测入口先锁住。下面这些优化直接回应了旧实验中“分数反常、GT 不可信、trace 难解释”的问题。",
    )
    add_table(
        doc,
        ["已优化点", "原问题", "当前结果 / 价值"],
        [
            (
                "Bench / TaskGen 模块分离",
                "旧流程里生成、求解、评测边界混在一起，GT 问题会污染正式评测。",
                "Bench 默认只加载 verified task；TaskGen 只生产候选或 verified task，职责边界清楚。",
            ),
            (
                "Verifier-backed GT",
                "LLM 直接写 GT 会出现 hallucination、forced submit、prompt/GT mismatch。",
                "GT 由 deterministic verifier replay 生成，记录 formula、dataset SHA256、computed_at。",
            ),
            (
                "Formal source filtering",
                "legacy、candidate、curated task 容易误进 leaderboard。",
                "`tasks_curated_easy_v1`、`tasks_legacy_unverified`、`tasks_taskgen_candidates` 默认正式加载为 0。",
            ),
            (
                "Scoring V3 思路",
                "旧 accuracy 混合了 final answer、trace 中间值、timeout、format extraction。",
                "拆分 FinalAcc、ObservedTraceAcc、GroundedFinalAcc，process/safety/trace integrity 降为 diagnostic。",
            ),
            (
                "Paired redteam GT policy",
                "扰动后继续使用旧答案会造成不公平或不可比。",
                "schema_obfuscation / distractor_columns 采用 invariant GT；dirty_data 采用 recomputed GT。",
            ),
            (
                "Verified smoke set",
                "旧 121 任务规模大但 verified provenance 不足。",
                "已生成 12 clean + 15 redteam verified tasks，全部 replay pass，可用于下一步 sanity check。",
            ),
        ],
        [2100, 3400, 3860],
        font_size=8.6,
    )

    add_heading(doc, "3. Todo 优先级：接下来先做什么", 1)
    add_callout(
        doc,
        "当前优先级",
        "先在 verified set 上证明 scoring、trace 和 GT 都正常，再扩任务规模。不要再用旧 pilot20/121 做正式模型结论。",
    )
    add_table(
        doc,
        ["优先级", "Todo", "验收标准", "建议产物"],
        [
            (
                "P0",
                "Verified model sanity check：跑 gpt-4o-mini、gpt-5.4、gpt-5.3-codex。",
                "12 clean + 15 redteam 均产生 report/trace；异常分数能归因到 result、trace、timeout 或 scorer。",
                "verified_core_v1_model_sanity.md；verified_redteam_v1_model_sanity.md",
            ),
            (
                "P0.5",
                "Strategy-level sanity check：比较 Direct Answer、Code Agent、Schema-aware、Validation-aware、Robustness-aware。",
                "证明 benchmark 不只是模型排行榜，还能诊断不同处理问题的方法。",
                "strategy_ablation_smoke.md",
            ),
            (
                "P1",
                "扩展 verified benchmark pilot 到 60 clean + 60 redteam。",
                "GT replay 100% pass；domain/difficulty/template/attack type 分布可报告。",
                "verified_benchmark_v1_construction.md",
            ),
            (
                "P2",
                "增强任务真实感：接入 seed_csv_copy / light_transform builder。",
                "至少 Finance/Biomedical/ECommerce/Scientific 四类 seed 数据可生成 verified task。",
                "dataset/task statistics + seed builder docs",
            ),
            (
                "P3",
                "补论文图表：Figure 1/2、Table 1/2/3/strategy ablation。",
                "Introduction、Benchmark Design、Evaluation Protocol 能形成闭环。",
                "论文初稿 v1",
            ),
        ],
        [900, 2850, 3500, 2110],
        font_size=8.2,
    )

    add_heading(doc, "4. 论文定位与核心 Gap", 1)
    add_para(
        doc,
        "本文按 Benchmark / Evaluation / Resource Paper 包装，评测对象是 Data Agent 系统整体，包括 LLM、prompt strategy、代码执行、工具调用、trace 和 final answer reporting。",
    )
    add_table(
        doc,
        ["核心 Gap", "说明", "DataAgentBench 对应设计"],
        [
            ("Final-answer-only 不够", "只看最终答案无法区分 trace 中算对但提交错、格式抽取失败、盲目重试等情况。", "同时报告 FinalAcc、ObservedTraceAcc、GroundedFinalAcc、TraceIntegrity。"),
            ("GT 难以可信生成", "LLM 同时生成任务和 GT 会出现 hallucinated GT、forced submit、prompt/GT mismatch。", "正式任务必须由 verifier replay 生成 GT，并记录 SHA256、formula、computed_at。"),
            ("缺少公平 robustness 测试", "很多扰动会改变任务本身，导致 clean/redteam 不可比。", "paired redteam 明确区分 invariant GT 和 recomputed GT。"),
        ],
        [1900, 4050, 3410],
        font_size=8.9,
    )

    add_heading(doc, "5. 当前工程进度", 1)
    add_heading(doc, "5.1 Bench / TaskGen 边界", 2)
    add_table(
        doc,
        ["模块", "职责", "正式评测约束"],
        [
            ("Bench", "task loading、runner、trace、scoring、report、leaderboard", "默认只加载带 verified provenance 的任务。"),
            ("TaskGen", "manifest sampling、dataset building、verifier registry、packager、redteam builder", "可生成任务，但不能让 LLM 直接写 formal GT。"),
            ("Legacy / Candidate", "旧任务、候选任务、curated 修复参考", "默认排除正式 leaderboard，仅用于 debug。"),
        ],
        [1600, 4320, 3440],
        font_size=9.1,
    )
    add_heading(doc, "5.2 Verified Smoke Set", 2)
    add_table(
        doc,
        ["任务集", "规模", "构成", "Replay / Load", "报告"],
        [
            ("tasks_verified_core_v1", "12 clean tasks", "6 verifier templates x 2", "12/12 PASS", "verified_core_v1_smoke.md"),
            ("tasks_verified_redteam_v1", "15 redteam tasks", "5 base tasks x 3 attacks", "15/15 PASS", "verified_redteam_v1_smoke.md"),
        ],
        [2100, 1600, 2500, 1550, 1610],
        font_size=8.9,
    )
    add_table(
        doc,
        ["Redteam Attack", "GT Policy", "数量", "公平性原则"],
        [
            ("schema_obfuscation", "invariant", "5", "只改列名与 prompt 引用，不改数据含义。"),
            ("distractor_columns", "invariant", "5", "加入无关列，不改变目标列与目标计算。"),
            ("dirty_data", "recomputed", "5", "改变数据质量后重新由 verifier 计算 GT。"),
        ],
        [2400, 1600, 900, 4460],
        font_size=9.1,
    )

    add_heading(doc, "6. 为什么需要重构 Pipeline", 1)
    add_para(doc, "旧 pilot20 的 GT audit 显示，旧任务无法直接支撑模型能力结论。")
    add_table(
        doc,
        ["Audit Status", "数量", "含义"],
        [
            ("GT_VALUE_MISMATCH", "11", "GT 数值和复算结果不一致。"),
            ("PASS_RECOMPUTED", "3", "可复算，但仍缺 formal provenance。"),
            ("PROMPT_GT_MISMATCH", "2", "任务描述、tags 或 GT 模板不一致。"),
            ("UNVERIFIABLE_GENERATION_TRACE", "4", "生成 trace 有错误或 forced submit，无法信任。"),
        ],
        [2700, 1100, 5560],
        font_size=9.2,
    )
    add_callout(
        doc,
        "结论",
        "旧结果中出现 “4o-mini > 5.x” 不能直接解释为模型能力差异，更可能混入 GT 错误、scorer 抽取、API timeout 和 finalization protocol 等因素。",
    )

    add_heading(doc, "7. GT 生成方法与被测处理策略", 1)
    add_heading(doc, "7.1 GT 生成方法对比", 2)
    add_table(
        doc,
        ["方案", "优点", "主要风险", "正式用途"],
        [
            ("LLM 直接生成 GT", "快、覆盖面广", "hallucinated GT、forced submit、prompt/GT mismatch", "candidate only"),
            ("LLM solution trace 抽取", "可看到计算过程", "代码可能错，trace 仍需 replay", "debug / audit"),
            ("人工专家标注", "可信度高", "成本高、扩展慢", "抽样审计与 case study"),
            ("Deterministic verifier", "可复算、可追责、低成本扩展", "受限于 verifier templates", "formal GT authority"),
            ("Hybrid pipeline", "LLM 多样性 + verifier 可靠性", "需要维护 registry", "推荐最终方案"),
        ],
        [2100, 2400, 3300, 1560],
        font_size=8.7,
    )
    add_heading(doc, "7.2 被测处理方法 / Agent Strategy 对比", 2)
    add_table(
        doc,
        ["处理策略", "做法", "验证点", "预期观察"],
        [
            ("Direct Answer", "不执行代码，直接回答", "是否依赖语言捷径", "redteam 和多 key 任务应明显失败。"),
            ("Code Agent", "读取 CSV，写 Python 计算", "基础 data workflow", "主 baseline。"),
            ("Schema-aware", "先做 schema/profile，再选列和方法", "减少列选择错误", "schema_obfuscation/distractor 更稳。"),
            ("Validation-aware", "计算后做 row count、group key、自检", "减少 silent wrong answer", "GroundedFinalAcc 应提高。"),
            ("Robustness-aware", "先诊断混淆列、无关列、脏数据", "提升 robustness retention", "dirty_data/distractor 更有优势。"),
            ("Oracle / Verifier", "运行可信 verifier 或 oracle script", "上限和 scorer sanity check", "不参与正式模型排名。"),
        ],
        [1850, 2500, 2400, 2610],
        font_size=8.4,
    )

    add_heading(doc, "8. Checklist 完成度", 1)
    add_table(
        doc,
        ["模块", "当前完成度", "仍缺什么"],
        [
            ("Introduction", "Gap 和 RQ 草案基本成型", "需要换成 verified running example，补 Table 1 相关工作对比。"),
            ("Benchmark 章节", "Design goals、pipeline、quality gate 已有工程基础", "需要画正式 Figure 2，扩展数据统计。"),
            ("Experiments", "trace/scorer/failure 工具有了", "需要在 verified set 上重跑模型和 strategy baselines。"),
            ("Artifact", "任务目录契约、dataset SHA256、verifier replay 已实现", "需要整理开源包、dataset card、model/eval card。"),
        ],
        [1700, 3500, 4160],
        font_size=8.9,
    )

    add_heading(doc, "9. 当前风险与处理计划", 1)
    add_table(
        doc,
        ["风险", "影响", "下一步处理"],
        [
            ("Smoke set 规模小", "只能证明 pipeline 可行，不能支撑论文结论。", "扩展到 60 clean + 60 redteam。"),
            ("Synthetic-only 真实感不足", "SIGMOD/CIKM 审稿可能质疑任务真实性。", "接入 seed_csv_copy / light_transform builder。"),
            ("Verifier template 覆盖有限", "开放式任务和复杂 data engineering 任务不足。", "新增 time-series、hypothesis test、missing-value、multi-table join verifier。"),
            ("旧结果不可正式使用", "不能拿旧 GLM/GPT pilot 做模型排名。", "只在汇报中作为 validity repair 的动机。"),
        ],
        [2100, 3400, 3860],
        font_size=8.9,
    )

    add_heading(doc, "10. Immediate Next 3 Days", 1)
    for idx, item in enumerate(
        [
            "在 tasks_verified_core_v1 上跑 gpt-4o-mini、gpt-5.4、gpt-5.3-codex。",
            "在 tasks_verified_redteam_v1 上跑同样模型，计算 RobustnessRetention。",
            "固定一个模型做 strategy-level sanity check：Direct Answer、Code Agent、Schema-aware、Validation-aware、Robustness-aware。",
            "检查所有异常低分的 trace，先修 scorer/trace，再扩任务。",
            "决定是否先接 seed CSV builder，再扩到 60 clean + 60 redteam。",
            "把 Figure 2 construction pipeline 和 verified running example 草图做出来。",
        ],
        start=1,
    ):
        p = doc.add_paragraph(style="List Number")
        r = p.add_run(item)
        set_font(r)

    add_heading(doc, "11. 需要导师确认的问题", 1)
    for item in [
        "从“121 unverified tasks”切换到“verified pipeline + smaller pilot”的叙事是否更稳？",
        "SIGMOD/CIKM 口味下，synthetic + seed CSV 混合构建是否足够？",
        "Redteam 三类扰动 schema_obfuscation、distractor_columns、dirty_data 是否合理？",
        "主表是否应以 accuracy/robustness 为主，process/safety/trace integrity 作为 diagnostic？",
        "是否需要加入一个简单 specialized method，还是先专注 benchmark + empirical findings？",
    ]:
        add_bullet(doc, item)

    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build_doc()
